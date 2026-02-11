from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from justpipe._internal.runtime.engine.pipeline_runner import _PipelineRunner
from justpipe._internal.runtime.engine.composition import (
    RunnerConfig,
    build_runner,
    build_runner_deps,
)
from justpipe._internal.definition.steps import _BaseStep, _StandardStep
from justpipe._internal.runtime.orchestration.control import (
    InvocationContext,
    StepCompleted,
)
from justpipe._internal.types import _Map
from justpipe.types import Event, EventType, NodeKind


def _empty_config(queue_size: int = 0) -> RunnerConfig[Any, Any]:
    return RunnerConfig(
        steps={},
        topology={},
        injection_metadata={},
        startup_hooks=[],
        shutdown_hooks=[],
        queue_size=queue_size,
    )


def _single_edge_config() -> RunnerConfig[Any, Any]:
    steps: dict[str, _BaseStep] = {
        "a": _StandardStep(name="a", func=lambda: None),
        "b": _StandardStep(name="b", func=lambda: None),
    }
    return RunnerConfig(
        steps=steps,
        topology={"a": ["b"]},
        injection_metadata={},
        startup_hooks=[],
        shutdown_hooks=[],
    )


def _single_step_config() -> RunnerConfig[Any, Any]:
    return RunnerConfig(
        steps={"entry": _StandardStep(name="entry", func=lambda: None)},
        topology={},
        injection_metadata={},
        startup_hooks=[],
        shutdown_hooks=[],
    )


async def _no_step_events(
    item: StepCompleted, state: Any, context: Any
) -> AsyncGenerator[Event, None]:
    _ = (item, state, context)
    if False:
        yield Event(EventType.TOKEN, "unused")


def test_build_runner_deps_honors_queue_size() -> None:
    deps = build_runner_deps(_empty_config(queue_size=7))
    assert deps.queue.maxsize == 7
    assert deps.kernel is not None


def test_build_runner_deps_plan_matches_runtime_graph() -> None:
    deps = build_runner_deps(_single_edge_config())
    assert deps.plan.roots == {"a"}
    assert deps.plan.parents_map == deps.graph.parents_map_snapshot()


@pytest.mark.asyncio
async def test_build_runner_returns_runnable_runner() -> None:
    runner = build_runner(_empty_config(queue_size=3))
    assert isinstance(runner, _PipelineRunner)
    assert runner._tracker is not None

    events = [event async for event in runner.run(state={})]
    assert any(event.type == EventType.STEP_ERROR for event in events)
    assert events[-1].type is EventType.FINISH


def test_prepare_event_preserves_origin_run_lineage() -> None:
    """Forwarded events keep source lineage while adopting local stream ownership."""
    runner = build_runner(_empty_config())
    runner._ctx.run_id = "parent-run"

    forwarded = runner._prepare_event(
        Event(
            EventType.STEP_START,
            "child_step",
            run_id="child-run",
            origin_run_id="root-run",
        )
    )
    assert forwarded.run_id == "parent-run"
    assert forwarded.origin_run_id == "root-run"
    assert forwarded.seq == 1

    forwarded_without_origin = runner._prepare_event(
        Event(
            EventType.STEP_START,
            "child_step",
            run_id="child-run",
        )
    )
    assert forwarded_without_origin.run_id == "parent-run"
    assert forwarded_without_origin.origin_run_id == "child-run"
    assert forwarded_without_origin.seq == 2

    native_event = runner._prepare_event(Event(EventType.STEP_START, "native"))
    assert native_event.run_id == "parent-run"
    assert native_event.origin_run_id == "parent-run"
    assert native_event.seq == 3


@pytest.mark.asyncio
async def test_handle_result_deferred_owner_emits_worker_and_owner_terminal() -> None:
    runner = build_runner(_single_step_config())
    runner._ctx.state = {"state": "ok"}
    runner._ctx.context = {"ctx": "ok"}
    published: list[Event] = []
    barrier_calls: list[str] = []

    async def publish(event: Event) -> Event:
        published.append(event)
        return event

    async def process_result(
        item: StepCompleted, state: Any, context: Any
    ) -> AsyncGenerator[Event, None]:
        _ = (state, context)
        yield Event(EventType.TOKEN, item.name, "token")

    def on_step_completed(owner: str, name: str) -> list[dict[str, Any]]:
        if owner == name:
            return [
                {"owner_invocation_id": "owner-inv", "owner_scope": ("root", "map")}
            ]
        return []

    runner._publish = publish
    runner._results.process_step_result = process_result  # type: ignore[method-assign]
    runner._scheduler.on_step_completed = on_step_completed  # type: ignore[method-assign,assignment]
    runner._barriers.handle_completion = barrier_calls.append  # type: ignore[method-assign,assignment]

    owner_invocation = InvocationContext(
        invocation_id="owner-inv",
        owner_invocation_id="owner-inv",
        attempt=2,
        scope=("root",),
        node_kind=NodeKind.MAP,
    )
    worker_invocation = InvocationContext(
        invocation_id="worker-inv",
        parent_invocation_id="owner-inv",
        owner_invocation_id="owner-inv",
        scope=("root", "worker"),
    )

    runner._tracker.total_active_tasks = 2
    runner._tracker.logical_active["map_owner"] = 2

    first_events = [
        event
        async for event in runner._handle_result(
            StepCompleted(
                owner="map_owner",
                name="map_owner",
                result=_Map(items=[1], target="worker"),
                invocation=owner_invocation,
            )
        )
    ]
    second_events = [
        event
        async for event in runner._handle_result(
            StepCompleted(
                owner="map_owner",
                name="worker",
                result=None,
                invocation=worker_invocation,
            )
        )
    ]

    map_complete = next(
        event for event in first_events if event.type is EventType.MAP_COMPLETE
    )
    assert map_complete.invocation_id == "owner-inv"
    assert map_complete.owner_invocation_id == "owner-inv"
    assert map_complete.scope == ("root", "map")

    step_end_stages = [
        event.stage for event in second_events if event.type is EventType.STEP_END
    ]
    assert step_end_stages == ["worker", "map_owner"]
    worker_end = next(
        event
        for event in second_events
        if event.type is EventType.STEP_END and event.stage == "worker"
    )
    owner_end = next(
        event
        for event in second_events
        if event.type is EventType.STEP_END and event.stage == "map_owner"
    )
    assert worker_end.invocation_id == "worker-inv"
    assert owner_end.invocation_id == "owner-inv"
    assert barrier_calls == ["map_owner"]
    assert runner._pending_owner_invocations.get("map_owner", []) == []
    assert len(published) >= len(first_events) + len(second_events)


@pytest.mark.asyncio
async def test_handle_result_already_terminal_suppresses_duplicate_owner_end() -> None:
    runner = build_runner(_single_step_config())
    barrier_calls: list[str] = []

    runner._results.process_step_result = _no_step_events  # type: ignore[method-assign]
    runner._scheduler.on_step_completed = lambda owner, name: []  # type: ignore[method-assign,assignment]
    runner._barriers.handle_completion = barrier_calls.append  # type: ignore[method-assign,assignment]
    runner._publish = AsyncMock(side_effect=lambda event: event)

    runner._tracker.logical_active["owner"] = 1
    events = [
        event
        async for event in runner._handle_result(
            StepCompleted(
                owner="owner",
                name="owner",
                result=None,
                invocation=InvocationContext("owner-inv"),
                already_terminal=True,
            )
        )
    ]

    assert events == []
    assert barrier_calls == ["owner"]


@pytest.mark.asyncio
async def test_handle_result_track_owner_false_skips_barrier_accounting() -> None:
    runner = build_runner(_single_step_config())
    barrier_calls: list[str] = []

    runner._results.process_step_result = _no_step_events  # type: ignore[method-assign]
    runner._scheduler.on_step_completed = lambda owner, name: []  # type: ignore[method-assign,assignment]
    runner._barriers.handle_completion = barrier_calls.append  # type: ignore[method-assign,assignment]
    runner._publish = AsyncMock(side_effect=lambda event: event)

    runner._tracker.logical_active["owner"] = 1
    events = [
        event
        async for event in runner._handle_result(
            StepCompleted(
                owner="owner",
                name="worker",
                result=None,
                track_owner=False,
                invocation=InvocationContext(
                    "worker-inv", owner_invocation_id="owner-inv"
                ),
            )
        )
    ]

    assert [event.stage for event in events if event.type is EventType.STEP_END] == [
        "worker"
    ]
    assert runner._tracker.logical_active["owner"] == 1
    assert barrier_calls == []
