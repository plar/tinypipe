import pytest
from typing import Any
from unittest.mock import Mock
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_startup_handlers(state: Any, context: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log: list[str] = []

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
    pipe: Pipe[Any, Any] = Pipe(Any, Any)
    seen: list[str] = []

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
    pipe: Pipe[Any, Any] = Pipe(name="test_pipe")

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
    assert any(e.type == EventType.STEP_ERROR and e.stage == "startup" for e in events)

    # Check how many times shutdown was called
    assert shutdown_mock.call_count == 1


@pytest.mark.asyncio
async def test_shutdown_errors_are_yielded_on_startup_failure() -> None:
    pipe: Pipe[Any, Any] = Pipe(name="test_pipe")

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
    assert any(e.type == EventType.STEP_ERROR and e.stage == "startup" for e in events)
    assert any(e.type == EventType.STEP_ERROR and e.stage == "shutdown" for e in events)


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
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert any("Startup failed" in str(e.payload) for e in error_events)

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
    error_events = [e for e in events if e.type == EventType.STEP_ERROR]
    assert any("Shutdown failed" in str(e.payload) for e in error_events)

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


@pytest.mark.asyncio
async def test_observers_notified_of_startup_failure() -> None:
    """Test that observers are correctly notified when startup fails.

    This tests the fix for resource cleanup - observers should receive
    error notification, not success notification, when startup fails.
    """
    from justpipe.observability import Observer

    pipe: Pipe[Any, None] = Pipe()

    observer_start_called = False
    observer_error_called = False
    observer_end_called = False

    class TestObserver(Observer):
        async def on_pipeline_start(self, state: Any, context: Any, meta: Any) -> None:
            _ = meta
            nonlocal observer_start_called
            observer_start_called = True

        async def on_event(
            self, state: Any, context: Any, meta: Any, event: Any
        ) -> None:
            _ = (state, context, meta, event)
            pass

        async def on_pipeline_end(
            self, state: Any, context: Any, meta: Any, duration_s: float
        ) -> None:
            _ = (state, context, meta, duration_s)
            nonlocal observer_end_called
            observer_end_called = True

        async def on_pipeline_error(
            self, state: Any, context: Any, meta: Any, error: Exception
        ) -> None:
            _ = (state, context, meta, error)
            nonlocal observer_error_called
            observer_error_called = True

    pipe.add_observer(TestObserver())

    @pipe.on_startup
    async def failing_startup() -> None:
        raise RuntimeError("Startup failed")

    @pipe.step()
    async def dummy(state: Any) -> None:
        pass

    _ = [e async for e in pipe.run({})]

    assert observer_start_called, "Observer should be notified of pipeline start"
    assert observer_error_called, "Observer should be notified of error"
    assert not observer_end_called, "Observer should NOT be notified of successful end"


@pytest.mark.asyncio
async def test_shutdown_runs_when_no_steps_registered() -> None:
    """Test that shutdown hooks run even when there are no steps registered.

    This tests the fix for resource cleanup - shutdown should always run
    to clean up resources, even if the pipeline has no steps.
    """
    pipe: Pipe[Any, None] = Pipe()

    startup_called = False
    shutdown_called = False

    @pipe.on_startup
    async def setup() -> None:
        nonlocal startup_called
        startup_called = True

    @pipe.on_shutdown
    async def cleanup() -> None:
        nonlocal shutdown_called
        shutdown_called = True

    # No steps defined
    events = [e async for e in pipe.run({})]

    assert startup_called, "Startup should have been called"
    assert shutdown_called, "Shutdown should have been called for cleanup"
    assert any(e.type == EventType.STEP_ERROR for e in events)


@pytest.mark.asyncio
async def test_barrier_cleanup_when_startup_fails() -> None:
    """Test that barrier task cleanup doesn't crash when execution never started.

    This tests the fix for resource cleanup - barrier cleanup should only
    run if execution actually started, to avoid errors.
    """
    pipe: Pipe[Any, None] = Pipe(allow_multi_root=True)

    @pipe.on_startup
    async def failing_startup() -> None:
        raise RuntimeError("Startup failed")

    @pipe.step()
    async def step1(state: Any) -> None:
        pass

    @pipe.step(to="step3")
    async def step2(state: Any) -> None:
        pass

    @pipe.step(barrier_timeout=5.0)
    async def step3(state: Any) -> None:
        # This is a barrier step (multiple parents)
        pass

    # Should not crash even though execution never started
    events = [e async for e in pipe.run({})]

    assert any(e.type == EventType.STEP_ERROR for e in events)
