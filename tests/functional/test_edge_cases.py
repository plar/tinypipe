"""Edge case tests for justpipe."""

from typing import Any
from justpipe import EventType, Pipe


async def test_empty_pipeline() -> None:
    """Empty pipeline should yield ERROR and FINISH, not crash."""
    pipe: Pipe[Any, Any] = Pipe()
    events = [e async for e in pipe.run({})]

    assert len(events) >= 2
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1
    assert "No steps registered" in error_events[0].data
    assert events[-1].type == EventType.FINISH


async def test_startup_exception_runs_shutdown() -> None:
    """If startup hook fails, shutdown hooks should still run."""
    shutdown_called = False

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.on_startup
    async def bad_startup(ctx: Any) -> None:
        raise ValueError("Startup failed!")

    @pipe.on_shutdown
    async def cleanup(ctx: Any) -> None:
        nonlocal shutdown_called
        shutdown_called = True

    @pipe.step
    async def dummy(s: Any) -> None:
        pass

    events = [e async for e in pipe.run({})]

    # Should have startup error
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Startup failed" in str(e.data) for e in error_events)

    # Shutdown should have been called
    assert shutdown_called

    # Should end with FINISH
    assert events[-1].type == EventType.FINISH


async def test_shutdown_exception_yields_error() -> None:
    """Shutdown hook exception should yield ERROR event."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.on_shutdown
    async def bad_shutdown(ctx: Any) -> None:
        raise ValueError("Shutdown failed!")

    @pipe.step
    async def dummy(s: Any) -> None:
        pass

    events = [e async for e in pipe.run({})]

    # Should have shutdown error
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Shutdown failed" in str(e.data) for e in error_events)

    # Should still end with FINISH
    assert events[-1].type == EventType.FINISH


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
    assert any(e.data == "before_error" for e in token_events)

    # Should have error event
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Mid-stream failure" in str(e.data) for e in error_events)

    # Should end with FINISH
    assert events[-1].type == EventType.FINISH


async def test_multiple_startup_hooks_partial_failure() -> None:
    """If second startup hook fails, first ran and shutdown still runs."""
    hooks_called = []

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.on_startup
    async def startup1(ctx: Any) -> None:
        hooks_called.append("startup1")

    @pipe.on_startup
    async def startup2(ctx: Any) -> None:
        hooks_called.append("startup2")
        raise ValueError("Second startup failed!")

    @pipe.on_shutdown
    async def shutdown1(ctx: Any) -> None:
        hooks_called.append("shutdown1")

    @pipe.step
    async def dummy(s: Any) -> None:
        pass

    events = [e async for e in pipe.run({})]

    assert "startup1" in hooks_called
    assert "startup2" in hooks_called
    assert "shutdown1" in hooks_called
    assert events[-1].type == EventType.FINISH


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
