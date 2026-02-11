"""Functional barrier-timeout tests with deterministic worker coordination."""

import asyncio
from typing import Any

import pytest

from justpipe import Pipe, EventType


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("with_downstream",),
    [(False,), (True,)],
    ids=["terminal_join", "join_to_end"],
)
async def test_barrier_timeout_success_paths(with_downstream: bool) -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(allow_multi_root=True)
    # Deterministic gating avoids scheduler-dependent sleep timing.
    release_workers = asyncio.Event()

    @pipe.step(to="join")
    async def step_a(state: dict[str, Any]) -> None:
        _ = state
        release_workers.set()

    @pipe.step(to="join")
    async def step_b(state: dict[str, Any]) -> None:
        _ = state
        await release_workers.wait()

    if with_downstream:

        @pipe.step("join", barrier_timeout=0.2, to="end")
        async def join(state: dict[str, Any]) -> None:
            state["join"] = state.get("join", 0) + 1

        @pipe.step()
        async def end(state: dict[str, Any]) -> None:
            state["end"] = True

    else:

        @pipe.step("join", barrier_timeout=0.2)
        async def join(state: dict[str, Any]) -> None:
            state["join"] = state.get("join", 0) + 1

    state: dict[str, Any] = {}
    events = [ev async for ev in pipe.run(state, timeout=1.0)]

    assert state.get("join") == 1
    if with_downstream:
        assert state.get("end") is True
    else:
        assert "end" not in state

    assert any(ev.type == EventType.STEP_END and ev.stage == "join" for ev in events)
    assert not any(
        ev.type == EventType.STEP_ERROR and ev.stage == "join" for ev in events
    )


@pytest.mark.asyncio
async def test_barrier_timeout_failure() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(allow_multi_root=True)
    # Keep one worker blocked until the join step times out.
    worker_started = asyncio.Event()
    release_worker = asyncio.Event()

    @pipe.step(to="combine")
    async def step_a(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to="combine")
    async def step_b(state: dict[str, Any]) -> None:
        _ = state
        worker_started.set()
        await release_worker.wait()

    @pipe.step(barrier_timeout=0.05)
    async def combine(state: dict[str, Any]) -> None:
        state["done"] = True

    state: dict[str, Any] = {}
    errors: list[Any] = []
    async for ev in pipe.run(state, timeout=1.0):
        if ev.type == EventType.STEP_ERROR:
            errors.append(ev)
            if ev.stage == "combine":
                release_worker.set()

    assert worker_started.is_set()
    assert len(errors) == 1
    assert "Barrier timeout" in str(errors[0].payload)
    assert state.get("done") is None


@pytest.mark.asyncio
async def test_barrier_timeout_does_not_skip_other_targets() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(allow_multi_root=True)
    # Block only the barrier path; sibling targets should still execute.
    release_worker = asyncio.Event()

    @pipe.step(to="combine")
    async def step_a(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to=["combine", "after_b"])
    async def step_b(state: dict[str, Any]) -> None:
        _ = state
        await release_worker.wait()

    @pipe.step(barrier_timeout=0.05)
    async def combine(state: dict[str, Any]) -> None:
        state["combine_done"] = True

    @pipe.step()
    async def after_b(state: dict[str, Any]) -> None:
        state["after_b"] = True

    state: dict[str, Any] = {}
    async for ev in pipe.run(state, timeout=1.0):
        if ev.type == EventType.STEP_ERROR and ev.stage == "combine":
            release_worker.set()

    assert state.get("after_b") is True
