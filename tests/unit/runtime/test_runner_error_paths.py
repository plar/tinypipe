"""Pipeline runner error and startup-path coverage."""

import asyncio
from typing import Any
from unittest.mock import ANY, AsyncMock

import pytest

from justpipe._internal.runtime.engine.composition import RunnerConfig, build_runner
from tests.unit.runtime.conftest import single_step_config
from justpipe._internal.runtime.engine.run_state import _RunPhase
from justpipe.types import (
    Event,
    EventType,
    FailureKind,
    FailureReason,
    FailureSource,
    NodeKind,
)


def _empty_config() -> RunnerConfig[Any, Any]:
    return RunnerConfig(
        steps={},
        topology={},
        injection_metadata={},
        startup_hooks=[],
        shutdown_hooks=[],
    )


async def _empty_stream() -> Any:
    if False:
        yield None


def _single_step_config() -> RunnerConfig[Any, Any]:
    return single_step_config()


@pytest.mark.asyncio
async def test_event_stream_cancelled_path_marks_log() -> None:
    runner = build_runner(_empty_config())

    async def raise_cancel(*_: Any, **__: Any) -> Any:
        raise asyncio.CancelledError()

    runner._startup_phase = raise_cancel  # type: ignore[method-assign]
    runner._shutdown_and_finish = _empty_stream  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        _ = [event async for event in runner._event_stream({}, None)]

    assert runner._ctx.log.cancelled is True


@pytest.mark.asyncio
async def test_event_stream_runtime_error_records_infra_failure() -> None:
    runner = build_runner(_empty_config())

    async def raise_runtime(*_: Any, **__: Any) -> Any:
        raise RuntimeError("boom")

    runner._startup_phase = raise_runtime  # type: ignore[method-assign]
    runner._shutdown_and_finish = _empty_stream  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="boom"):
        _ = [event async for event in runner._event_stream({}, None)]

    assert runner._ctx.log.failures
    assert runner._ctx.log.failures[0].kind is FailureKind.INFRA


@pytest.mark.asyncio
async def test_shutdown_closing_suppresses_shutdown_events() -> None:
    runner = build_runner(_empty_config())
    runner._ctx.log.mark_closing()

    calls = {"count": 0}

    async def fake_shutdown(state: Any, context: Any) -> Any:
        _ = (state, context)
        calls["count"] += 1
        yield Event(EventType.STEP_ERROR, "shutdown", "boom")

    runner._lifecycle.execute_shutdown = fake_shutdown  # type: ignore[method-assign]

    events = [event async for event in runner._shutdown_and_finish()]

    assert events == []
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_startup_phase_uses_explicit_start_target_and_notifies_start() -> None:
    runner = build_runner(_single_step_config())
    runner._ctx.state = {"value": 1}
    runner._ctx.context = {"ctx": 2}
    runner._events.notify_start = AsyncMock()  # type: ignore[method-assign]
    runner._lifecycle.execute_startup = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )

    async def explicit_start() -> None:
        return None

    roots, error_event = await runner._startup_phase(explicit_start)

    assert roots == {"explicit_start"}
    assert error_event is None
    assert runner._ctx.runtime_sm.phase is _RunPhase.STARTUP
    runner._events.notify_start.assert_awaited_once_with(
        runner._ctx.state,
        runner._ctx.context,
        run_id=ANY,
    )
    runner._lifecycle.execute_startup.assert_awaited_once_with(
        runner._ctx.state,
        runner._ctx.context,
    )


@pytest.mark.asyncio
async def test_startup_phase_records_startup_failure() -> None:
    runner = build_runner(_single_step_config())
    runner._ctx.state = {"value": 1}
    runner._ctx.context = None
    runner._events.notify_start = AsyncMock()  # type: ignore[method-assign]
    startup_error = Event(EventType.STEP_ERROR, "startup", "boom")
    runner._lifecycle.execute_startup = AsyncMock(  # type: ignore[method-assign]
        return_value=startup_error
    )

    roots, error_event = await runner._startup_phase(None)

    assert roots == set()
    assert error_event is startup_error
    assert len(runner._ctx.log.failures) == 1
    failure = runner._ctx.log.failures[0]
    assert failure.kind is FailureKind.STARTUP
    assert failure.source is FailureSource.USER_CODE
    assert failure.reason is FailureReason.STARTUP_HOOK_ERROR
    assert failure.error_message == "Startup hook failed: boom"
    assert isinstance(failure.error, RuntimeError)


@pytest.mark.asyncio
async def test_startup_phase_no_steps_records_validation_failure() -> None:
    runner = build_runner(_empty_config())
    runner._ctx.state = {}
    runner._ctx.context = None
    runner._events.notify_start = AsyncMock()  # type: ignore[method-assign]
    runner._lifecycle.execute_startup = AsyncMock(  # type: ignore[method-assign]
        return_value=None
    )

    roots, error_event = await runner._startup_phase(None)

    assert roots == set()
    assert error_event is not None
    assert error_event.type is EventType.STEP_ERROR
    assert error_event.stage == "system"
    assert error_event.payload == "No steps registered"
    assert error_event.node_kind is NodeKind.SYSTEM
    assert len(runner._ctx.log.failures) == 1
    failure = runner._ctx.log.failures[0]
    assert failure.kind is FailureKind.VALIDATION
    assert failure.source is FailureSource.FRAMEWORK
    assert failure.reason is FailureReason.NO_STEPS
