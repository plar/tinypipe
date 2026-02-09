from __future__ import annotations

from typing import Any, Generic, TypeVar
from collections.abc import Awaitable, Callable

from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe.types import EventType, NodeKind

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _EmitPort:
    def __init__(
        self,
        emit: Callable[..., Awaitable[None]],
    ):
        self._emit = emit

    async def emit(
        self,
        event_type: EventType,
        stage: str,
        payload: Any = None,
        *,
        node_kind: NodeKind = NodeKind.STEP,
        invocation_id: str | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        attempt: int = 1,
        scope: tuple[str, ...] = (),
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self._emit(
            event_type,
            stage,
            payload,
            node_kind=node_kind,
            invocation_id=invocation_id,
            parent_invocation_id=parent_invocation_id,
            owner_invocation_id=owner_invocation_id,
            attempt=attempt,
            scope=scope,
            meta=meta,
        )


class _StepExecutionCoordinator(Generic[StateT, ContextT]):
    """Encapsulates step execution and default error completion behavior."""

    def __init__(
        self,
        *,
        invoker: _StepInvoker[StateT, ContextT],
        emit: Callable[..., Awaitable[None]],
        complete_step: Callable[
            [
                str,
                str,
                Any,
                dict[str, Any] | None,
                bool,
                InvocationContext | None,
                bool,
            ],
            Awaitable[None],
        ],
        handle_failure: Callable[
            [
                str,
                str,
                dict[str, Any] | None,
                Exception,
                StateT | None,
                ContextT | None,
                InvocationContext | None,
            ],
            Awaitable[None],
        ],
        state_getter: Callable[[], StateT | None],
        context_getter: Callable[[], ContextT | None],
        step_errors: _StepErrorStore,
    ):
        self._invoker = invoker
        self._emit = emit
        self._complete_step = complete_step
        self._handle_failure = handle_failure
        self._state_getter = state_getter
        self._context_getter = context_getter
        self._step_errors = step_errors
        self._invoker_port = _EmitPort(emit)

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
        await self._emit(event_type, stage, payload, **kwargs)

    async def fail_step(
        self,
        owner: str,
        name: str,
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
        await self._complete_step(
            owner,
            name,
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
            result = await self._invoker.execute(
                name,
                self._invoker_port,
                self._state_getter(),
                self._context_getter(),
                payload,
            )
            await self._complete_step(
                owner,
                name,
                result,
                payload,
                True,
                invocation,
                False,
            )
        except Exception as error:
            await self._handle_failure(
                name,
                owner,
                payload,
                error,
                self._state_getter(),
                self._context_getter(),
                invocation,
            )

    def node_kind_for(self, name: str) -> NodeKind:
        return self._invoker.get_node_kind(name)
