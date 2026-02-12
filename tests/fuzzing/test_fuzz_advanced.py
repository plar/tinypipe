"""Advanced fuzzing tests for complex pipeline features.

Tests barriers, switches, retries, state transitions, and sub-pipelines.
"""

import asyncio
import pytest
from typing import Any
from hypothesis import given, strategies as st, settings

from justpipe import Pipe, EventType

pytestmark = pytest.mark.slow


# ============================================================================
# Switch Routing Fuzz Tests
# ============================================================================


@given(
    route_key=st.sampled_from(["route_a", "route_b", "route_c"]),
)
@settings(max_examples=10, deadline=2000)
@pytest.mark.asyncio
async def test_fuzz_switch_routing(route_key: str) -> None:
    """Test switch routing with random route selections."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[str] = []

    @pipe.switch(
        "router",
        to={
            "route_a": "step_a",
            "route_b": "step_b",
            "route_c": "step_c",
        },
    )
    async def router(state: Any) -> str:
        return route_key

    @pipe.step("step_a")
    async def step_a(state: Any) -> None:
        executed.append("a")

    @pipe.step("step_b")
    async def step_b(state: Any) -> None:
        executed.append("b")

    @pipe.step("step_c")
    async def step_c(state: Any) -> None:
        executed.append("c")

    _ = [e async for e in pipe.run(None)]

    # Should execute exactly one route
    assert len(executed) == 1
    # Should execute the correct route
    expected = route_key.split("_")[1]
    assert executed[0] == expected


# ============================================================================
# Retry Logic Fuzz Tests
# ============================================================================


@given(
    retries=st.integers(min_value=0, max_value=3),
    fail_until_attempt=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=10, deadline=3000)
@pytest.mark.asyncio
async def test_fuzz_retry_logic(retries: int, fail_until_attempt: int) -> None:
    """Test retry logic with random retry counts and failure patterns."""
    pipe: Pipe[Any, Any] = Pipe()
    attempts: list[int] = []

    @pipe.step(retries=retries, retry_wait_min=0.01, retry_wait_max=0.01)
    async def might_fail(state: Any) -> None:
        attempt_num = len(attempts)
        attempts.append(attempt_num)
        if attempt_num < fail_until_attempt:
            raise ValueError(f"Intentional failure {attempt_num}")

    _ = [e async for e in pipe.run(None)]

    # Should attempt: 1 initial + min(retries, fail_until_attempt) retries
    if fail_until_attempt == 0:
        # No failures, completes on first try
        assert len(attempts) == 1
    elif fail_until_attempt <= retries:
        # Enough retries to succeed
        assert len(attempts) == fail_until_attempt + 1
    else:
        # Not enough retries, gives up
        assert len(attempts) == retries + 1


# ============================================================================
# Barrier Operations Fuzz Tests
# ============================================================================


@given(
    worker_count=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=10, deadline=3000)
@pytest.mark.asyncio
async def test_fuzz_barrier_with_workers(worker_count: int) -> None:
    """Test barriers with random worker counts."""
    pipe: Pipe[Any, Any] = Pipe()
    completed: list[int] = []

    @pipe.map(each="worker", to="sync_point")
    async def create_workers(state: Any) -> range:
        return range(worker_count)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        await asyncio.sleep(0.01)
        completed.append(item)

    @pipe.step(name="sync_point", barrier_timeout=2.0)
    async def after_barrier(state: Any) -> None:
        pass

    events = [e async for e in pipe.run(None)]

    # All workers should complete
    assert len(completed) == worker_count
    assert any(e.type == EventType.FINISH for e in events)


# ============================================================================
# Sub-Pipeline Nesting Fuzz Tests
# ============================================================================


@given(
    nesting_depth=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=5, deadline=3000)
@pytest.mark.asyncio
async def test_fuzz_sub_pipeline_nesting(nesting_depth: int) -> None:
    """Test nested sub-pipelines with random depth."""
    execution_order: list[str] = []

    def create_sub_pipe(depth: int) -> Pipe[Any, Any]:
        """Recursively create nested sub-pipelines."""
        sub_pipe: Pipe[Any, Any] = Pipe()

        @sub_pipe.step()
        async def process(state: Any) -> None:
            execution_order.append(f"depth_{depth}")
            if depth > 1:
                nested_pipe = create_sub_pipe(depth - 1)
                async for _ in nested_pipe.run(state):
                    pass

        return sub_pipe

    main_pipe: Pipe[Any, Any] = Pipe()

    @main_pipe.step()
    async def start(state: Any) -> None:
        execution_order.append("main")
        sub = create_sub_pipe(nesting_depth)
        async for _ in sub.run(state):
            pass

    _ = [e async for e in main_pipe.run(None)]

    # Should execute all levels
    assert len(execution_order) == nesting_depth + 1
    assert execution_order[0] == "main"


@given(
    sub_pipe_count=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=5, deadline=3000)
@pytest.mark.asyncio
async def test_fuzz_multiple_sub_pipelines(sub_pipe_count: int) -> None:
    """Test multiple sub-pipelines executing in parallel."""
    main_pipe: Pipe[Any, Any] = Pipe()
    completed: list[int] = []

    @main_pipe.map(each="run_sub")
    async def create_sub_pipes(state: Any) -> range:
        return range(sub_pipe_count)

    @main_pipe.step()
    async def run_sub(state: Any, item: int) -> None:
        sub_pipe: Pipe[Any, Any] = Pipe()

        @sub_pipe.step()
        async def worker(s: Any) -> None:
            completed.append(item)

        async for _ in sub_pipe.run(state):
            pass

    _ = [e async for e in main_pipe.run(None)]

    # All sub-pipelines should complete
    assert len(completed) == sub_pipe_count


# ============================================================================
# Complex Feature Combinations
# ============================================================================


@given(
    use_barrier=st.booleans(),
    worker_count=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=5, deadline=3000)
@pytest.mark.asyncio
async def test_fuzz_barrier_combinations(use_barrier: bool, worker_count: int) -> None:
    """Test barriers with random configurations."""
    pipe: Pipe[Any, Any] = Pipe()
    completed: list[int] = []

    @pipe.map(each="worker", to="after_map" if not use_barrier else "sync_point")
    async def create_workers(state: Any) -> range:
        return range(worker_count)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        completed.append(item)

    if use_barrier:

        @pipe.step(name="sync_point", barrier_timeout=2.0, to="after_map")
        async def sync(state: Any) -> None:
            pass

    @pipe.step("after_map")
    async def after_map(state: Any) -> None:
        pass

    events = [e async for e in pipe.run(None)]

    # All workers should complete
    assert len(completed) == worker_count
    assert any(e.type == EventType.FINISH for e in events)
