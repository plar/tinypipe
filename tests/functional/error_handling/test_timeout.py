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
@pytest.mark.parametrize(
    ("num_steps", "step_sleep", "timeout", "expected_status"),
    [
        pytest.param(
            1,
            0.01,
            1.0,
            PipelineTerminalStatus.SUCCESS,
            id="single_step_within_timeout",
        ),
        pytest.param(
            3,
            0.01,
            1.0,
            PipelineTerminalStatus.SUCCESS,
            id="multiple_steps_within_timeout",
        ),
        pytest.param(
            2, 0.06, 0.1, PipelineTerminalStatus.TIMEOUT, id="total_exceeds_timeout"
        ),
    ],
)
async def test_pipeline_timeout_behavior(
    num_steps: int,
    step_sleep: float,
    timeout: float,
    expected_status: PipelineTerminalStatus,
) -> None:
    """Test timeout applies to entire pipeline duration, not per-step."""
    pipe: Pipe[Any, Any] = Pipe()

    # Register chained steps dynamically
    for i in range(num_steps):
        name = f"step{i}"
        next_name = f"step{i + 1}" if i < num_steps - 1 else None

        @pipe.step(name, to=next_name)
        async def step_fn(state: Any, _sleep: float = step_sleep) -> None:
            await asyncio.sleep(_sleep)

    events = [e async for e in pipe.run(None, timeout=timeout)]
    finish = next(e for e in events if e.type == EventType.FINISH)
    assert isinstance(finish.payload, PipelineEndData)
    assert finish.payload.status == expected_status

    timeout_events = [e for e in events if e.type == EventType.TIMEOUT]
    if expected_status == PipelineTerminalStatus.TIMEOUT:
        assert len(timeout_events) > 0
    else:
        assert len(timeout_events) == 0


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
