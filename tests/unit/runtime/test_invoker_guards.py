from typing import Any

import pytest

from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.definition.steps import _StandardStep
from tests.unit.fakes import FakeOrchestrator


async def _noop(**_: Any) -> None:
    return None


async def test_execute_rejects_empty_step_name() -> None:
    invoker: _StepInvoker[Any, Any] = _StepInvoker(steps={}, injection_metadata={})

    with pytest.raises(ValueError, match="Step name cannot be empty"):
        await invoker.execute("", FakeOrchestrator(), state=None, context=None)


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


@pytest.mark.parametrize(
    "bad_name, expected_pattern",
    [
        ("alpah", r"Did you mean 'alpha'\?"),
        ("zzzz", r"Did you forget to decorate with @pipe\.step\(\)\?"),
    ],
    ids=["close_match_suggestion", "no_match_fallback"],
)
async def test_execute_unknown_step_error_message(
    bad_name: str, expected_pattern: str
) -> None:
    step = _StandardStep(name="alpha", func=_noop)
    invoker: _StepInvoker[Any, Any] = _StepInvoker(
        steps={"alpha": step}, injection_metadata={}
    )

    with pytest.raises(ValueError, match=expected_pattern):
        await invoker.execute(bad_name, FakeOrchestrator(), state=None, context=None)


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
