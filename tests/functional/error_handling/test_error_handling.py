import pytest
import logging
import asyncio

from typing import Any
from collections.abc import AsyncGenerator
from justpipe import Pipe, EventType, Retry, Skip


@pytest.mark.asyncio
async def test_step_level_substitution() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()

    async def handle_error(error: Exception, state: dict[str, Any]) -> None:
        state["received"] = "fallback_result"
        return None  # Just continue to successors

    @pipe.step(on_error=handle_error, to="next_step")
    async def failing_step(state: dict[str, Any]) -> None:
        raise ValueError("Boom")

    @pipe.step()
    async def next_step(state: dict[str, Any]) -> None:
        pass

    state: dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("received") == "fallback_result"


@pytest.mark.asyncio
async def test_step_level_retry() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()

    async def handle_error(error: Exception, state: dict[str, Any]) -> Any:
        if state["attempts"] < 2:
            return Retry()
        return Skip()

    @pipe.step(on_error=handle_error)
    async def flaky_step(state: dict[str, Any]) -> AsyncGenerator[str, None]:
        state["attempts"] = state.get("attempts", 0) + 1
        if state["attempts"] < 2:
            raise ValueError("Try again")
        yield "success"

    state: dict[str, Any] = {"attempts": 0}
    tokens: list[Any] = []
    async for ev in pipe.run(state):
        if ev.type == EventType.TOKEN:
            tokens.append(ev.payload)

    assert state["attempts"] == 2
    assert tokens == ["success"]


@pytest.mark.asyncio
async def test_global_handler() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.on_error
    async def global_handler(
        error: Exception, step_name: str, state: dict[str, Any]
    ) -> Any:
        state["global_caught"] = step_name
        return Skip()

    @pipe.step()
    async def fail_me(state: dict[str, Any]) -> None:
        raise ValueError("Global catch me")

    state: dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("global_caught") == "fail_me"


@pytest.mark.asyncio
async def test_skip_pruning() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.step(on_error=lambda e: Skip(), to="dependent")
    async def fail_and_skip(state: dict[str, Any]) -> None:
        raise ValueError("Skip me")

    @pipe.step()
    async def dependent(state: dict[str, Any]) -> None:
        state["ran"] = True

    state: dict[str, Any] = {"ran": False}
    async for ev in pipe.run(state):
        pass

    assert state["ran"] is False


@pytest.mark.asyncio
async def test_default_logging(caplog: pytest.LogCaptureFixture) -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.step()
    async def unhandled(state: dict[str, Any]) -> None:
        raise ValueError("No handler here")

    state: dict[str, Any] = {}
    with caplog.at_level(logging.ERROR):
        async for ev in pipe.run(state):
            pass

    assert "Step 'unhandled' failed with ValueError: No handler here" in caplog.text
    assert "State: {}" in caplog.text


@pytest.mark.asyncio
async def test_step_redirect_via_next() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe()
    from justpipe._internal.types import _Next

    async def handle_error(error: Exception, state: dict[str, Any]) -> _Next:
        return _Next("recovery")

    @pipe.step(on_error=handle_error)
    async def failing_step(state: dict[str, Any]) -> None:
        raise ValueError("Boom")

    @pipe.step()
    async def recovery(state: dict[str, Any]) -> None:
        state["recovered"] = True

    state: dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("recovered") is True


@pytest.mark.asyncio
async def test_error_handler_failure() -> None:
    """Test when the error handler itself raises an exception."""
    pipe: Pipe[None, None] = Pipe()

    def buggy_handler(error: Exception) -> None:
        raise ValueError("Handler crashed")

    @pipe.step("fail", on_error=buggy_handler)
    async def fail() -> None:
        raise RuntimeError("Step failed")

    events: list[Any] = []
    async for ev in pipe.run(None):
        events.append(ev)

    # The runner catches the handler exception and reports it
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert len(error_events) >= 1
    # It should eventually report the handler's error (or original error depending on impl detail,
    # checking code: _execute_handler -> raise e -> _wrapper catches -> _report_error)
    # The handler raised ValueError("Handler crashed"), so that should be the reported error.
    assert "Handler crashed" in str(error_events[0].payload)


@pytest.mark.asyncio
async def test_error_handler_injection() -> None:
    pipe: Pipe[str, None] = Pipe()
    captured: dict[str, Any] = {}

    def handler(step_name: str, error: Exception, state: str) -> None:
        captured["name"] = step_name
        captured["error"] = error
        captured["state"] = state

    @pipe.step("fail", on_error=handler)
    async def fail() -> None:
        raise RuntimeError("Boom")

    async for _ in pipe.run("initial_state"):
        pass

    assert captured["name"] == "fail"
    assert isinstance(captured["error"], RuntimeError)
    assert captured["state"] == "initial_state"


@pytest.mark.asyncio
async def test_step_handler_fail_to_global() -> None:
    """Test step handler failing and falling back to global handler."""
    pipe: Pipe[None, None] = Pipe()

    def step_handler(error: Exception) -> None:
        raise ValueError("Step handler failed")

    captured: list[Any] = []

    def global_handler(error: Exception) -> Any:
        captured.append(error)
        return Skip()

    pipe.on_error(global_handler)

    @pipe.step("fail", on_error=step_handler)
    async def fail() -> None:
        raise RuntimeError("Original error")

    async for _ in pipe.run(None):
        pass

    assert len(captured) == 1
    assert str(captured[0]) == "Step handler failed"


@pytest.mark.asyncio
async def test_streaming_exception_midstream() -> None:
    """Exception mid-stream should yield ERROR but collect prior tokens."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step
    async def failing_stream(s: Any) -> Any:
        yield "before_error"
        raise ValueError("Mid-stream failure!")
        yield "after_error"  # Never reached

    events = [e async for e in pipe.run({})]

    # Should have the token before the error
    token_events = [e for e in events if e.type == EventType.TOKEN]
    assert any(e.payload == "before_error" for e in token_events)

    # Should have error event
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert any("Mid-stream failure" in str(e.payload) for e in error_events)

    # Should end with FINISH
    assert events[-1].type == EventType.FINISH


@pytest.mark.asyncio
async def test_error_handler_sync_function() -> None:
    """Test error handler works with synchronous functions."""
    pipe: Pipe[dict[str, int], None] = Pipe()
    handler_called = False

    def sync_error_handler(error: Exception, state: dict[str, int]) -> None:
        nonlocal handler_called
        handler_called = True

    @pipe.step(on_error=sync_error_handler)
    async def failing_step(state: dict[str, int]) -> None:
        raise ValueError("test error")

    _ = [e async for e in pipe.run({})]

    assert handler_called, "Synchronous error handler should have been called"


@pytest.mark.asyncio
async def test_error_handler_async_function() -> None:
    """Test error handler works with async functions."""
    pipe: Pipe[dict[str, int], None] = Pipe()
    handler_called = False

    async def async_error_handler(error: Exception, state: dict[str, int]) -> None:
        nonlocal handler_called
        handler_called = True
        await asyncio.sleep(0)  # Ensure it's actually async

    @pipe.step(on_error=async_error_handler)
    async def failing_step(state: dict[str, int]) -> None:
        raise ValueError("test error")

    _ = [e async for e in pipe.run({})]

    assert handler_called, "Async error handler should have been called"


@pytest.mark.asyncio
async def test_error_handler_sync_returning_awaitable() -> None:
    """Test error handler works with sync functions that return awaitables.

    This tests the fix for inconsistent async conventions - we now properly
    handle sync functions that return coroutines.
    """
    import asyncio

    pipe: Pipe[dict[str, int], None] = Pipe()
    handler_called = False

    def sync_returning_awaitable(error: Exception, state: dict[str, int]) -> Any:
        nonlocal handler_called
        handler_called = True
        # Return a coroutine (not await it)
        return asyncio.sleep(0)

    @pipe.step(on_error=sync_returning_awaitable)
    async def failing_step(state: dict[str, int]) -> None:
        raise ValueError("test error")

    _ = [e async for e in pipe.run({})]

    assert handler_called, "Handler should have been called"
