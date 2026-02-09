"""Functional runtime contracts not covered by event-ordering canonicals."""

from collections.abc import AsyncGenerator
from typing import Any

import asyncio
import pytest

from justpipe import DefinitionError, EventType, Pipe
from justpipe.types import (
    FailureKind,
    FailureReason,
    PipelineEndData,
    PipelineTerminalStatus,
)


async def process_data(data: str) -> str:
    return data.upper()


@pytest.mark.asyncio
async def test_streaming_execution(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    tokens: list[Any] = []

    @pipe.step("streamer")
    async def streamer() -> AsyncGenerator[str, None]:
        yield "a"
        yield "b"

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            tokens.append(event.payload)
    assert tokens == ["a", "b"]


@pytest.mark.asyncio
async def test_step_not_found(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to="non_existent")
    async def start() -> None:
        pass

    with pytest.raises(DefinitionError, match="targets unknown step 'non_existent'"):
        async for _ in pipe.run(state):
            pass


@pytest.mark.asyncio
async def test_step_timeout_execution() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    release = asyncio.Event()

    @pipe.step("slow", timeout=0.1)
    async def slow() -> None:
        await release.wait()

    events: list[Any] = []
    async for ev in pipe.run(None):
        if ev.type == EventType.STEP_ERROR:
            events.append(ev)

    assert len(events) == 1
    assert "timed out" in str(events[0].payload)


@pytest.mark.asyncio
async def test_empty_pipeline() -> None:
    """Empty pipeline should yield ERROR and FINISH, not crash."""
    pipe: Pipe[Any, Any] = Pipe()
    events: list[Any] = [e async for e in pipe.run({})]

    assert len(events) >= 2
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert len(error_events) == 1
    assert "No steps registered" in error_events[0].payload
    assert events[-1].type == EventType.FINISH
    finish = events[-1]
    assert isinstance(finish.payload, PipelineEndData)
    assert finish.payload.status is PipelineTerminalStatus.FAILED
    assert finish.payload.failure_kind is FailureKind.VALIDATION
    assert finish.payload.reason == FailureReason.NO_STEPS.value


@pytest.mark.asyncio
async def test_concurrent_token_streaming() -> None:
    """Parallel steps should both have their tokens collected."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to=["a", "b"])
    async def start(s: Any) -> None:
        _ = s

    @pipe.step("a")
    async def step_a(s: Any) -> Any:
        _ = s
        yield "token_from_a"

    @pipe.step("b")
    async def step_b(s: Any) -> Any:
        _ = s
        yield "token_from_b"

    events = [e async for e in pipe.run({})]

    token_events = [e for e in events if e.type == EventType.TOKEN]
    token_data = {e.payload for e in token_events}

    assert "token_from_a" in token_data
    assert "token_from_b" in token_data


@pytest.mark.asyncio
async def test_context_none_handling() -> None:
    """Steps and hooks should handle context=None gracefully."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.on_startup
    async def startup(ctx: Any) -> None:
        # ctx is None, should not crash
        _ = ctx

    @pipe.on_shutdown
    async def shutdown(ctx: Any) -> None:
        # ctx is None, should not crash
        _ = ctx

    @pipe.step
    async def step_with_ctx(s: Any, ctx: Any) -> None:
        _ = s
        # ctx is None
        assert ctx is None

    events = [e async for e in pipe.run({}, context=None)]

    assert events[-1].type == EventType.FINISH
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert len(error_events) == 0


@pytest.mark.asyncio
async def test_etl_pipeline_simulation() -> None:
    """Simulate a simple ETL pipeline."""

    class AppState:
        def __init__(self) -> None:
            self.raw_data: list[str] = []
            self.processed_data: list[str] = []
            self.db_committed = False

    app = AppState()
    pipe: Pipe[AppState, Any] = Pipe()

    @pipe.step("extract", to="transform")
    async def extract(state: AppState) -> None:
        state.raw_data = ["a", "b", "c"]

    @pipe.step("transform", to="load")
    async def transform(state: AppState) -> None:
        for item in state.raw_data:
            processed = await process_data(item)
            state.processed_data.append(processed)

    @pipe.step("load")
    async def load(state: AppState) -> None:
        state.db_committed = True

    events = [event async for event in pipe.run(app)]

    assert app.db_committed
    assert app.processed_data == ["A", "B", "C"]

    stages = [e.stage for e in events if e.type == EventType.STEP_END]
    assert stages == ["extract", "transform", "load"]


@pytest.mark.asyncio
async def test_subpipe_event_origin_run_lineage_is_preserved() -> None:
    """Child events keep a stable origin_run_id when forwarded to parent stream."""
    sub_pipe: Pipe[dict[str, Any], None] = Pipe()

    @sub_pipe.step()
    async def child_step(state: dict[str, Any]) -> None:
        state["child_ran"] = True

    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.sub(pipeline=sub_pipe)
    async def run_child(state: dict[str, Any]) -> dict[str, Any]:
        return state

    state: dict[str, Any] = {}
    events = [event async for event in pipe.run(state)]

    assert state.get("child_ran") is True

    parent_run_id = events[0].run_id
    assert parent_run_id is not None

    child_step_events = [
        event
        for event in events
        if event.stage == "run_child:child_step"
        and event.type in (EventType.STEP_START, EventType.STEP_END)
    ]
    assert len(child_step_events) == 2

    child_origin_ids = {event.origin_run_id for event in child_step_events}
    assert len(child_origin_ids) == 1
    child_origin_id = next(iter(child_origin_ids))
    assert child_origin_id is not None
    assert child_origin_id != parent_run_id

    assert {event.run_id for event in child_step_events} == {parent_run_id}
