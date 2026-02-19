import pytest
from typing import Any
from collections.abc import AsyncGenerator
from justpipe import Pipe, EventType
from justpipe._internal.definition.steps import _MapStep

pytestmark = pytest.mark.slow

# Reference the actual production default instead of hardcoding
_DEFAULT_LIMIT = _MapStep.DEFAULT_MAX_ITEMS


async def test_map_async_gen_limit_default() -> None:
    pipe: Pipe[dict[str, Any], Any] = Pipe(dict)

    @pipe.step(to="source")
    async def start(state: dict[str, Any]) -> None:
        state["items"] = []

    @pipe.map(each="worker")
    async def source(state: dict[str, Any]) -> AsyncGenerator[int, None]:
        for i in range(_DEFAULT_LIMIT + 1):
            yield i

    @pipe.step()
    async def worker(state: dict[str, Any], item: int) -> None:
        pass

    events = [e async for e in pipe.run({})]

    error_event = next((e for e in events if e.type == EventType.STEP_ERROR), None)
    assert error_event is not None
    assert f"exceeded maximum of {_DEFAULT_LIMIT} items" in str(error_event.payload)


async def test_map_async_gen_limit_configurable() -> None:
    custom_limit = 10
    pipe: Pipe[dict[str, Any], Any] = Pipe(dict, max_map_items=custom_limit)

    @pipe.map(each="worker")
    async def source(state: dict[str, Any]) -> AsyncGenerator[int, None]:
        for i in range(custom_limit + 1):
            yield i

    @pipe.step()
    async def worker(state: dict[str, Any], item: int) -> None:
        pass

    events = [e async for e in pipe.run({})]

    error_event = next((e for e in events if e.type == EventType.STEP_ERROR), None)
    assert error_event is not None
    assert f"exceeded maximum of {custom_limit} items" in str(error_event.payload)


async def test_map_async_gen_limit_within_bounds() -> None:
    pipe: Pipe[dict[str, Any], Any] = Pipe(dict, max_map_items=50)

    @pipe.map(each="worker")
    async def source(state: dict[str, Any]) -> AsyncGenerator[int, None]:
        for i in range(50):
            yield i

    @pipe.step()
    async def worker(state: dict[str, Any], item: int) -> None:
        state.setdefault("collected", []).append(item)

    events = [e async for e in pipe.run({})]

    error_event = next((e for e in events if e.type == EventType.STEP_ERROR), None)
    assert error_event is None

    # Verify execution finished successfully
    finish_event = next(e for e in events if e.type == EventType.FINISH)
    assert finish_event.payload.status.value == "success"
