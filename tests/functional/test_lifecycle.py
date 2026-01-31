import pytest
from typing import Any, List
from unittest.mock import Mock
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_startup_handlers(state: Any, context: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log: List[str] = []

    async def _startup(ctx: Any) -> None:
        log.append("startup")

    async def _shutdown(ctx: Any) -> None:
        log.append("shutdown")

    pipe.on_startup(_startup)
    pipe.on_shutdown(_shutdown)

    @pipe.step("start")
    async def start() -> None:
        pass

    async for _ in pipe.run(state, context):
        pass
    assert log == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_lifecycle_injection(state: Any, context: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe[Any, Any]()
    seen: List[str] = []

    @pipe.on_startup
    async def startup(s: Any, ctx: Any) -> None:
        assert s is state
        assert ctx is context
        seen.append("startup")

    @pipe.on_shutdown
    async def shutdown(s: Any, ctx: Any) -> None:
        assert s is state
        assert ctx is context
        seen.append("shutdown")

    @pipe.step("start")
    async def start(s: Any) -> None:
        assert s is state

    async for _ in pipe.run(state, context):
        pass

    assert seen == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_shutdown_called_once_on_startup_failure() -> None:
    pipe: Pipe[Any, Any] = Pipe("test_pipe")

    shutdown_mock = Mock()

    async def failing_startup(ctx: Any) -> None:
        raise ValueError("Startup failed")

    async def shutdown_hook(ctx: Any) -> None:
        shutdown_mock()

    pipe.on_startup(failing_startup)
    pipe.on_shutdown(shutdown_hook)

    # Run the pipeline
    events = []
    async for ev in pipe.run(state={}):
        events.append(ev)

    # Check that startup failure was reported
    assert any(e.type == EventType.ERROR and e.stage == "startup" for e in events)

    # Check how many times shutdown was called
    assert shutdown_mock.call_count == 1


@pytest.mark.asyncio
async def test_shutdown_errors_are_yielded_on_startup_failure() -> None:
    pipe: Pipe[Any, Any] = Pipe("test_pipe")

    async def failing_startup(ctx: Any) -> None:
        raise ValueError("Startup failed")

    async def failing_shutdown(ctx: Any) -> None:
        raise ValueError("Shutdown failed")

    pipe.on_startup(failing_startup)
    pipe.on_shutdown(failing_shutdown)

    events = []
    async for ev in pipe.run(state={}):
        events.append(ev)

    # Should see both startup and shutdown errors
    assert any(e.type == EventType.ERROR and e.stage == "startup" for e in events)
    assert any(e.type == EventType.ERROR and e.stage == "shutdown" for e in events)


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
