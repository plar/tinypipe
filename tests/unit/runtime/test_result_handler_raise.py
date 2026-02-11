from unittest.mock import AsyncMock, MagicMock

import pytest

from justpipe._internal.runtime.orchestration.control import StepCompleted
from justpipe._internal.runtime.execution.result_handler import _ResultHandler
from justpipe._internal.definition.steps import _StandardStep
from justpipe.types import Raise
from tests.unit.fakes import FakeOrchestrator


async def _noop() -> None:
    return None


@pytest.mark.asyncio
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
        owner="step",
        name="step",
        result=Raise(RuntimeError("boom")),
        payload={"k": "v"},
    )

    events = [
        event
        async for event in handler.process_step_result(item, state={"x": 1}, context={})
    ]

    assert events == []
    failure_handler.handle_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_raise_without_exception_is_noop() -> None:
    orchestrator = FakeOrchestrator()
    failure_handler = MagicMock()
    failure_handler.handle_failure = AsyncMock()

    handler = _ResultHandler(
        orchestrator=orchestrator,
        failure_handler=failure_handler,
        scheduler=MagicMock(),
        steps={"step": _StandardStep(name="step", func=_noop)},
    )

    item = StepCompleted(owner="step", name="step", result=Raise(None), payload=None)
    events = [
        event async for event in handler.process_step_result(item, state={}, context={})
    ]

    assert events == []
    failure_handler.handle_failure.assert_not_awaited()
