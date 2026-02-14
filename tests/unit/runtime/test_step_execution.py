from dataclasses import dataclass
from typing import Any, cast

import pytest

from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.execution.step_execution_coordinator import (
    _StepExecutionCoordinator,
)
from justpipe._internal.runtime.meta import _current_step_meta_var
from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe.types import EventType, NodeKind


@dataclass
class CompletedCall:
    name: str
    owner: str
    result: Any
    payload: dict[str, Any] | None
    track_owner: bool
    invocation: InvocationContext | None
    already_terminal: bool
    step_meta: dict[str, Any] | None


@dataclass
class FailureCall:
    name: str
    owner: str
    error: Exception
    state: Any
    context: Any
    invocation: InvocationContext | None
    step_meta: dict[str, Any] | None


class _FakeCoordinatorPort:
    """Minimal fake satisfying CoordinatorOrchestrator."""

    def __init__(self, state: Any = None, context: Any = None):
        self.emitted: list[tuple[EventType, str, Any]] = []
        self.completed: list[CompletedCall] = []
        self.failures: list[FailureCall] = []
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
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        self.completed.append(
            CompletedCall(
                name=name,
                owner=owner,
                result=result,
                payload=payload,
                track_owner=track_owner,
                invocation=invocation,
                already_terminal=already_terminal,
                step_meta=step_meta,
            )
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
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        self.failures.append(
            FailureCall(
                name=name,
                owner=owner,
                error=error,
                state=state,
                context=context,
                invocation=invocation,
                step_meta=step_meta,
            )
        )


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


class _InvokerWithMeta:
    """Invoker that writes step meta during execution."""

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
        # Write to the step meta contextvar
        meta = _current_step_meta_var.get()
        if meta is not None:
            meta.set("model", "gpt-4")
            meta.record_metric("latency", 1.5)
        return None


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


class _InvokerFailureWithMeta:
    """Invoker that writes step meta then fails."""

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
        meta = _current_step_meta_var.get()
        if meta is not None:
            meta.set("partial", True)
            meta.increment("processed", 3)
        raise ValueError("boom after meta")


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
    assert port.completed[0].name == "step_a"
    assert port.completed[0].owner == "owner_a"
    assert port.completed[0].payload == {"x": 1}
    assert port.completed[0].track_owner is True
    assert port.completed[0].invocation is not None
    assert port.completed[0].already_terminal is False
    assert not port.failures


@pytest.mark.asyncio
async def test_execute_step_captures_step_meta() -> None:
    """Step meta written during execution is captured and passed to complete_step."""
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort(state=None, context=None)
    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerWithMeta()),
        orch=port,
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a")

    assert len(port.completed) == 1
    assert port.completed[0].step_meta is not None
    assert port.completed[0].step_meta["data"]["model"] == "gpt-4"
    assert port.completed[0].step_meta["metrics"]["latency"] == [1.5]


@pytest.mark.asyncio
async def test_execute_step_no_meta_written_passes_none() -> None:
    """When no step meta is written, step_meta is None."""
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort(state=None, context=None)
    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        orch=port,
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a")

    assert len(port.completed) == 1
    assert port.completed[0].step_meta is None


@pytest.mark.asyncio
async def test_fail_step_records_error_and_emits_terminal_step() -> None:
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort()

    async def _raise_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError(
            "handle_execution_failure should not be called in fail_step"
        )

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
    assert port.completed == [
        CompletedCall(
            name="step_a",
            owner="owner_a",
            result=None,
            payload=None,
            track_owner=False,
            invocation=None,
            already_terminal=True,
            step_meta=None,
        )
    ]


@pytest.mark.asyncio
async def test_fail_step_with_step_meta() -> None:
    """fail_step passes step_meta to STEP_ERROR emit and complete_step."""
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort()

    async def _raise_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("handle_execution_failure should not be called")

    port.handle_execution_failure = _raise_if_called  # type: ignore[method-assign]

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerSuccess()),
        orch=port,
        step_errors=step_errors,
    )

    meta = {"data": {"partial": True}}
    await coordinator.fail_step("step_a", "owner_a", RuntimeError("x"), step_meta=meta)

    # step_meta passed through to complete_step
    assert port.completed[0].step_meta == meta


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
    assert port.failures[0].name == "step_a"
    assert port.failures[0].owner == "owner_a"
    assert isinstance(port.failures[0].error, ValueError)
    assert port.failures[0].state == {"s": 1}
    assert port.failures[0].context == {"c": 1}
    assert port.failures[0].invocation is not None


@pytest.mark.asyncio
async def test_execute_step_failure_carries_partial_step_meta() -> None:
    """When a step fails after writing meta, the partial meta is passed to handle_execution_failure."""
    step_errors = _StepErrorStore()
    port = _FakeCoordinatorPort(state=None, context=None)

    async def _raise_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("complete_step should not be called on failure path")

    port.complete_step = _raise_if_called  # type: ignore[method-assign]

    coordinator = _StepExecutionCoordinator[Any, Any](
        invoker=cast(Any, _InvokerFailureWithMeta()),
        orch=port,
        step_errors=step_errors,
    )

    await coordinator.execute_step("step_a", "owner_a")

    assert len(port.failures) == 1
    assert port.failures[0].step_meta is not None
    assert port.failures[0].step_meta["data"]["partial"] is True
    assert port.failures[0].step_meta["counters"]["processed"] == 3
