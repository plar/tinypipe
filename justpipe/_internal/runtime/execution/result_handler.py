import warnings
from typing import Any, TYPE_CHECKING
from collections.abc import AsyncGenerator

from justpipe.types import (
    Event,
    EventType,
    NodeKind,
    Raise,
    Retry,
    Skip,
    Stop,
    Suspend,
    _Map,
    _Next,
    _Run,
)
from justpipe._internal.runtime.orchestration.control import StepCompleted
from justpipe._internal.shared.utils import _resolve_name

if TYPE_CHECKING:
    from justpipe._internal.runtime.orchestration.protocols import ResultOrchestrator
    from justpipe._internal.runtime.failure.failure_handler import _FailureHandler
    from justpipe._internal.definition.steps import _BaseStep
    from justpipe._internal.runtime.execution.scheduler import _Scheduler


class _ResultHandler:
    """Internal handler for processing step execution results."""

    def __init__(
        self,
        orchestrator: "ResultOrchestrator",
        failure_handler: "_FailureHandler",
        scheduler: "_Scheduler",
        steps: dict[str, "_BaseStep"],
        max_retries: int = 100,
    ):
        self._orchestrator = orchestrator
        self._failure_handler = failure_handler
        self._scheduler = scheduler
        self._steps = steps
        self._max_retries = max_retries

    async def process_step_result(
        self, item: StepCompleted, state: Any, context: Any
    ) -> AsyncGenerator[Event, None]:
        """Determine next action based on step return value."""
        res = item.result
        inv = item.invocation

        if isinstance(res, Raise):
            error = res.exception or RuntimeError(
                f"Step '{item.name}' returned Raise() without an exception"
            )
            await self._failure_handler.handle_failure(
                item.name,
                item.owner,
                error,
                item.payload,
                state,
                context,
            )
            return

        if isinstance(res, Skip):
            self._orchestrator.tracker.mark_skipped(item.owner)
            return

        if isinstance(res, Retry):
            attempt = inv.attempt if inv else 1
            if attempt >= self._max_retries:
                warnings.warn(
                    f"Step '{item.name}' exceeded max retries ({self._max_retries}). Treating as error.",
                    UserWarning,
                    stacklevel=2,
                )
                await self._failure_handler.handle_failure(
                    item.name,
                    item.owner,
                    RuntimeError(
                        f"Step '{item.name}' exceeded max retries ({self._max_retries})"
                    ),
                    item.payload,
                    state,
                    context,
                )
                return
            self._orchestrator.schedule(
                item.name,
                owner=item.owner,
                payload=item.payload,
                parent_invocation_id=inv.invocation_id if inv else None,
                owner_invocation_id=inv.owner_invocation_id if inv else None,
                scope=inv.scope if inv else (),
            )
            return

        if res is Stop or isinstance(res, Stop):
            self._orchestrator.stop()
            return

        if isinstance(res, str):
            res = _Next(res)

        # Dynamic Override:
        # If a standard step explicitly returns a next step (dynamic routing),
        # we skip the static topology transitions for this step.
        step = self._steps.get(item.owner)
        if step and step.get_kind() == NodeKind.STEP:
            if isinstance(res, _Next) and res.target is not None:
                self._orchestrator.tracker.mark_skipped(item.owner)

        if isinstance(res, Suspend):
            yield Event(EventType.SUSPEND, item.name, res.reason)
            self._orchestrator.stop()
        elif isinstance(res, _Next) and res.target is not None:
            self._orchestrator.schedule(
                _resolve_name(res.target),
                parent_invocation_id=inv.invocation_id if inv else None,
                scope=inv.scope if inv else (),
            )
        elif isinstance(res, _Map):
            await self._scheduler.handle_map(res, item.owner, item.invocation)
        elif isinstance(res, _Run):
            self._orchestrator.spawn(
                self._scheduler.sub_pipe_wrapper(
                    res.pipe,
                    res.state,
                    item.owner,
                    context,
                    item.invocation,
                ),
                item.owner,
            )
        elif res is not None:
            # Unexpected return type - likely a mistake
            warnings.warn(
                f"Step '{item.name}' returned {type(res).__name__} ({repr(res)}), "
                f"which will be ignored. "
                f"Valid return values: step names (str), Stop, or Suspend. "
                f"To pass data: mutate state, use context, external storage, or yield for streaming.",
                UserWarning,
                stacklevel=2,
            )
