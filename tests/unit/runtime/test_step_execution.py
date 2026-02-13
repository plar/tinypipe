from typing import Any, cast

import pytest

from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.execution.step_execution_coordinator import (
    _StepExecutionCoordinator,
)
from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe.types import EventType, NodeKind


class _FakeCoordinatorPort:
    """Minimal fake satisfying CoordinatorOrchestrator."""

    def __init__(self, state: Any = None, context: Any = None):
        self.emitted: list[tuple[EventType, str, Any]] = []
        self.completed: list[
            tuple[
                str, str, Any, dict[str, Any] | None, bool, InvocationContext | None, bool
            ]
        ] = []
        self.failures: list[tuple[str, str, Exception, Any, Any, InvocationContext | None]] = []
        self._state = state
        self._context = context

    @property
    def state(self) -> Any:
        return self._state

    @property
    def context(self) -> Any:
        return self._context

    async def emit(
        self,
        event_type: EventType,
        stage: str,
        payload: Any = None,
        **_: Any,
    ) -> None:
        self.emitted.append((event_type, stage, payload))

    async def complete_step(
        self,
        name: str,
        owner: str,
        result: Any,
        payload: dict[str, Any] | None = None,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
        already_terminal: bool = False,
    ) -> None:
        self.completed.append(
            (name, owner, result, payload, track_owner, invocation, already_terminal)
        )

    async def handle_execution_failure(
        self,
        name: str,
        owner: str,
        error: Exception,
        payload: dict[str, Any] | None = None,
        state: Any = None,
        context: Any = None,
        invocation: InvocationContext | None = None,
    ) -> None:
        self.failures.append((name, owner, error, state, context, invocation))


class _InvokerSuccess:
    def get_node_kind(self, name: str) -> NodeKind:
        return NodeKind.STEP

    async def execute(
        self,
        name: str,
        orchestrator: Any,
        state: Any,
        context: Any,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return {"ok": True, "name": name, "payload": payload}


class _InvokerFailure:
    def get_node_kind(self, name: str) -> NodeKind:
        return NodeKind.STEP

    async def execute(
        self,
        name: str,
        orchestrator: Any,
        state: Any,
        context: Any,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        raise ValueError("boom")


@pytest.mark.asyncio
async def test_execute_step_emits_start_and_completes() -> None:
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort(state={"state": 1}, context={"context": 1})
    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        orch=port,
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a", {"x": 1})

    assert port.emitted == [(EventType.STEP_START, "step_a", None)]
    assert port.completed[0][0] == "step_a"
    assert port.completed[0][1] == "owner_a"
    assert port.completed[0][3] == {"x": 1}
    assert port.completed[0][4] is True
    assert port.completed[0][5] is not None
    assert port.completed[0][6] is False
    assert not port.failures


@pytest.mark.asyncio
async def test_fail_step_records_error_and_emits_terminal_step() -> None:
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort()

    async def _raise_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("handle_execution_failure should not be called in fail_step")

    port.handle_execution_failure = _raise_if_called  # type: ignore[method-assign]

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        orch=port,
        step_errors=step_errors,
    )

    err = RuntimeError("x")
    await coordinator.fail_step("step_a", "owner_a", err, track_owner=False)

    assert step_errors.consume("step_a") is err
    assert port.emitted == [(EventType.STEP_ERROR, "step_a", "x")]
    assert port.completed == [("step_a", "owner_a", None, None, False, None, True)]


@pytest.mark.asyncio
async def test_execute_step_failure_delegates_to_failure_handler() -> None:
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort(state={"s": 1}, context={"c": 1})

    async def _raise_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("complete_step should not be called on failure path")

    port.complete_step = _raise_if_called  # type: ignore[method-assign]

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerFailure()),
        orch=port,
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a")

    assert port.emitted == [(EventType.STEP_START, "step_a", None)]
    assert len(port.failures) == 1
    assert port.failures[0][0] == "step_a"
    assert port.failures[0][1] == "owner_a"
    assert isinstance(port.failures[0][2], ValueError)
    assert port.failures[0][3] == {"s": 1}
    assert port.failures[0][4] == {"c": 1}
    assert port.failures[0][5] is not None
