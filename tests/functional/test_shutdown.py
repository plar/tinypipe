import pytest
from typing import Any
from unittest.mock import Mock
from justpipe import Pipe, EventType


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
    assert shutdown_mock.call_count == 1, (
        f"Expected shutdown to be called once, but was called {shutdown_mock.call_count} times"
    )


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
