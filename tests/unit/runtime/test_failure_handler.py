import pytest
import logging
from typing import Any
from unittest.mock import MagicMock, AsyncMock
from justpipe._internal.runtime.failure.failure_handler import _FailureHandler
from justpipe.types import Event, EventType
from justpipe._internal.runtime.orchestration.control import StepCompleted


@pytest.mark.asyncio
async def test_failure_handler_basic_reporting(
    fake_orchestrator: Any,
) -> None:
    invoker = MagicMock()
    invoker.global_error_handler = None

    handler = _FailureHandler(steps={}, invoker=invoker, orchestrator=fake_orchestrator)

    error = ValueError("Boom")
    await handler.handle_failure(
        name="test_step",
        owner="test_step",
        error=error,
        payload=None,
        state=None,
        context=None,
    )

    # Should submit STEP_ERROR and StepCompleted (None)
    assert len(fake_orchestrator.submissions) == 2
    assert isinstance(fake_orchestrator.submissions[0], Event)
    assert fake_orchestrator.submissions[0].type == EventType.STEP_ERROR
    assert isinstance(fake_orchestrator.submissions[1], StepCompleted)
    assert fake_orchestrator.submissions[1].result is None


@pytest.mark.asyncio
async def test_failure_handler_local_escalation(
    fake_orchestrator: Any,
) -> None:
    # Setup step with local error handler
    local_handler = MagicMock()
    step = MagicMock()
    step.on_error = local_handler

    invoker = MagicMock()
    invoker.execute_handler = AsyncMock(return_value="recovered")
    invoker.global_error_handler = None

    handler = _FailureHandler(
        steps={"test_step": step}, invoker=invoker, orchestrator=fake_orchestrator
    )

    error = ValueError("Initial")
    await handler.handle_failure(
        name="test_step", owner="test_step", error=error, payload={"data": 1}
    )

    # Should call local handler and submit result
    invoker.execute_handler.assert_called_once()
    assert len(fake_orchestrator.submissions) == 1
    assert fake_orchestrator.submissions[0].result == "recovered"


@pytest.mark.asyncio
async def test_failure_handler_logging_uses_standard_timestamp(
    caplog: pytest.LogCaptureFixture,
    fake_orchestrator: Any,
) -> None:
    invoker = MagicMock()
    invoker.global_error_handler = None
    handler = _FailureHandler(steps={}, invoker=invoker, orchestrator=fake_orchestrator)

    with caplog.at_level(logging.ERROR):
        await handler.handle_failure(
            name="test_step",
            owner="test_step",
            error=ValueError("Boom"),
            payload=None,
            state={"x": 1},
            context=None,
        )

    assert caplog.records
    record = caplog.records[0]
    message = record.getMessage()
    assert message.startswith("Step 'test_step' failed with ValueError: Boom")
    assert not message.startswith("[")
    assert getattr(record, "step_name") == "test_step"
    assert getattr(record, "error_type") == "ValueError"
    assert getattr(record, "state_type") == "dict"
    assert not hasattr(record, "timestamp")
