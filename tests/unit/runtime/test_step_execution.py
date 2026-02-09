from typing import Any, cast

import pytest

from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.execution.step_execution_coordinator import (
    _StepExecutionCoordinator,
)
from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe.types import EventType, NodeKind


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
    emitted: list[tuple[EventType, str, Any]] = []
    completed: list[
        tuple[
            str, str, Any, dict[str, Any] | None, bool, InvocationContext | None, bool
        ]
    ] = []
    failures: list[tuple[str, str, Exception, Any, Any, InvocationContext | None]] = []
    step_errors = _StepErrorStore()

    async def emit(
        event_type: EventType,
        stage: str,
        payload: Any | None = None,
        **_: Any,
    ) -> None:
        emitted.append((event_type, stage, payload))

    async def complete_step(
        owner: str,
        name: str,
        result: Any,
        payload: dict[str, Any] | None,
        track_owner: bool,
        invocation: InvocationContext | None,
        already_terminal: bool,
    ) -> None:
        completed.append(
            (owner, name, result, payload, track_owner, invocation, already_terminal)
        )

    async def handle_failure(
        name: str,
        owner: str,
        payload: dict[str, Any] | None,
        error: Exception,
        state: Any,
        context: Any,
        invocation: InvocationContext | None,
    ) -> None:
        failures.append((name, owner, error, state, context, invocation))

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        emit=emit,
        complete_step=complete_step,
        handle_failure=handle_failure,
        state_getter=lambda: {"state": 1},
        context_getter=lambda: {"context": 1},
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a", {"x": 1})

    assert emitted == [(EventType.STEP_START, "step_a", None)]
    assert completed[0][0] == "owner_a"
    assert completed[0][1] == "step_a"
    assert completed[0][3] == {"x": 1}
    assert completed[0][4] is True
    assert completed[0][5] is not None
    assert completed[0][6] is False
    assert not failures


@pytest.mark.asyncio
async def test_fail_step_records_error_and_emits_terminal_step() -> None:
    emitted: list[tuple[EventType, str, Any]] = []
    completed: list[
        tuple[
            str, str, Any, dict[str, Any] | None, bool, InvocationContext | None, bool
        ]
    ] = []
    step_errors = _StepErrorStore()

    async def emit(
        event_type: EventType,
        stage: str,
        payload: Any | None = None,
        **_: Any,
    ) -> None:
        emitted.append((event_type, stage, payload))

    async def complete_step(
        owner: str,
        name: str,
        result: Any,
        payload: dict[str, Any] | None,
        track_owner: bool,
        invocation: InvocationContext | None,
        already_terminal: bool,
    ) -> None:
        completed.append(
            (owner, name, result, payload, track_owner, invocation, already_terminal)
        )

    async def handle_failure(
        name: str,
        owner: str,
        payload: dict[str, Any] | None,
        error: Exception,
        state: Any,
        context: Any,
        invocation: InvocationContext | None,
    ) -> None:
        raise AssertionError("handle_failure should not be called in fail_step")

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        emit=emit,
        complete_step=complete_step,
        handle_failure=handle_failure,
        state_getter=lambda: None,
        context_getter=lambda: None,
        step_errors=step_errors,
    )

    err = RuntimeError("x")
    await coordinator.fail_step("owner_a", "step_a", err, track_owner=False)

    assert step_errors.consume("step_a") is err
    assert emitted == [(EventType.STEP_ERROR, "step_a", "x")]
    assert completed == [("owner_a", "step_a", None, None, False, None, True)]


@pytest.mark.asyncio
async def test_execute_step_failure_delegates_to_failure_handler() -> None:
    emitted: list[tuple[EventType, str, Any]] = []
    failures: list[tuple[str, str, Exception, Any, Any, InvocationContext | None]] = []
    step_errors = _StepErrorStore()

    async def emit(
        event_type: EventType,
        stage: str,
        payload: Any | None = None,
        **_: Any,
    ) -> None:
        emitted.append((event_type, stage, payload))

    async def complete_step(
        owner: str,
        name: str,
        result: Any,
        payload: dict[str, Any] | None,
        track_owner: bool,
        invocation: InvocationContext | None,
        already_terminal: bool,
    ) -> None:
        raise AssertionError("complete_step should not be called on failure path")

    async def handle_failure(
        name: str,
        owner: str,
        payload: dict[str, Any] | None,
        error: Exception,
        state: Any,
        context: Any,
        invocation: InvocationContext | None,
    ) -> None:
        failures.append((name, owner, error, state, context, invocation))

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerFailure()),
        emit=emit,
        complete_step=complete_step,
        handle_failure=handle_failure,
        state_getter=lambda: {"s": 1},
        context_getter=lambda: {"c": 1},
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a")

    assert emitted == [(EventType.STEP_START, "step_a", None)]
    assert len(failures) == 1
    assert failures[0][0] == "step_a"
    assert failures[0][1] == "owner_a"
    assert isinstance(failures[0][2], ValueError)
    assert failures[0][3] == {"s": 1}
    assert failures[0][4] == {"c": 1}
    assert failures[0][5] is not None
