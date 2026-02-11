import pytest
from typing import Any
from collections.abc import AsyncGenerator
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_map_async_gen_limit_default() -> None:
    pipe: Pipe[dict[str, Any], Any] = Pipe(dict)

    @pipe.step(to="source")
    async def start(state: dict[str, Any]) -> None:
        state["items"] = []

    @pipe.map(each="worker")
    async def source(state: dict[str, Any]) -> AsyncGenerator[int, None]:
        # Return async generator with more than default 100k items
        for i in range(100_001):
            yield i

    @pipe.step()
    async def worker(state: dict[str, Any], item: int) -> None:
        pass

    events = [e async for e in pipe.run({})]

    # Should find a STEP_ERROR event
    error_event = next((e for e in events if e.type == EventType.STEP_ERROR), None)
    assert error_event is not None
    assert "async generator exceeded maximum of 100000 items" in str(
        error_event.payload
    )


@pytest.mark.asyncio
async def test_map_async_gen_limit_configurable() -> None:
    # set limit to 10
    pipe: Pipe[dict[str, Any], Any] = Pipe(dict, max_map_items=10)

    @pipe.map(each="worker")
    async def source(state: dict[str, Any]) -> AsyncGenerator[int, None]:
        for i in range(11):
            yield i

    @pipe.step()
    async def worker(state: dict[str, Any], item: int) -> None:
        pass

    events = [e async for e in pipe.run({})]

    error_event = next((e for e in events if e.type == EventType.STEP_ERROR), None)
    assert error_event is not None
    assert "async generator exceeded maximum of 10 items" in str(error_event.payload)


@pytest.mark.asyncio
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
