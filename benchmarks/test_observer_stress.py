import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from justpipe.observability import Observer
from justpipe.pipe import Pipe


class FastObserver(Observer):
    async def on_event(self, state: Any, context: Any, meta: Any, event: Any) -> None:
        _ = (state, context, meta, event)


def _build_pipe(observer_count: int) -> Pipe[dict[str, Any], None]:
    pipe: Pipe[dict[str, Any], None] = Pipe(name=f"StressPipe{observer_count}")

    @pipe.step("start", to="work")
    async def start() -> None:
        return None

    @pipe.step("work")
    async def work() -> AsyncGenerator[int, None]:
        for i in range(100):
            yield i

    for _ in range(observer_count):
        pipe.add_observer(FastObserver())
    return pipe


async def _run_once(observer_count: int) -> float:
    pipe = _build_pipe(observer_count)
    start = time.perf_counter()
    async for _ in pipe.run({}):
        pass
    return time.perf_counter() - start


def _run_once_sync(observer_count: int) -> float:
    return asyncio.run(_run_once(observer_count))


@pytest.mark.benchmark
def test_observer_stress_benchmark(benchmark: Any) -> None:
    baseline_duration = benchmark(lambda: _run_once_sync(1))
    stress_duration = _run_once_sync(50)
    assert stress_duration < baseline_duration * 15
