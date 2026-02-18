from typing import Any, TYPE_CHECKING
import traceback
import logging

from justpipe._internal.runtime.orchestration.control import InvocationContext
from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.definition.steps import _BaseStep
from justpipe.types import EventType, NodeKind, PipelineCancelled

if TYPE_CHECKING:
    from justpipe._internal.runtime.orchestration.protocols import (
        FailureHandlingOrchestrator,
    )


class _FailureHandler:
    """Manages error escalation and reporting."""

    def __init__(
        self,
        steps: dict[str, _BaseStep],
        invoker: _StepInvoker[Any, Any],
        orchestrator: "FailureHandlingOrchestrator",
    ):
        self._steps = steps
        self._invoker = invoker
        self._orchestrator = orchestrator

    async def handle_failure(
        self,
        name: str,
        owner: str,
        error: Exception,
        payload: dict[str, Any] | None = None,
        state: Any | None = None,
        context: Any | None = None,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        """Centralized error handling logic with escalation."""
        step = self._steps.get(name)
        local_handler = step.on_error if step else None

        # 1. Try Local Handler
        if local_handler:
            try:
                res = await self._invoker.execute_handler(
                    local_handler, error, name, state, context, is_global=False
                )
                await self._orchestrator.complete_step(
                    name=name,
                    owner=owner,
                    result=res,
                    payload=payload,
                    track_owner=track_owner,
                    invocation=invocation,
                    step_meta=step_meta,
                )
                return
            except Exception as new_error:
                # Local handler failed, escalate to global
                error = new_error

        # 2. Try Global Handler
        global_handler = self._invoker.global_error_handler
        if global_handler:
            try:
                res = await self._invoker.execute_handler(
                    global_handler, error, name, state, context, is_global=True
                )
                await self._orchestrator.complete_step(
                    name=name,
                    owner=owner,
                    result=res,
                    payload=payload,
                    track_owner=track_owner,
                    invocation=invocation,
                    step_meta=step_meta,
                )
                return
            except Exception as final_error:
                error = final_error

        # 3. Default Reporting (Terminal)
        if isinstance(error, PipelineCancelled):
            self._orchestrator.stop()
            await self._orchestrator.emit(
                EventType.CANCELLED,
                name,
                str(error),
                node_kind=invocation.node_kind if invocation else NodeKind.STEP,
                invocation_id=invocation.invocation_id if invocation else None,
                parent_invocation_id=(
                    invocation.parent_invocation_id if invocation else None
                ),
                owner_invocation_id=(
                    invocation.owner_invocation_id if invocation else None
                ),
                attempt=invocation.attempt if invocation else 1,
                scope=invocation.scope if invocation else (),
            )
            # Complete the step without emitting STEP_ERROR.
            await self._orchestrator.complete_step(
                name=name,
                owner=owner,
                result=None,
                payload=None,
                track_owner=track_owner,
                invocation=invocation,
                already_terminal=True,
                step_meta=step_meta,
            )
            return
        self._log_error(name, error, state)
        await self._report_error(
            name,
            owner,
            error,
            track_owner=track_owner,
            invocation=invocation,
            step_meta=step_meta,
        )

    async def _report_error(
        self,
        name: str,
        owner: str,
        error: Exception,
        track_owner: bool,
        invocation: InvocationContext | None = None,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        await self._orchestrator.fail_step(
            name=name,
            owner=owner,
            error=error,
            track_owner=track_owner,
            invocation=invocation,
            step_meta=step_meta,
        )

    def _log_error(self, name: str, error: Exception, state: Any | None) -> None:
        stack = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        state_str = str(state)[:1000]
        logging.error(
            "Step '%s' failed with %s: %s\nState: %s\nStack trace:\n%s",
            name,
            type(error).__name__,
            error,
            state_str,
            stack,
            extra={
                "step_name": name,
                "error_type": type(error).__name__,
                "state_type": type(state).__name__ if state is not None else None,
            },
            exc_info=True,
        )
