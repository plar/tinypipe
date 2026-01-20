import pytest
import logging
from typing import Any, AsyncGenerator, List, Dict
from justpipe import Pipe, EventType, Retry, Skip


@pytest.mark.asyncio
async def test_step_level_substitution() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    async def handle_error(error: Exception, state: Dict[str, Any]) -> None:
        state["received"] = "fallback_result"
        return None  # Just continue to successors

    @pipe.step(on_error=handle_error, to="next_step")
    async def failing_step(state: Dict[str, Any]) -> None:
        raise ValueError("Boom")

    @pipe.step()
    async def next_step(state: Dict[str, Any]) -> None:
        pass

    state: Dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("received") == "fallback_result"


@pytest.mark.asyncio
async def test_step_level_retry() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    async def handle_error(error: Exception, state: Dict[str, Any]) -> Any:
        if state["attempts"] < 2:
            return Retry()
        return Skip()

    @pipe.step(on_error=handle_error)
    async def flaky_step(state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        state["attempts"] = state.get("attempts", 0) + 1
        if state["attempts"] < 2:
            raise ValueError("Try again")
        yield "success"

    state: Dict[str, Any] = {"attempts": 0}
    tokens: List[Any] = []
    async for ev in pipe.run(state):
        if ev.type == EventType.TOKEN:
            tokens.append(ev.data)

    assert state["attempts"] == 2
    assert tokens == ["success"]


@pytest.mark.asyncio
async def test_global_handler() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    @pipe.on_error
    async def global_handler(error: Exception, step_name: str, state: Dict[str, Any]) -> Any:
        state["global_caught"] = step_name
        return Skip()

    @pipe.step()
    async def fail_me(state: Dict[str, Any]) -> None:
        raise ValueError("Global catch me")

    state: Dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("global_caught") == "fail_me"


@pytest.mark.asyncio
async def test_skip_pruning() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    @pipe.step(on_error=lambda e: Skip(), to="dependent")
    async def fail_and_skip(state: Dict[str, Any]) -> None:
        raise ValueError("Skip me")

    @pipe.step()
    async def dependent(state: Dict[str, Any]) -> None:
        state["ran"] = True

    state: Dict[str, Any] = {"ran": False}
    async for ev in pipe.run(state):
        pass

    assert state["ran"] is False


@pytest.mark.asyncio
async def test_default_logging(caplog: pytest.LogCaptureFixture) -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    @pipe.step()
    async def unhandled(state: Dict[str, Any]) -> None:
        raise ValueError("No handler here")

    state: Dict[str, Any] = {}
    with caplog.at_level(logging.ERROR):
        async for ev in pipe.run(state):
            pass

    assert "Step 'unhandled' failed with ValueError: No handler here" in caplog.text
    assert "State: {}" in caplog.text


@pytest.mark.asyncio
async def test_step_redirect_via_next() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()
    from justpipe.types import _Next

    async def handle_error(error: Exception, state: Dict[str, Any]) -> _Next:
        return _Next("recovery")

    @pipe.step(on_error=handle_error)
    async def failing_step(state: Dict[str, Any]) -> None:
        raise ValueError("Boom")

    @pipe.step()
    async def recovery(state: Dict[str, Any]) -> None:
        state["recovered"] = True

    state: Dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("recovered") is True


@pytest.mark.asyncio
async def test_startup_hook_failure() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.on_startup
    async def bad_startup(_: Any) -> None:
        raise ValueError("Startup failed")

    events: List[Any] = []
    async for ev in pipe.run(None):
        events.append(ev)

    assert len(events) >= 1
    assert events[0].type == EventType.ERROR
    assert events[0].data == "Startup failed"
    # Ensure finally block runs
    assert events[-1].type == EventType.FINISH


@pytest.mark.asyncio
async def test_shutdown_hook_failure() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step("noop")
    async def noop() -> None:
        pass

    @pipe.on_shutdown
    async def bad_shutdown(_: Any) -> None:
        raise ValueError("Shutdown failed")

    events: List[Any] = []
    async for ev in pipe.run(None):
        events.append(ev)

    # Should contain START, STEP_START, STEP_END, ERROR (shutdown), FINISH
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1
    assert error_events[0].data == "Shutdown failed"


@pytest.mark.asyncio
async def test_error_handler_failure() -> None:
    """Test when the error handler itself raises an exception."""
    pipe: Pipe[None, None] = Pipe()

    def buggy_handler(error: Exception) -> None:
        raise ValueError("Handler crashed")

    @pipe.step("fail", on_error=buggy_handler)
    async def fail() -> None:
        raise RuntimeError("Step failed")

    events: List[Any] = []
    async for ev in pipe.run(None):
        events.append(ev)

    # The runner catches the handler exception and reports it
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) >= 1
    # It should eventually report the handler's error (or original error depending on impl detail,
    # checking code: _execute_handler -> raise e -> _wrapper catches -> _report_error)
    # The handler raised ValueError("Handler crashed"), so that should be the reported error.
    assert "Handler crashed" in str(error_events[0].data)


@pytest.mark.asyncio
async def test_error_handler_injection() -> None:
    pipe: Pipe[str, None] = Pipe()
    captured: Dict[str, Any] = {}

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

    captured: List[Any] = []

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