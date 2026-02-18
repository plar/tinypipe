"""Functional tests for pipeline cancellation."""

import asyncio
import pytest
from typing import Any

from justpipe import Pipe, EventType
from justpipe.types import (
    CancellationToken,
    FailureKind,
    FailureReason,
    PipelineTerminalStatus,
    PipelineEndData,
)


@pytest.mark.asyncio
async def test_cancellation_token_injection() -> None:
    """Test that cancellation token is injected into steps."""
    cancel = CancellationToken()
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)
    token_received: CancellationToken | None = None

    @pipe.step()
    async def check_token(state: Any, cancel: CancellationToken) -> None:
        nonlocal token_received
        token_received = cancel

    _ = [e async for e in pipe.run(None)]

    assert token_received is cancel


@pytest.mark.asyncio
async def test_pipeline_emits_cancelled_event_and_terminal_status() -> None:
    """Cancellation via token checkpoint should emit CANCELLED and terminal CANCELLED."""
    cancel = CancellationToken()
    cancel.cancel("user_cancelled")
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)

    @pipe.step()
    async def should_cancel(state: Any, token: CancellationToken) -> None:
        await token.checkpoint()

    events = [e async for e in pipe.run(None)]
    cancelled_events = [e for e in events if e.type == EventType.CANCELLED]
    finish = [e for e in events if e.type == EventType.FINISH][-1]

    assert len(cancelled_events) == 1
    assert "user_cancelled" in str(cancelled_events[0].payload)
    assert isinstance(finish.payload, PipelineEndData)
    assert finish.payload.status == PipelineTerminalStatus.CANCELLED
    assert finish.payload.reason == FailureReason.CANCELLED.value
    assert finish.payload.failure_kind == FailureKind.NONE


@pytest.mark.asyncio
async def test_cancellation_in_map_workers() -> None:
    """Test that cancellation works in map workers via checkpoint."""
    cancel = CancellationToken()
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)
    processed: list[int] = []
    gate = asyncio.Event()

    @pipe.map(each="worker", max_concurrency=1)
    async def create_workers(state: Any) -> range:
        return range(10)

    @pipe.step()
    async def worker(state: Any, cancel: CancellationToken, item: int) -> None:
        await cancel.checkpoint()
        processed.append(item)
        if item == 2:
            gate.set()
            # Yield control so the cancel task fires before next worker
            await asyncio.sleep(0)

    async def cancel_after_gate() -> None:
        await gate.wait()
        cancel.cancel("Test cancellation")

    task = asyncio.create_task(cancel_after_gate())

    events: list[Any] = []
    async for event in pipe.run(None):
        events.append(event)

    await task

    # Workers 0, 1, 2 processed before cancellation; remaining hit checkpoint
    assert 0 in processed and 1 in processed and 2 in processed
    assert len(processed) < 10

    # Pipeline must report cancellation
    cancelled_or_error = [
        e
        for e in events
        if e.type in (EventType.CANCELLED, EventType.STEP_ERROR)
        and "cancel" in str(e.payload).lower()
    ]
    assert len(cancelled_or_error) >= 1


@pytest.mark.asyncio
async def test_cancelled_step_does_not_emit_step_error() -> None:
    """A cancelled step should only emit CANCELLED, never STEP_ERROR."""
    cancel = CancellationToken()
    cancel.cancel("user_cancelled")
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)

    @pipe.step()
    async def should_cancel(state: Any, token: CancellationToken) -> None:
        await token.checkpoint()

    events = [e async for e in pipe.run(None)]

    cancelled_events = [e for e in events if e.type == EventType.CANCELLED]
    step_errors = [
        e
        for e in events
        if e.type == EventType.STEP_ERROR and e.stage == "should_cancel"
    ]

    assert len(cancelled_events) == 1
    assert len(step_errors) == 0, (
        f"STEP_ERROR should not be emitted for a cancelled step, got: {step_errors}"
    )


@pytest.mark.asyncio
async def test_cancellation_without_checkpoint() -> None:
    """Test that cancellation without checkpoints doesn't stop execution."""
    cancel = CancellationToken()
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)
    completed = False

    @pipe.step()
    async def no_checkpoint(state: Any) -> None:
        # Doesn't call cancel.checkpoint()
        await asyncio.sleep(0.01)
        nonlocal completed
        completed = True

    # Cancel immediately
    cancel.cancel("Cancelled")

    # Pipeline should complete since step doesn't check cancellation
    events = [e async for e in pipe.run(None)]

    assert completed is True
    assert any(e.type == EventType.FINISH for e in events)
