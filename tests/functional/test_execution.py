"""Functional tests for core pipeline execution."""

import pytest
import asyncio
from typing import Any, List, AsyncGenerator
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_linear_execution_flow(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    events: List[Any] = []

    @pipe.step("start", to="step2")
    async def start() -> None:
        return None

    @pipe.step("step2")
    async def step2() -> None:
        pass

    async for event in pipe.run(state):
        events.append(event)

    types = [e.type for e in events]
    assert EventType.START in types
    assert EventType.FINISH in types
    assert [e.stage for e in events if e.type == EventType.STEP_START] == [
        "start",
        "step2",
    ]


@pytest.mark.asyncio
async def test_streaming_execution(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    tokens: List[Any] = []

    @pipe.step("streamer")
    async def streamer() -> AsyncGenerator[str, None]:
        yield "a"
        yield "b"

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            tokens.append(event.data)
    assert tokens == ["a", "b"]


@pytest.mark.asyncio
async def test_step_not_found(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    errors: List[Any] = []

    @pipe.step("start", to="non_existent")
    async def start() -> None:
        pass

    async for event in pipe.run(state):
        if event.type == EventType.ERROR:
            errors.append(event)
    assert any("Step not found" in str(e.data) for e in errors)


@pytest.mark.asyncio
async def test_step_timeout_execution() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("slow", timeout=0.1)
    async def slow() -> None:
        await asyncio.sleep(0.5)

    events: List[Any] = []
    async for ev in pipe.run(None):
        if ev.type == EventType.ERROR:
            events.append(ev)

    assert len(events) == 1
    assert "timed out" in str(events[0].data)


def test_async_gen_retry_warning() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    with pytest.warns(UserWarning, match="cannot retry automatically"):

        @pipe.step("stream", retries=3)
        async def stream() -> AsyncGenerator[int, None]:
            yield 1


def test_advanced_retry_config() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    # Should not raise
    @pipe.step("retry", retries={"stop": 1})
    async def retry_step() -> None:
        pass

    assert "retry" in pipe._steps


@pytest.mark.asyncio
async def test_empty_pipeline() -> None:
    """Empty pipeline should yield ERROR and FINISH, not crash."""
    pipe: Pipe[Any, Any] = Pipe()
    events = [e async for e in pipe.run({})]

    assert len(events) >= 2
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1
    assert "No steps registered" in error_events[0].data
    assert events[-1].type == EventType.FINISH


@pytest.mark.asyncio
async def test_concurrent_token_streaming() -> None:
    """Parallel steps should both have their tokens collected."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to=["a", "b"])
    async def start(s: Any) -> None:
        pass

    @pipe.step("a")
    async def step_a(s: Any) -> Any:
        yield "token_from_a"

    @pipe.step("b")
    async def step_b(s: Any) -> Any:
        yield "token_from_b"

    events = [e async for e in pipe.run({})]

    token_events = [e for e in events if e.type == EventType.TOKEN]
    token_data = {e.data for e in token_events}

    assert "token_from_a" in token_data
    assert "token_from_b" in token_data


@pytest.mark.asyncio
async def test_context_none_handling() -> None:
    """Steps and hooks should handle context=None gracefully."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.on_startup
    async def startup(ctx: Any) -> None:
        # ctx is None, should not crash
        pass

    @pipe.on_shutdown
    async def shutdown(ctx: Any) -> None:
        # ctx is None, should not crash
        pass

    @pipe.step
    async def step_with_ctx(s: Any, ctx: Any) -> None:
        # ctx is None
        assert ctx is None

    events = [e async for e in pipe.run({}, context=None)]

    assert events[-1].type == EventType.FINISH
    # No errors
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 0
