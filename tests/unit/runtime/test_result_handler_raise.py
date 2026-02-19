from unittest.mock import AsyncMock, MagicMock


from justpipe._internal.runtime.orchestration.control import StepCompleted
from justpipe._internal.runtime.execution.result_handler import _ResultHandler
from justpipe._internal.definition.steps import _StandardStep
from justpipe.types import Raise
from tests.unit.fakes import FakeOrchestrator


async def _noop() -> None:
    return None


async def test_raise_with_exception_delegates_to_failure_handler() -> None:
    orchestrator = FakeOrchestrator()
    failure_handler = MagicMock()
    failure_handler.handle_failure = AsyncMock()

    handler = _ResultHandler(
        orchestrator=orchestrator,
        failure_handler=failure_handler,
        scheduler=MagicMock(),
        steps={"step": _StandardStep(name="step", func=_noop)},
    )

    item = StepCompleted(
        name="step",
        owner="step",
        result=Raise(RuntimeError("boom")),
        payload={"k": "v"},
    )

    events = [
        event
        async for event in handler.process_step_result(item, state={"x": 1}, context={})
    ]

    assert events == []
    failure_handler.handle_failure.assert_awaited_once()


async def test_raise_without_exception_synthesizes_error() -> None:
    """Raise(None) should still trigger failure handling with a synthesized error."""
    orchestrator = FakeOrchestrator()
    failure_handler = MagicMock()
    failure_handler.handle_failure = AsyncMock()

    handler = _ResultHandler(
        orchestrator=orchestrator,
        failure_handler=failure_handler,
        scheduler=MagicMock(),
        steps={"step": _StandardStep(name="step", func=_noop)},
    )

    item = StepCompleted(name="step", owner="step", result=Raise(None), payload=None)
    events = [
        event async for event in handler.process_step_result(item, state={}, context={})
    ]

    assert events == []
    failure_handler.handle_failure.assert_awaited_once()
    # The synthesized error should be a RuntimeError
    call_args = failure_handler.handle_failure.call_args
    error_arg = call_args[0][2]  # third positional arg is the error
    assert isinstance(error_arg, RuntimeError)
    assert "Raise()" in str(error_arg)
