from __future__ import annotations

from typing import Any, Generic, TypeVar

from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.meta import _current_step_var
from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe._internal.runtime.orchestration.protocols import CoordinatorOrchestrator
from justpipe.types import EventType, NodeKind

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _StepExecutionCoordinator(Generic[StateT, ContextT]):
    """Encapsulates step execution and default error completion behavior."""

    def __init__(
        self,
        *,
        invoker: _StepInvoker[StateT, ContextT],
        orch: CoordinatorOrchestrator,
        step_errors: _StepErrorStore,
    ):
        self._invoker = invoker
        self._orch = orch
        self._step_errors = step_errors

    async def _emit_with_context(
        self,
        event_type: EventType,
        stage: str,
        payload: Any,
        *,
        node_kind: NodeKind,
        invocation: InvocationContext | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "node_kind": node_kind,
            "invocation_id": invocation.invocation_id if invocation else None,
            "parent_invocation_id": (
                invocation.parent_invocation_id if invocation else None
            ),
            "owner_invocation_id": (
                invocation.owner_invocation_id if invocation else None
            ),
            "attempt": invocation.attempt if invocation else 1,
            "scope": invocation.scope if invocation else (),
        }
        await self._orch.emit(event_type, stage, payload, **kwargs)

    async def fail_step(
        self,
        name: str,
        owner: str,
        error: Exception,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
    ) -> None:
        self._step_errors.record(name, error)
        await self._emit_with_context(
            EventType.STEP_ERROR,
            name,
            str(error),
            node_kind=invocation.node_kind if invocation else NodeKind.STEP,
            invocation=invocation,
        )
        await self._orch.complete_step(
            name,
            owner,
            None,
            None,
            track_owner,
            invocation,
            True,
        )

    async def execute_step(
        self,
        name: str,
        owner: str,
        payload: dict[str, Any] | None = None,
        invocation: InvocationContext | None = None,
    ) -> None:
        node_kind = self.node_kind_for(name)
        if invocation is None:
            invocation = InvocationContext(
                invocation_id=f"orphan:{name}",
                node_kind=node_kind,
            )
        try:
            await self._emit_with_context(
                EventType.STEP_START,
                name,
                None,
                node_kind=invocation.node_kind,
                invocation=invocation,
            )
            token = _current_step_var.set(name)
            try:
                result = await self._invoker.execute(
                    name,
                    self._orch,
                    self._orch.state,
                    self._orch.context,
                    payload,
                )
            finally:
                _current_step_var.reset(token)
            await self._orch.complete_step(
                name,
                owner,
                result,
                payload,
                True,
                invocation,
                False,
            )
        except Exception as error:
            await self._orch.handle_execution_failure(
                name,
                owner,
                error,
                payload,
                self._orch.state,
                self._orch.context,
                invocation,
            )

    def node_kind_for(self, name: str) -> NodeKind:
        return self._invoker.get_node_kind(name)
