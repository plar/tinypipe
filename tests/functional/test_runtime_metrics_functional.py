import asyncio

from justpipe import Pipe
from justpipe.types import RuntimeMetrics


async def test_finish_metrics_basic() -> None:
    pipe: Pipe[dict[str, int], dict[str, int]] = Pipe(dict, dict)

    @pipe.step()
    async def add_one(state: dict[str, int]) -> None:
        state["x"] = state.get("x", 0) + 1

    events = []
    initial_state: dict[str, int] = {}
    async for ev in pipe.run(initial_state):
        events.append(ev)

    finish = next(e for e in events if e.type.value == "finish")
    metrics = finish.payload.metrics
    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.tasks.started >= 1
    assert metrics.tasks.completed >= 1
    assert "add_one" in metrics.step_latency
    assert metrics.step_latency["add_one"].count == 1
    assert metrics.queue.max_depth >= 1


async def test_finish_metrics_map_workers() -> None:
    pipe: Pipe[dict[str, int], dict[str, int]] = Pipe(dict, dict)

    @pipe.map(each="worker")
    async def fan_out() -> list[int]:
        return [1, 2, 3]

    @pipe.step()
    async def worker(item: int) -> None:
        _ = item
        await asyncio.sleep(0.01)

    events = []
    initial_state: dict[str, int] = {}
    async for ev in pipe.run(initial_state):
        events.append(ev)

    finish = next(e for e in events if e.type.value == "finish")
    metrics = finish.payload.metrics
    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.maps.maps_started == 1
    assert metrics.maps.maps_completed == 1
    assert metrics.maps.workers_started == 3
    # map fan-out captured from actual worker lifecycle
    assert metrics.maps.peak_workers >= 2


async def test_finish_metrics_map_peak_workers_respects_throttle() -> None:
    pipe: Pipe[dict[str, int], dict[str, int]] = Pipe(dict, dict)

    @pipe.map(each="worker", max_concurrency=1)
    async def start() -> list[int]:
        return [1, 2, 3, 4]

    @pipe.step()
    async def worker(item: int) -> None:
        _ = item
        await asyncio.sleep(0.01)

    events = []
    async for ev in pipe.run({}):
        events.append(ev)

    finish = next(e for e in events if e.type.value == "finish")
    metrics = finish.payload.metrics
    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.maps.workers_started == 4
    assert metrics.maps.peak_workers == 1
