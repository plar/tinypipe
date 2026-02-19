"""Fuzzing tests for pipeline robustness using property-based testing.

These tests use hypothesis to generate random inputs and configurations
to discover edge cases, race conditions, and unexpected behaviors.
"""

import asyncio
import pytest
from typing import Any
from hypothesis import given, strategies as st, settings, HealthCheck
from dataclasses import dataclass

from justpipe import Pipe, EventType
from justpipe.types import CancellationToken

pytestmark = pytest.mark.slow


# ============================================================================
# Strategy Definitions
# ============================================================================

# State strategies - various types and structures
simple_states = st.one_of(
    st.none(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
    st.booleans(),
)

nested_states = st.recursive(
    simple_states,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=10), children, max_size=5),
    ),
    max_leaves=10,
)


@dataclass
class RandomState:
    """Dataclass for random state testing."""

    value: Any
    counter: int = 0


state_objects = st.builds(
    RandomState,
    value=nested_states,
    counter=st.integers(min_value=0, max_value=1000),
)

# Configuration strategies
queue_sizes = st.integers(min_value=0, max_value=10000)
concurrency_limits = st.one_of(st.none(), st.integers(min_value=1, max_value=100))
timeout_values = st.one_of(
    st.none(), st.floats(min_value=0.001, max_value=10.0, allow_nan=False)
)
map_item_counts = st.integers(min_value=0, max_value=100)


# ============================================================================
# State Handling Fuzz Tests
# ============================================================================


@given(state=nested_states)
@settings(max_examples=50, deadline=1000)
async def test_fuzz_pipeline_with_random_state(state: Any) -> None:
    """Test that pipeline handles arbitrary state objects without crashing."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[bool] = []

    @pipe.step()
    async def process_state(s: Any) -> None:
        executed.append(True)
        # Just verify we can access the state without crashing
        _ = str(s)

    events: list[Any] = []
    try:
        async for event in pipe.run(state):
            events.append(event)
    except Exception as e:
        # Should not crash on any state type
        pytest.fail(f"Pipeline crashed with state {type(state)}: {e}")

    assert executed, "Step should have executed"
    assert any(e.type == EventType.FINISH for e in events), "Should finish successfully"


@given(state_obj=state_objects)
@settings(max_examples=50, deadline=1000)
async def test_fuzz_pipeline_with_dataclass_state(state_obj: RandomState) -> None:
    """Test pipeline with random dataclass state."""
    pipe: Pipe[Any, Any] = Pipe()
    results: list[int] = []

    @pipe.step()
    async def process(state: RandomState) -> None:
        results.append(state.counter)

    _ = [e async for e in pipe.run(state_obj)]
    assert len(results) == 1
    assert results[0] == state_obj.counter


# ============================================================================
# Queue Size Fuzz Tests
# ============================================================================


@given(queue_size=queue_sizes)
@settings(max_examples=30, deadline=2000)
async def test_fuzz_queue_size_configuration(queue_size: int) -> None:
    """Test pipeline with random queue sizes."""
    pipe: Pipe[Any, Any] = Pipe(queue_size=queue_size)

    @pipe.step()
    async def simple_step(state: Any) -> None:
        await asyncio.sleep(0.001)

    events = [e async for e in pipe.run(None)]
    assert any(e.type == EventType.FINISH for e in events)


# ============================================================================
# Concurrency Fuzz Tests
# ============================================================================


@given(
    max_concurrency=concurrency_limits,
    item_count=map_item_counts,
)
@settings(
    max_examples=30,
    deadline=3000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
async def test_fuzz_map_concurrency(
    max_concurrency: int | None, item_count: int
) -> None:
    """Test map operations with random concurrency limits and item counts."""
    pipe: Pipe[Any, Any] = Pipe()
    processed: list[int] = []

    @pipe.map(each="worker", max_concurrency=max_concurrency)
    async def create_items(state: Any) -> range:
        return range(item_count)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        processed.append(item)
        await asyncio.sleep(0.001)

    events = [e async for e in pipe.run(None)]

    # Should process all items
    assert len(processed) == item_count
    assert sorted(processed) == list(range(item_count))

    # Should have correct number of worker events
    worker_events = [e for e in events if e.type == EventType.MAP_WORKER]
    assert len(worker_events) == item_count


# ============================================================================
# Timeout Fuzz Tests
# ============================================================================


@given(timeout=timeout_values)
@settings(max_examples=20, deadline=15000)
async def test_fuzz_pipeline_timeout(timeout: float | None) -> None:
    """Test pipeline with random timeout values."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def fast_step(state: Any) -> None:
        # Always complete quickly
        await asyncio.sleep(0.001)

    if timeout is None or timeout > 0.1:
        # Should complete successfully
        events = [e async for e in pipe.run(None, timeout=timeout)]
        assert any(e.type == EventType.FINISH for e in events)
    else:
        # Might timeout with very small values, but shouldn't crash
        try:
            events = [e async for e in pipe.run(None, timeout=timeout)]
            # If it completes, it should have a terminal event
            assert any(e.type in (EventType.FINISH, EventType.TIMEOUT) for e in events)
        except TimeoutError:
            pass  # Expected for very small timeouts


# ============================================================================
# Cancellation Timing Fuzz Tests
# ============================================================================


@given(
    cancel_delay=st.floats(min_value=0.0, max_value=0.05, allow_nan=False),
    step_count=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20, deadline=2000)
async def test_fuzz_cancellation_timing(cancel_delay: float, step_count: int) -> None:
    """Test cancellation at random points during execution."""
    cancel = CancellationToken()
    pipe: Pipe[Any, Any] = Pipe(cancellation_token=cancel)
    executed: list[int] = []

    # Build chain of steps
    for i in range(step_count):
        if i == 0:

            @pipe.step(
                name=f"step_{i}", to=f"step_{i + 1}" if i < step_count - 1 else None
            )
            async def first_step(state: Any, cancel: CancellationToken) -> None:
                await cancel.checkpoint()
                executed.append(0)
                await asyncio.sleep(0.01)

        else:
            # Need to capture i in closure
            def make_step(idx: int) -> Any:
                @pipe.step(
                    name=f"step_{idx}",
                    to=f"step_{idx + 1}" if idx < step_count - 1 else None,
                )
                async def step(state: Any, cancel: CancellationToken) -> None:
                    await cancel.checkpoint()
                    executed.append(idx)
                    await asyncio.sleep(0.01)

                return step

            make_step(i)

    # Cancel after delay
    async def cancel_after_delay() -> None:
        await asyncio.sleep(cancel_delay)
        cancel.cancel("Fuzz test cancellation")

    task = asyncio.create_task(cancel_after_delay())

    # Run pipeline
    events: list[Any] = []
    cancelled = False
    completed = False
    try:
        async for event in pipe.run(None):
            events.append(event)
            if event.type == EventType.STEP_ERROR:
                if "cancel" in str(event.payload).lower():
                    cancelled = True
                    break
        completed = True
    except (asyncio.CancelledError, TimeoutError):
        pass  # Expected cancellation-related exceptions

    await task

    # Either cancelled or completed (timing dependent)
    assert cancelled or completed, "Pipeline must either cancel or complete"
    assert cancelled or completed


# ============================================================================
# Edge Case Combinations
# ============================================================================


@given(
    queue_size=st.integers(min_value=10, max_value=1000),
    concurrency=st.integers(min_value=1, max_value=10),
    item_count=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=10, deadline=5000)
async def test_fuzz_combined_edge_cases(
    queue_size: int, concurrency: int, item_count: int
) -> None:
    """Test combinations of edge cases together."""
    pipe: Pipe[Any, Any] = Pipe(queue_size=queue_size)
    processed: list[int] = []

    @pipe.map(each="worker", max_concurrency=concurrency)
    async def create_items(state: Any) -> range:
        return range(item_count)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        processed.append(item)
        # Don't sleep to avoid slowness
        pass

    events = [e async for e in pipe.run(None)]

    assert len(processed) == item_count
    assert any(e.type == EventType.FINISH for e in events)


# ============================================================================
# String/Name Injection Fuzz Tests
# ============================================================================


@given(
    step_name=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65
        ),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=20, deadline=1000)
async def test_fuzz_step_names(step_name: str) -> None:
    """Test pipeline with random step names."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[bool] = []

    @pipe.step(name=step_name)
    async def dynamic_step(state: Any) -> None:
        executed.append(True)

    events = [e async for e in pipe.run(None, start=step_name)]
    assert executed
    assert any(e.type == EventType.FINISH for e in events)


# ============================================================================
# Nested Structure Fuzz Tests
# ============================================================================


@given(depth=st.integers(min_value=1, max_value=5))
@settings(max_examples=10, deadline=2000)
async def test_fuzz_pipeline_depth(depth: int) -> None:
    """Test pipeline with random nesting depth."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[int] = []

    # Build chain
    for i in range(depth):
        if i == 0:

            @pipe.step(name=f"step_{i}", to=f"step_{i + 1}" if i < depth - 1 else None)
            async def first_step(state: Any) -> None:
                executed.append(0)

        else:

            def make_step(idx: int) -> Any:
                @pipe.step(
                    name=f"step_{idx}",
                    to=f"step_{idx + 1}" if idx < depth - 1 else None,
                )
                async def step(state: Any) -> None:
                    executed.append(idx)

                return step

            make_step(i)

    events = [e async for e in pipe.run(None)]
    assert len(executed) == depth
    assert any(e.type == EventType.FINISH for e in events)


# ============================================================================
# Error Injection Fuzz Tests
# ============================================================================


@given(raises_error=st.booleans())
@settings(max_examples=10, deadline=1000)
async def test_fuzz_error_handling(raises_error: bool) -> None:
    """Test that pipeline handles errors gracefully."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[bool] = []

    @pipe.step()
    async def maybe_error(state: Any) -> None:
        if raises_error:
            raise ValueError("Intentional fuzz error")
        executed.append(True)

    events = [e async for e in pipe.run(None)]

    if raises_error:
        # Should have error event
        error_events = [e for e in events if e.type == EventType.STEP_ERROR]
        assert len(error_events) > 0
        assert not executed
    else:
        # Should complete successfully
        assert executed
        assert any(e.type == EventType.FINISH for e in events)
