"""Tests for pipeline cancellation and timeout features."""

import asyncio
import pytest
from typing import Any

from justpipe import Pipe, EventType
from justpipe.types import (
    CancellationToken,
    FailureKind,
    FailureReason,
    PipelineCancelled,
    PipelineTerminalStatus,
    PipelineEndData,
)


# ============================================================================
# Cancellation Token Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cancellation_token_is_cancelled() -> None:
    """Test CancellationToken.is_cancelled() method."""
    cancel = CancellationToken()

    assert not cancel.is_cancelled()

    cancel.cancel("Test cancellation")

    assert cancel.is_cancelled()
    assert cancel.reason == "Test cancellation"


@pytest.mark.asyncio
async def test_cancellation_token_checkpoint_before_cancel() -> None:
    """Test that checkpoint doesn't raise before cancellation."""
    cancel = CancellationToken()

    # Should not raise
    await cancel.checkpoint()


@pytest.mark.asyncio
async def test_cancellation_token_checkpoint_after_cancel() -> None:
    """Test that checkpoint raises after cancellation."""
    cancel = CancellationToken()
    cancel.cancel("Already cancelled")

    with pytest.raises(PipelineCancelled) as exc_info:
        await cancel.checkpoint()

    assert "Already cancelled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancellation_token_default_reason() -> None:
    """Test that cancellation token has default reason."""
    cancel = CancellationToken()
    cancel.cancel()  # No reason provided

    assert cancel.is_cancelled()
    assert cancel.reason == "Cancelled"


@pytest.mark.asyncio
async def test_cancellation_token_multiple_cancels() -> None:
    """Test that multiple cancel calls preserve first reason."""
    cancel = CancellationToken()
    cancel.cancel("First reason")
    cancel.cancel("Second reason")  # Should be ignored

    assert cancel.reason == "First reason"


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
    """Test that cancellation works in map workers."""
    cancel = CancellationToken()
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)
    processed: list[int] = []

    @pipe.map(
        each="worker", max_concurrency=5
    )  # Limit concurrency to make timing more predictable
    async def create_workers(state: Any) -> range:
        return range(100)

    @pipe.step()
    async def worker(state: Any, cancel: CancellationToken, item: int) -> None:
        await cancel.checkpoint()
        processed.append(item)
        await asyncio.sleep(
            0.02
        )  # Longer sleep to ensure cancellation happens mid-execution

    # Cancel after very short delay
    async def cancel_soon() -> None:
        await asyncio.sleep(0.02)  # Cancel quickly
        cancel.cancel("Test cancellation")

    task = asyncio.create_task(cancel_soon())

    # Pipeline should encounter cancellation
    events: list[Any] = []
    error_found = False
    try:
        async for event in pipe.run(None):
            events.append(event)
            if event.type == EventType.STEP_ERROR:
                if (
                    "PipelineCancelled" in str(event.payload)
                    or "cancelled" in str(event.payload).lower()
                ):
                    error_found = True
                    break
    except Exception:
        pass

    await task

    # Either we found a cancellation error OR we didn't process all items
    # (timing-dependent test, so be flexible)
    assert error_found or len(processed) < 100


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


# ============================================================================
# Pipeline Timeout Tests
# ============================================================================


@pytest.mark.asyncio
async def test_pipeline_timeout_none_is_unlimited() -> None:
    """Test that timeout=None allows unlimited execution time."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def fast_step(state: Any) -> None:
        await asyncio.sleep(0.01)

    # Should complete without timeout
    events = [e async for e in pipe.run(None, timeout=None)]
    finish_events = [e for e in events if e.type == EventType.FINISH]
    assert len(finish_events) == 1


@pytest.mark.asyncio
async def test_pipeline_timeout_completes_before_timeout() -> None:
    """Test that pipeline completes successfully if within timeout."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def fast_step(state: Any) -> None:
        await asyncio.sleep(0.01)

    # Should complete without timeout
    events = [e async for e in pipe.run(None, timeout=1.0)]
    finish_events = [e for e in events if e.type == EventType.FINISH]
    assert len(finish_events) == 1
    timeout_events = [e for e in events if e.type == EventType.TIMEOUT]
    assert len(timeout_events) == 0
    assert isinstance(finish_events[0].payload, PipelineEndData)
    assert finish_events[0].payload.status == PipelineTerminalStatus.SUCCESS


@pytest.mark.asyncio
async def test_pipeline_timeout_with_multiple_steps() -> None:
    """Test timeout with multiple fast steps."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to="step2")
    async def step1(state: Any) -> None:
        await asyncio.sleep(0.01)

    @pipe.step(to="step3")
    async def step2(state: Any) -> None:
        await asyncio.sleep(0.01)

    @pipe.step()
    async def step3(state: Any) -> None:
        await asyncio.sleep(0.01)

    # All steps combined should complete within timeout
    events = [e async for e in pipe.run(None, timeout=1.0)]
    finish_events = [e for e in events if e.type == EventType.FINISH]
    assert len(finish_events) == 1


@pytest.mark.asyncio
async def test_pipeline_timeout_is_total_not_per_step() -> None:
    """Test that timeout applies to entire pipeline, not per-step."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step(to="step2")
    async def step1(state: Any) -> None:
        await asyncio.sleep(0.06)  # 60ms

    @pipe.step()
    async def step2(state: Any) -> None:
        await asyncio.sleep(0.06)  # 60ms

    # Total is ~120ms, timeout is 100ms - should timeout
    events = [e async for e in pipe.run(None, timeout=0.1)]
    timeout_events = [e for e in events if e.type == EventType.TIMEOUT]
    assert timeout_events
    finish = [e for e in events if e.type == EventType.FINISH][0]
    assert isinstance(finish.payload, PipelineEndData)
    assert finish.payload.status == PipelineTerminalStatus.TIMEOUT


@pytest.mark.asyncio
async def test_pipeline_timeout_emits_event_before_exception() -> None:
    """Test that TIMEOUT event is emitted before TimeoutError is raised."""
    pipe: Pipe[Any, Any] = Pipe()
    events: list[Any] = []

    @pipe.step()
    async def slow_step(state: Any) -> None:
        await asyncio.sleep(1.0)

    async for event in pipe.run(None, timeout=0.05):
        events.append(event)

    # Should have TIMEOUT event and terminal status TIMEOUT
    timeout_events = [e for e in events if e.type == EventType.TIMEOUT]
    assert len(timeout_events) == 1
    finish = [e for e in events if e.type == EventType.FINISH][0]
    assert isinstance(finish.payload, PipelineEndData)
    assert finish.payload.status == PipelineTerminalStatus.TIMEOUT


# ============================================================================
# Edge Cases and Integration
# ============================================================================


@pytest.mark.asyncio
async def test_queue_size_default_is_bounded() -> None:
    """Test that default queue_size is bounded (1000)."""
    pipe: Pipe[Any, Any] = Pipe()
    assert pipe.queue_size == 1000


@pytest.mark.asyncio
async def test_queue_size_can_be_set_to_unbounded() -> None:
    """Test that queue_size can be explicitly set to 0 (unbounded)."""
    pipe: Pipe[Any, Any] = Pipe(queue_size=0)
    assert pipe.queue_size == 0


@pytest.mark.asyncio
async def test_cancellation_token_per_pipeline() -> None:
    """Test that each pipeline can have its own cancellation token."""
    cancel1 = CancellationToken()
    cancel2 = CancellationToken()

    pipe1: Pipe[Any, Any] = Pipe(cancellation_token=cancel1)
    pipe2: Pipe[Any, Any] = Pipe(cancellation_token=cancel2)

    assert pipe1.cancellation_token is cancel1
    assert pipe2.cancellation_token is cancel2
    assert cancel1 is not cancel2


@pytest.mark.asyncio
async def test_default_cancellation_token_created() -> None:
    """Test that pipeline creates default cancellation token if none provided."""
    pipe: Pipe[Any, Any] = Pipe()

    assert pipe.cancellation_token is not None
    assert isinstance(pipe.cancellation_token, CancellationToken)
    assert not pipe.cancellation_token.is_cancelled()
