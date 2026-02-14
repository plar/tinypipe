from __future__ import annotations

import asyncio
from typing import Any, Generic, TypeVar

from justpipe._internal.runtime.orchestration.control import (
    InvocationContext,
    RuntimeEvent,
    StepCompleted,
)
from justpipe._internal.runtime.failure.failure_handler import _FailureHandler
from justpipe._internal.runtime.telemetry.runtime_metrics import _RuntimeMetricsRecorder
from justpipe._internal.runtime.orchestration.protocols import TaskOrchestrator
from justpipe._internal.runtime.engine.run_context import _RunContext
from justpipe._internal.runtime.orchestration.runtime_kernel import _RuntimeKernel
from justpipe._internal.runtime.execution.step_execution_coordinator import (
    _StepExecutionCoordinator,
)
from justpipe._internal.shared.execution_tracker import _ExecutionTracker
from justpipe.types import Event, EventType, NodeKind

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _Orchestrator(Generic[StateT, ContextT], TaskOrchestrator[StateT, ContextT]):
    """Thin protocol implementation — forwarding only, no business logic."""

    def __init__(
        self,
        ctx: _RunContext[StateT, ContextT],
        kernel: _RuntimeKernel,
        tracker: _ExecutionTracker,
        step_execution: _StepExecutionCoordinator[StateT, ContextT],
        failure_handler: _FailureHandler,
        metrics: _RuntimeMetricsRecorder,
    ) -> None:
        self._ctx = ctx
        self._kernel = kernel
        self._tracker = tracker
        self._step_execution = step_execution
        self._failure_handler = failure_handler
        self._metrics = metrics

    # --- StateContextView ---
    @property
    def state(self) -> StateT | None:
        return self._ctx.state

    @property
    def context(self) -> ContextT | None:
        return self._ctx.context

    # --- TrackerView ---
    @property
    def tracker(self) -> _ExecutionTracker:
        return self._tracker

    # --- QueueSubmitPort ---
    async def submit(self, item: RuntimeEvent | StepCompleted) -> None:
        await self._kernel.submit(item)

    # --- EventEmitPort ---
    async def emit(
        self,
        event_type: EventType,
        stage: str,
        payload: Any = None,
        *,
        node_kind: NodeKind = NodeKind.SYSTEM,
        invocation_id: str | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        attempt: int = 1,
        scope: tuple[str, ...] = (),
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.submit(
            RuntimeEvent(
                Event(
                    type=event_type,
                    stage=stage,
                    payload=payload,
                    node_kind=node_kind,
                    invocation_id=invocation_id,
                    parent_invocation_id=parent_invocation_id,
                    owner_invocation_id=owner_invocation_id,
                    attempt=attempt,
                    scope=scope,
                    meta=meta,
                )
            )
        )

    # --- StepCompletionPort ---
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
        await self.submit(
            StepCompleted(
                owner=owner,
                name=name,
                result=result,
                payload=payload,
                track_owner=track_owner,
                invocation=invocation,
                already_terminal=already_terminal,
                step_meta=step_meta,
            )
        )

    # --- StepFailurePort ---
    async def fail_step(
        self,
        name: str,
        owner: str,
        error: Exception,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        await self._step_execution.fail_step(
            name, owner, error, track_owner, invocation=invocation, step_meta=step_meta
        )

    # --- StopPort ---
    def stop(self) -> None:
        self._kernel.request_stop()

    # --- SpawnPort ---
    def spawn(
        self,
        coro: Any,
        owner: str,
        track_owner: bool = True,
    ) -> asyncio.Task[Any] | None:
        return self._kernel.spawn(coro, owner, track_owner)

    # --- SchedulePort ---
    def schedule(
        self,
        name: str,
        owner: str | None = None,
        payload: dict[str, Any] | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None:
        target_owner = owner or name
        self.spawn(
            self.execute_step(
                name,
                target_owner,
                payload,
                parent_invocation_id=parent_invocation_id,
                owner_invocation_id=owner_invocation_id,
                scope=scope,
            ),
            target_owner,
        )

    # --- StepExecutionPort ---
    async def execute_step(
        self,
        name: str,
        owner: str,
        payload: dict[str, Any] | None = None,
        invocation: InvocationContext | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None:
        if invocation is None:
            invocation_id = self._ctx.next_invocation_id()
            resolved_owner_invocation_id = owner_invocation_id or invocation_id
            invocation = InvocationContext(
                invocation_id=invocation_id,
                parent_invocation_id=parent_invocation_id,
                owner_invocation_id=resolved_owner_invocation_id,
                attempt=self._ctx.next_attempt(name),
                scope=scope,
                node_kind=self._step_execution.node_kind_for(name),
            )
        await self._step_execution.execute_step(name, owner, payload, invocation)

    def map_worker_started(self, owner: str, target: str) -> None:
        self._metrics.record_map_worker_started(owner, target)

    def map_worker_finished(self, owner: str, target: str) -> None:
        self._metrics.record_map_worker_finished(owner, target)

    # --- FailureEscalationPort ---
    async def handle_execution_failure(
        self,
        name: str,
        owner: str,
        error: Exception,
        payload: dict[str, Any] | None,
        state: StateT | None,
        context: ContextT | None,
        invocation: InvocationContext | None = None,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        await self._failure_handler.handle_failure(
            name,
            owner,
            error,
            payload,
            state,
            context,
            invocation=invocation,
            step_meta=step_meta,
        )
