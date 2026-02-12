"""Functional tests for pipeline timeout behavior."""

import asyncio
import pytest
from typing import Any

from justpipe import Pipe, EventType
from justpipe.types import PipelineTerminalStatus, PipelineEndData


@pytest.mark.asyncio
async def test_pipeline_timeout_none_is_unlimited() -> None:
    """Test that timeout=None allows unlimited execution time."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def fast_step(state: Any) -> None:
        await asyncio.sleep(0.01)

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
