"""Golden event-order and invariant tests.

These tests lock down exact event sequences before any runner decomposition.
They serve as a safety net: if any refactoring breaks observable behavior,
these tests will catch it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from justpipe import EventType, Pipe, Suspend
from justpipe.types import (
    CancellationToken,
    PipelineEndData,
    PipelineTerminalStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_events(
    pipe: Pipe[Any, Any], state: Any = None, **kwargs: Any
) -> list[Any]:
    return [e async for e in pipe.run(state, **kwargs)]


def _types(events: list[Any]) -> list[EventType]:
    return [e.type for e in events]


def _stages(events: list[Any], event_type: EventType) -> list[str]:
    return [e.stage for e in events if e.type == event_type]


def _finish(events: list[Any]) -> Any:
    finishes = [e for e in events if e.type == EventType.FINISH]
    assert len(finishes) == 1, f"Expected exactly 1 FINISH, got {len(finishes)}"
    return finishes[0]


# ---------------------------------------------------------------------------
# Invariant helpers (applied to every scenario)
# ---------------------------------------------------------------------------


def assert_invariants(events: list[Any]) -> None:
    """Assert universal invariants that must hold for every pipeline run."""
    # 1. Exactly one FINISH event per run
    finish_events = [e for e in events if e.type == EventType.FINISH]
    assert len(finish_events) == 1, (
        f"Expected exactly 1 FINISH event, got {len(finish_events)}: "
        f"{[e.stage for e in finish_events]}"
    )

    # 2. No events emitted after FINISH
    finish_idx = next(i for i, e in enumerate(events) if e.type == EventType.FINISH)
    after_finish = events[finish_idx + 1 :]
    assert after_finish == [], (
        f"Events after FINISH: {[(e.type, e.stage) for e in after_finish]}"
    )

    # 3. FINISH always carries PipelineEndData with a valid PipelineTerminalStatus
    finish = finish_events[0]
    assert isinstance(finish.payload, PipelineEndData), (
        f"FINISH.payload is {type(finish.payload).__name__}, expected PipelineEndData"
    )
    assert isinstance(finish.payload.status, PipelineTerminalStatus), (
        f"FINISH.payload.status is {type(finish.payload.status).__name__}, "
        f"expected PipelineTerminalStatus"
    )

    # 4. Every STEP_START has a matching STEP_END or STEP_ERROR (no orphans)
    #    Exception: map workers get STEP_START but their owner gets STEP_END,
    #    and timeout/cancel may abort in-flight steps.
    terminal_status = finish_events[0].payload.status
    is_aborted = terminal_status in {
        PipelineTerminalStatus.TIMEOUT,
        PipelineTerminalStatus.CANCELLED,
        PipelineTerminalStatus.CLIENT_CLOSED,
    }
    # Collect map worker step names (they don't get individual STEP_END)
    map_worker_stages = {
        e.payload["target"]
        for e in events
        if e.type == EventType.MAP_WORKER and isinstance(e.payload, dict)
    }

    started = []
    ended = set()
    errored = set()
    for e in events:
        if e.type == EventType.STEP_START:
            started.append(e.stage)
        elif e.type == EventType.STEP_END:
            ended.add(e.stage)
        elif e.type == EventType.STEP_ERROR:
            errored.add(e.stage)

    if not is_aborted:
        for step in started:
            if step in map_worker_stages:
                continue
            assert step in ended or step in errored, (
                f"STEP_START('{step}') has no matching STEP_END or STEP_ERROR. "
                f"Ended: {ended}, Errored: {errored}"
            )


# ===========================================================================
# Scenario 1: Linear pipeline
# ===========================================================================


@pytest.mark.asyncio
async def test_linear_pipeline_event_order() -> None:
    """Linear a -> b produces START, STEP_START(a), STEP_END(a), STEP_START(b), STEP_END(b), FINISH(success)."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to="b")
    async def a() -> None:
        pass

    @pipe.step()
    async def b() -> None:
        pass

    events = await _collect_events(pipe)

    expected_types = [
        EventType.START,
        EventType.STEP_START,
        EventType.STEP_END,
        EventType.STEP_START,
        EventType.STEP_END,
        EventType.FINISH,
    ]
    assert _types(events) == expected_types
    assert _stages(events, EventType.STEP_START) == ["a", "b"]
    assert _stages(events, EventType.STEP_END) == ["a", "b"]
    assert _finish(events).payload.status == PipelineTerminalStatus.SUCCESS
    assert_invariants(events)


# ===========================================================================
# Scenario 2: Parallel fan-out/fan-in (barrier)
# ===========================================================================


@pytest.mark.asyncio
async def test_parallel_fan_out_fan_in_event_order() -> None:
    """Root fans out to a and b (parallel), then joins at 'join'."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to=["branch_a", "branch_b"])
    async def root() -> None:
        pass

    @pipe.step(to="join")
    async def branch_a() -> None:
        pass

    @pipe.step(to="join")
    async def branch_b() -> None:
        pass

    @pipe.step()
    async def join() -> None:
        pass

    events = await _collect_events(pipe)

    types = _types(events)

    # START must come first
    assert types[0] == EventType.START

    # root executes first
    assert types[1] == EventType.STEP_START
    assert events[1].stage == "root"
    assert types[2] == EventType.STEP_END
    assert events[2].stage == "root"

    # branch_a and branch_b start in any order after root ends
    branch_starts = _stages(events, EventType.STEP_START)
    assert "root" in branch_starts
    root_idx = branch_starts.index("root")
    after_root = branch_starts[root_idx + 1 :]
    assert set(after_root[:2]) == {"branch_a", "branch_b"}

    # join starts after both branches end
    branch_ends = _stages(events, EventType.STEP_END)
    assert "join" in branch_ends
    join_end_idx = branch_ends.index("join")
    # Both branches end before join ends
    assert "branch_a" in branch_ends[:join_end_idx]
    assert "branch_b" in branch_ends[:join_end_idx]

    # join starts and ends
    assert "join" in _stages(events, EventType.STEP_START)
    assert "join" in _stages(events, EventType.STEP_END)

    # FINISH at end with success
    assert types[-1] == EventType.FINISH
    assert _finish(events).payload.status == PipelineTerminalStatus.SUCCESS
    assert_invariants(events)


# ===========================================================================
# Scenario 3: Map operation
# ===========================================================================


@pytest.mark.asyncio
async def test_map_operation_event_order() -> None:
    """Map step fans out to workers, then MAP_COMPLETE fires."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.map(each="worker")
    async def mapper() -> list[int]:
        return [1, 2, 3]

    @pipe.step()
    async def worker(item: int) -> None:
        pass

    events = await _collect_events(pipe)
    types = _types(events)

    # START comes first
    assert types[0] == EventType.START

    # mapper STEP_START
    assert EventType.STEP_START in types
    assert "mapper" in _stages(events, EventType.STEP_START)

    # MAP_START after mapper starts
    assert EventType.MAP_START in types
    map_start_idx = types.index(EventType.MAP_START)
    mapper_start_idx = next(
        i
        for i, e in enumerate(events)
        if e.type == EventType.STEP_START and e.stage == "mapper"
    )
    assert map_start_idx > mapper_start_idx

    # MAP_WORKER events present
    map_workers = [e for e in events if e.type == EventType.MAP_WORKER]
    assert len(map_workers) == 3

    # MAP_COMPLETE fires
    assert EventType.MAP_COMPLETE in types

    # FINISH at end with success
    assert types[-1] == EventType.FINISH
    assert _finish(events).payload.status == PipelineTerminalStatus.SUCCESS
    assert_invariants(events)


# ===========================================================================
# Scenario 4: Step error
# ===========================================================================


@pytest.mark.asyncio
async def test_step_error_event_order() -> None:
    """Step error: START, STEP_START(a), STEP_ERROR(a), FINISH(failed)."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def a() -> None:
        raise ValueError("boom")

    events = await _collect_events(pipe)
    types = _types(events)

    assert types[0] == EventType.START
    assert EventType.STEP_START in types
    assert "a" in _stages(events, EventType.STEP_START)
    assert EventType.STEP_ERROR in types
    assert "a" in _stages(events, EventType.STEP_ERROR)
    assert types[-1] == EventType.FINISH
    assert _finish(events).payload.status == PipelineTerminalStatus.FAILED
    assert_invariants(events)


# ===========================================================================
# Scenario 5: Timeout
# ===========================================================================


@pytest.mark.asyncio
async def test_timeout_event_order() -> None:
    """Timeout: START, STEP_START(slow), TIMEOUT, FINISH(timeout)."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def slow() -> None:
        await asyncio.sleep(10)

    events = await _collect_events(pipe, timeout=0.05)
    types = _types(events)

    assert types[0] == EventType.START
    assert EventType.STEP_START in types
    assert "slow" in _stages(events, EventType.STEP_START)
    assert EventType.TIMEOUT in types
    assert types[-1] == EventType.FINISH
    assert _finish(events).payload.status == PipelineTerminalStatus.TIMEOUT
    assert_invariants(events)


# ===========================================================================
# Scenario 6: Suspend
# ===========================================================================


@pytest.mark.asyncio
async def test_suspend_event_order() -> None:
    """Suspend: START, STEP_START(a), SUSPEND, STEP_END(a), FINISH(success)."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def a() -> Suspend:
        return Suspend(reason="pausing")

    events = await _collect_events(pipe)
    types = _types(events)

    assert types[0] == EventType.START
    assert EventType.STEP_START in types
    assert "a" in _stages(events, EventType.STEP_START)
    assert EventType.SUSPEND in types
    assert EventType.STEP_END in types
    assert "a" in _stages(events, EventType.STEP_END)
    assert types[-1] == EventType.FINISH

    # Suspend results in success terminal status
    assert _finish(events).payload.status == PipelineTerminalStatus.SUCCESS
    assert_invariants(events)


# ===========================================================================
# Scenario 7: Client close (GeneratorExit mid-stream)
# ===========================================================================


@pytest.mark.asyncio
async def test_client_close_event_order() -> None:
    """Client close mid-stream: partial events, then no FINISH visible."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def slow() -> None:
        await asyncio.sleep(10)

    stream = pipe.run(None)
    received: list[Any] = []

    # Consume START and STEP_START, then close
    ev = await stream.__anext__()
    received.append(ev)
    assert ev.type == EventType.START

    ev = await stream.__anext__()
    received.append(ev)
    assert ev.type == EventType.STEP_START

    # Close the stream mid-execution (GeneratorExit)
    await stream.aclose()

    # After aclose, no more events can be collected from this stream.
    # The FINISH event is emitted during shutdown but suppressed when closing.
    # We only assert we got the partial events before close.
    assert len(received) >= 2
    assert received[0].type == EventType.START
    assert received[1].type == EventType.STEP_START


# ===========================================================================
# Standalone invariant tests (apply broadly)
# ===========================================================================


@pytest.mark.asyncio
async def test_invariants_empty_pipeline() -> None:
    """Empty pipeline (no steps) still satisfies invariants."""
    pipe: Pipe[Any, Any] = Pipe()

    # An empty pipe emits a STEP_ERROR for "No steps registered" then FINISH
    events = await _collect_events(pipe)
    assert_invariants(events)
    assert _finish(events).payload.status == PipelineTerminalStatus.FAILED


@pytest.mark.asyncio
async def test_invariants_cancel_via_token() -> None:
    """Cancellation via token still satisfies invariants."""
    cancel = CancellationToken()
    cancel.cancel("test")
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)

    @pipe.step()
    async def do_work(cancel: CancellationToken) -> None:
        await cancel.checkpoint()

    events = await _collect_events(pipe)
    assert_invariants(events)
    assert _finish(events).payload.status == PipelineTerminalStatus.CANCELLED


@pytest.mark.asyncio
async def test_invariants_multi_step_chain() -> None:
    """Multi-step chain satisfies invariants."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to="b")
    async def a() -> None:
        pass

    @pipe.step(to="c")
    async def b() -> None:
        pass

    @pipe.step()
    async def c() -> None:
        pass

    events = await _collect_events(pipe)
    assert_invariants(events)
    assert _finish(events).payload.status == PipelineTerminalStatus.SUCCESS
    assert _stages(events, EventType.STEP_START) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_invariants_error_in_second_step() -> None:
    """Error in second step of a chain: first step has STEP_END, second has STEP_ERROR."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to="b")
    async def a() -> None:
        pass

    @pipe.step()
    async def b() -> None:
        raise RuntimeError("fail in b")

    events = await _collect_events(pipe)
    assert_invariants(events)
    assert _finish(events).payload.status == PipelineTerminalStatus.FAILED
    assert "a" in _stages(events, EventType.STEP_END)
    assert "b" in _stages(events, EventType.STEP_ERROR)
