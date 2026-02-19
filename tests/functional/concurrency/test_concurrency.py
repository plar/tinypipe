"""Tests for concurrency control features (max_concurrency)."""

import asyncio
import pytest
from typing import Any

from justpipe import Pipe, EventType

pytestmark = pytest.mark.slow


async def test_map_max_concurrency_throttling() -> None:
    """Test that max_concurrency limits concurrent workers."""
    pipe: Pipe[Any, Any] = Pipe()
    active_workers: list[int] = []
    max_concurrent = 0

    @pipe.map(each="worker", max_concurrency=3)
    async def create_workers(state: Any) -> range:
        return range(10)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        active_workers.append(item)
        nonlocal max_concurrent
        max_concurrent = max(max_concurrent, len(active_workers))
        await asyncio.sleep(0.01)  # Simulate work
        active_workers.remove(item)

    events = [e async for e in pipe.run(None)]

    # Should have processed all 10 items
    map_workers = [e for e in events if e.type == EventType.MAP_WORKER]
    assert len(map_workers) == 10

    # But never more than 3 concurrent
    assert max_concurrent <= 3
    assert max_concurrent > 0  # At least some were concurrent


async def test_map_max_concurrency_none_is_unlimited() -> None:
    """Test that max_concurrency=None allows unlimited concurrency."""
    pipe: Pipe[Any, Any] = Pipe()
    active_workers: list[int] = []
    max_concurrent = 0

    @pipe.map(each="worker", max_concurrency=None)
    async def create_workers(state: Any) -> range:
        return range(10)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        active_workers.append(item)
        nonlocal max_concurrent
        max_concurrent = max(max_concurrent, len(active_workers))
        await asyncio.sleep(0.01)
        active_workers.remove(item)

    _ = [e async for e in pipe.run(None)]

    # All 10 should run concurrently (or close to it)
    assert max_concurrent >= 8  # Allow some timing variance


async def test_map_max_concurrency_one_is_sequential() -> None:
    """Test that max_concurrency=1 forces sequential execution."""
    pipe: Pipe[Any, Any] = Pipe()
    execution_order: list[tuple[str, int]] = []

    @pipe.map(each="worker", max_concurrency=1)
    async def create_workers(state: Any) -> range:
        return range(5)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        execution_order.append(("start", item))
        await asyncio.sleep(0.01)
        execution_order.append(("end", item))

    _ = [e async for e in pipe.run(None)]

    # Verify sequential execution - each worker completes before next starts
    for i in range(5):
        start_idx = execution_order.index(("start", i))
        end_idx = execution_order.index(("end", i))
        # No other worker should start between this worker's start and end
        between = execution_order[start_idx + 1 : end_idx]
        assert all(event[0] != "start" for event in between)


async def test_map_max_concurrency_with_slow_workers() -> None:
    """Test throttling with workers that take varying time."""
    pipe: Pipe[Any, Any] = Pipe()
    active_workers: list[int] = []
    max_concurrent = 0
    completed: list[int] = []

    @pipe.map(each="worker", max_concurrency=2)
    async def create_workers(state: Any) -> range:
        return range(6)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        active_workers.append(item)
        nonlocal max_concurrent
        max_concurrent = max(max_concurrent, len(active_workers))
        # Varying sleep times
        await asyncio.sleep(0.01 * (item + 1))
        completed.append(item)
        active_workers.remove(item)

    _ = [e async for e in pipe.run(None)]

    # Should never exceed max_concurrency
    assert max_concurrent <= 2
    # All items should complete
    assert len(completed) == 6


async def test_map_max_concurrency_zero_items() -> None:
    """Test that max_concurrency works with zero items."""
    pipe: Pipe[Any, Any] = Pipe()
    worker_called = False

    @pipe.map(each="worker", max_concurrency=3, to="after_map")
    async def create_workers(state: Any) -> list[int]:
        return []  # No items

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        nonlocal worker_called
        worker_called = True

    @pipe.step()
    async def after_map(state: Any) -> None:
        pass  # Step to continue after empty map

    events = [e async for e in pipe.run(None)]

    # Worker should never be called
    assert not worker_called
    # Should emit map start/complete events
    map_events = [
        e for e in events if e.type in (EventType.MAP_START, EventType.MAP_COMPLETE)
    ]
    assert len(map_events) == 2


async def test_map_max_concurrency_single_item() -> None:
    """Test that max_concurrency works with a single item."""
    pipe: Pipe[Any, Any] = Pipe()
    worker_called = 0

    @pipe.map(each="worker", max_concurrency=10)
    async def create_workers(state: Any) -> list[int]:
        return [42]  # Single item

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        nonlocal worker_called
        worker_called += 1
        assert item == 42

    _ = [e async for e in pipe.run(None)]

    # Worker should be called exactly once
    assert worker_called == 1


async def test_map_max_concurrency_preserves_order_in_events() -> None:
    """Test that MAP_WORKER events maintain order even with throttling."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.map(each="worker", max_concurrency=2)
    async def create_workers(state: Any) -> range:
        return range(5)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        await asyncio.sleep(0.01)

    events = [e async for e in pipe.run(None)]

    # MAP_WORKER events should be emitted in order
    map_worker_events = [e for e in events if e.type == EventType.MAP_WORKER]
    indices = [e.payload["index"] for e in map_worker_events]
    assert indices == list(range(5))


async def test_map_max_concurrency_with_errors() -> None:
    """Test that max_concurrency handles worker errors gracefully."""
    pipe: Pipe[Any, Any] = Pipe()
    completed: list[int] = []

    @pipe.map(each="worker", max_concurrency=2)
    async def create_workers(state: Any) -> range:
        return range(5)

    @pipe.step()
    async def worker(state: Any, item: int) -> None:
        if item == 2:
            raise ValueError("Intentional error")
        completed.append(item)
        await asyncio.sleep(0.01)

    events = [e async for e in pipe.run(None)]

    # Other workers should still complete
    assert len(completed) > 0
    # Should have error event
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert len(error_events) > 0


async def test_map_complete_emitted_after_workers_drain() -> None:
    """MAP_COMPLETE should be emitted only after all workers finish."""
    pipe: Pipe[dict[str, int], Any] = Pipe(dict, Any)

    @pipe.map(each="worker")
    async def create_workers(state: dict[str, int]) -> range:
        state["done"] = 0
        return range(4)

    @pipe.step()
    async def worker(state: dict[str, int], item: int) -> None:
        await asyncio.sleep(0.01)
        state["done"] += 1

    state: dict[str, int] = {}
    map_complete_seen = False
    async for event in pipe.run(state):
        if event.type == EventType.MAP_COMPLETE:
            map_complete_seen = True
            assert state["done"] == 4

    assert map_complete_seen
