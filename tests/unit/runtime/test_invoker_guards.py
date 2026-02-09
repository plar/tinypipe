from typing import Any

import pytest

from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.definition.steps import _StandardStep
from tests.unit.fakes import FakeOrchestrator


async def _noop(**_: Any) -> None:
    return None


@pytest.mark.asyncio
async def test_execute_rejects_empty_step_name() -> None:
    invoker: _StepInvoker[Any, Any] = _StepInvoker(steps={}, injection_metadata={})

    with pytest.raises(ValueError, match="Step name cannot be empty"):
        await invoker.execute("", FakeOrchestrator(), state=None, context=None)


@pytest.mark.asyncio
async def test_execute_rejects_none_orchestrator() -> None:
    invoker: _StepInvoker[Any, Any] = _StepInvoker(steps={}, injection_metadata={})

    with pytest.raises(ValueError, match="Orchestrator cannot be None"):
        await invoker.execute("x", None, state=None, context=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_execute_rejects_non_dict_payload() -> None:
    invoker: _StepInvoker[Any, Any] = _StepInvoker(steps={}, injection_metadata={})

    with pytest.raises(TypeError, match="Payload must be a dict"):
        await invoker.execute(
            "x",
            FakeOrchestrator(),
            state=None,
            context=None,
            payload=[],  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_execute_unknown_step_reports_suggestion() -> None:
    step = _StandardStep(name="alpha", func=_noop)
    invoker: _StepInvoker[Any, Any] = _StepInvoker(
        steps={"alpha": step}, injection_metadata={}
    )

    with pytest.raises(ValueError, match=r"Did you mean 'alpha'\?"):
        await invoker.execute("alpah", FakeOrchestrator(), state=None, context=None)


@pytest.mark.asyncio
async def test_execute_unknown_step_reports_fallback_hint() -> None:
    step = _StandardStep(name="alpha", func=_noop)
    invoker: _StepInvoker[Any, Any] = _StepInvoker(
        steps={"alpha": step}, injection_metadata={}
    )

    with pytest.raises(
        ValueError, match=r"Did you forget to decorate with @pipe.step\(\)\?"
    ):
        await invoker.execute("zzzz", FakeOrchestrator(), state=None, context=None)


@pytest.mark.asyncio
async def test_execute_handler_global_requires_hookspec() -> None:
    invoker: _StepInvoker[Any, Any] = _StepInvoker(steps={}, injection_metadata={})

    with pytest.raises(TypeError, match="Global error hook must be a HookSpec"):
        await invoker.execute_handler(
            handler=lambda **_: None,
            error=RuntimeError("boom"),
            step_name="x",
            state=None,
            context=None,
            is_global=True,
        )
