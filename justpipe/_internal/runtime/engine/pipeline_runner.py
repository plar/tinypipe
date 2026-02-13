from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import replace
from typing import (
    Any,
    TypeVar,
    Generic,
)
from collections.abc import AsyncGenerator, Awaitable, Callable

from justpipe._internal.runtime.orchestration.control import (
    InvocationContext,
    RuntimeEvent,
    StepCompleted,
)
from justpipe._internal.runtime.orchestration.barrier_manager import _BarrierManager
from justpipe._internal.runtime.telemetry.execution_log import (
    _TerminalSignal,
    _resolve_outcome,
)
from justpipe._internal.runtime.telemetry.failure_journal import _FailureJournal
from justpipe._internal.runtime.failure.failure_handler import _FailureHandler
from justpipe._internal.runtime.orchestration.orchestrator import _Orchestrator
from justpipe._internal.runtime.orchestration.event_publisher import (
    make_event_publisher,
)
from justpipe._internal.runtime.engine.run_context import _RunContext
from justpipe._internal.runtime.engine.composition import RunnerConfig, RunnerDeps
from justpipe._internal.runtime.execution.result_handler import _ResultHandler
from justpipe._internal.runtime.telemetry.runtime_metrics import _RuntimeMetricsRecorder
from justpipe._internal.runtime.execution.scheduler import _Scheduler
from justpipe._internal.runtime.execution.step_error_store import _StepErrorStore
from justpipe._internal.runtime.execution.step_execution_coordinator import (
    _StepExecutionCoordinator,
)
from justpipe._internal.runtime.meta import detect_and_init_meta
from justpipe._internal.types import _Map, _Run
from justpipe._internal.shared.utils import _resolve_name
from justpipe.types import (
    Event,
    EventType,
    FailureKind,
    FailureReason,
    FailureSource,
    NodeKind,
    PipelineEndData,
)

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _PipelineRunner(Generic[StateT, ContextT]):
    """Pipeline phase engine — owns lifecycle orchestration, not protocol methods."""

    def __init__(
        self,
        config: RunnerConfig[StateT, ContextT],
        deps: RunnerDeps[StateT, ContextT] | None = None,
    ):
        if deps is None:
            from justpipe._internal.runtime.engine.composition import build_runner_deps

            deps = build_runner_deps(config)

        self._pipe_name = config.pipe_name
        self._cancellation_token = config.cancellation_token
        self._pipe_metadata = config.pipe_metadata
        self._journal = _FailureJournal(config.failure_classification)
        self._plan = deps.plan

        # Mutable per-run state
        self._ctx: _RunContext[StateT, ContextT] = _RunContext()
        self._step_errors = _StepErrorStore()
        self._pending_owner_invocations: dict[str, list[InvocationContext]] = (
            defaultdict(list)
        )

        # Components
        self._tracker = deps.tracker
        self._events = deps.events
        self._lifecycle = deps.lifecycle
        self._invoker = deps.invoker
        self._graph = deps.graph
        self._queue = deps.queue
        self._kernel = deps.kernel

        # Metrics
        self._metrics = _RuntimeMetricsRecorder()
        self._kernel.set_hooks(
            on_spawn=self._metrics.record_task_spawn,
            on_submit_queue_depth=self._metrics.record_queue_depth,
        )

        # Runtime coordination
        self._publish: Callable[[Event], Awaitable[Event]] = make_event_publisher(
            notify_event=self._events.notify_event,
            apply_hooks=self._events.apply_hooks,
            state_getter=lambda: self._ctx.state,
            prepare_event=self._prepare_event,
            on_event=self._metrics.on_event,
        )
        # Build orchestrator first (needed by step_execution lambdas)
        # We use a two-phase init: create orchestrator, then set step_execution.
        self._failure_handler = _FailureHandler(
            self._plan.steps,
            self._invoker,
            None,  # type: ignore[arg-type]
        )
        self._orch: _Orchestrator[StateT, ContextT] = _Orchestrator(
            ctx=self._ctx,
            kernel=self._kernel,
            tracker=self._tracker,
            step_execution=None,  # type: ignore[arg-type]
            failure_handler=self._failure_handler,
            metrics=self._metrics,
        )
        self._failure_handler._orchestrator = self._orch
        self._step_execution = _StepExecutionCoordinator[StateT, ContextT](
            invoker=self._invoker,
            orch=self._orch,
            step_errors=self._step_errors,
        )
        self._orch._step_execution = self._step_execution

        self._barriers = _BarrierManager(
            self._orch,
            self._graph,
            self._failure_handler,
            self._plan.parents_map,
        )
        self._scheduler = _Scheduler(
            self._orch,
            self._failure_handler,
            self._plan.steps,
            self._plan.injection_metadata,
        )
        self._results = _ResultHandler(
            self._orch,
            self._failure_handler,
            self._scheduler,
            self._plan.steps,
        )

    async def _process_queue(self) -> AsyncGenerator[Event, None]:
        while self._tracker.is_active:
            item = await self._queue.get()

            if isinstance(item, RuntimeEvent):
                async for ev in self._handle_event(item.event):
                    yield ev
            elif isinstance(item, StepCompleted):
                async for ev in self._handle_result(item):
                    yield ev

    def _prepare_event(self, event: Event) -> Event:
        # Stream ownership is always the current runner's run id.
        run_id = self._ctx.run_id
        # Preserve original producer when forwarding across sub-pipelines.
        origin_run_id = event.origin_run_id or event.run_id or run_id
        seq = event.seq if event.seq is not None else self._ctx.next_event_seq()
        return replace(
            event,
            run_id=run_id,
            origin_run_id=origin_run_id,
            seq=seq,
        )

    async def _handle_event(self, item: Event) -> AsyncGenerator[Event, None]:
        yield await self._publish(item)
        if item.type == EventType.SUSPEND:
            self._tracker.request_stop()

    async def _handle_result(self, item: StepCompleted) -> AsyncGenerator[Event, None]:
        self._tracker.record_physical_completion()
        self._metrics.record_task_completion(self._tracker.total_active_tasks)

        async for event in self._results.process_step_result(
            item,
            self._ctx.state,
            self._ctx.context,
        ):
            yield await self._publish(event)

        for completion in self._scheduler.on_step_completed(item.owner, item.name):
            map_complete = Event(
                EventType.MAP_COMPLETE,
                item.owner,
                completion,
                node_kind=NodeKind.MAP,
                invocation_id=completion.get("owner_invocation_id"),
                owner_invocation_id=completion.get("owner_invocation_id"),
                scope=tuple(completion.get("owner_scope", ())),
            )
            yield await self._publish(map_complete)

        deferred_owner = (
            isinstance(item.result, (_Map, _Run)) and item.name == item.owner
        )
        if deferred_owner and item.invocation is not None:
            self._pending_owner_invocations[item.owner].append(item.invocation)

        if (
            item.invocation is not None
            and item.name != item.owner
            and not item.already_terminal
        ):
            worker_end = Event(
                EventType.STEP_END,
                item.name,
                self._ctx.state,
                node_kind=item.invocation.node_kind,
                invocation_id=item.invocation.invocation_id,
                parent_invocation_id=item.invocation.parent_invocation_id,
                owner_invocation_id=item.invocation.owner_invocation_id,
                attempt=item.invocation.attempt,
                scope=item.invocation.scope,
            )
            yield await self._publish(worker_end)

        if item.track_owner and self._tracker.record_logical_completion(item.owner):
            owner_invocation: InvocationContext | None = None
            owner_pending = self._pending_owner_invocations.get(item.owner)
            if owner_pending:
                owner_invocation = owner_pending.pop(0)
                if not owner_pending:
                    self._pending_owner_invocations.pop(item.owner, None)
            elif item.name == item.owner:
                owner_invocation = item.invocation

            emit_owner_terminal = owner_invocation is not None and not (
                owner_invocation == item.invocation and item.already_terminal
            )
            if emit_owner_terminal and owner_invocation is not None:
                end_event = Event(
                    EventType.STEP_END,
                    item.owner,
                    self._ctx.state,
                    node_kind=owner_invocation.node_kind,
                    invocation_id=owner_invocation.invocation_id,
                    parent_invocation_id=owner_invocation.parent_invocation_id,
                    owner_invocation_id=owner_invocation.owner_invocation_id,
                    attempt=owner_invocation.attempt,
                    scope=owner_invocation.scope,
                )
                yield await self._publish(end_event)
            self._barriers.handle_completion(item.owner)

    async def _startup_phase(
        self,
        start: str | Callable[..., Any] | None,
    ) -> tuple[set[str], Event | None]:
        log = self._ctx.log
        self._ctx.runtime_sm.start_startup()
        state = self._ctx.state
        context = self._ctx.context
        await self._events.notify_start(state, context, run_id=self._ctx.run_id)

        error_event = await self._lifecycle.execute_startup(state, context)
        if error_event:
            error_message = f"Startup hook failed: {error_event.payload}"
            self._journal.record_failure(
                log,
                kind=FailureKind.STARTUP,
                source=FailureSource.USER_CODE,
                reason=FailureReason.STARTUP_HOOK_ERROR,
                error_message=error_message,
                error=RuntimeError(error_message),
            )
            return set(), error_event

        if start:
            roots = {_resolve_name(start)}
        else:
            roots = self._plan.roots

        if not roots and not self._plan.steps:
            error_message = "No steps registered"
            self._journal.record_failure(
                log,
                kind=FailureKind.VALIDATION,
                source=FailureSource.FRAMEWORK,
                reason=FailureReason.NO_STEPS,
                error_message=error_message,
                error=RuntimeError(error_message),
            )
            error_event = Event(
                EventType.STEP_ERROR,
                "system",
                "No steps registered",
                node_kind=NodeKind.SYSTEM,
            )
            return set(), error_event

        return roots, None

    async def _execute_pipeline(
        self,
        roots: set[str],
        timeout: float | None,
    ) -> AsyncGenerator[Event, None]:
        log = self._ctx.log
        log.mark_started()
        self._ctx.runtime_sm.start_execution()
        timeout_cm = asyncio.timeout(timeout) if timeout is not None else nullcontext()
        try:
            try:
                async with timeout_cm:
                    async with asyncio.TaskGroup() as tg:
                        self._kernel.attach_task_group(tg)
                        for root in roots:
                            self._orch.schedule(root)

                        async for event in self._process_queue():
                            if event.type == EventType.CANCELLED:
                                log.mark_cancelled()
                                log.signal_terminal(
                                    _TerminalSignal.CANCELLED,
                                    FailureReason.CANCELLED,
                                )
                            if event.type == EventType.STEP_ERROR:
                                error_message = str(event.payload)
                                source_error = self._step_errors.consume(event.stage)
                                self._journal.record_failure(
                                    log,
                                    kind=FailureKind.STEP,
                                    source=FailureSource.USER_CODE,
                                    reason=FailureReason.STEP_ERROR,
                                    error_message=error_message,
                                    step=event.stage,
                                    error=source_error or RuntimeError(error_message),
                                )
                            yield event
            except TimeoutError:
                log.signal_terminal(_TerminalSignal.TIMEOUT, FailureReason.TIMEOUT)
                timeout_event = Event(
                    EventType.TIMEOUT,
                    "system",
                    f"Pipeline exceeded timeout of {timeout}s",
                    node_kind=NodeKind.SYSTEM,
                )
                yield await self._publish(timeout_event)
        finally:
            self._kernel.attach_task_group(None)

    async def _handle_generator_exit(self) -> None:
        self._ctx.log.mark_closing()
        self._ctx.log.signal_terminal(
            _TerminalSignal.CLIENT_CLOSED, FailureReason.CLIENT_CLOSED
        )

    async def _handle_cancel(self) -> None:
        self._ctx.log.mark_closing()
        self._ctx.log.mark_cancelled()
        self._ctx.log.signal_terminal(
            _TerminalSignal.CANCELLED, FailureReason.CANCELLED
        )

    def _handle_runtime_error(self, exc: Exception) -> None:
        self._journal.record_failure(
            self._ctx.log,
            kind=FailureKind.INFRA,
            source=FailureSource.FRAMEWORK,
            reason=FailureReason.INTERNAL_ERROR,
            error_message=str(exc),
            error=exc,
        )

    async def _shutdown_and_finish(self) -> AsyncGenerator[Event, None]:
        log = self._ctx.log
        state = self._ctx.state
        context = self._ctx.context

        # Cancel and clear orphaned barrier tasks to prevent leaks.
        if log.execution_started:
            self._barriers.stop()

        if log.closing or self._ctx.closing:
            # Run shutdown hooks for cleanup, but suppress yielded events.
            async for _ in self._lifecycle.execute_shutdown(state, context):
                pass
            return

        # Always run shutdown hooks, even if startup failed.
        self._ctx.runtime_sm.start_shutdown()
        async for ev in self._lifecycle.execute_shutdown(state, context):
            if ev.type == EventType.STEP_ERROR:
                error_message = f"Shutdown hook failed: {ev.payload}"
                self._journal.record_failure(
                    log,
                    kind=FailureKind.SHUTDOWN,
                    source=FailureSource.USER_CODE,
                    reason=FailureReason.SHUTDOWN_HOOK_ERROR,
                    error_message=error_message,
                    error=RuntimeError(error_message),
                )
            yield await self._publish(ev)

        resolved = _resolve_outcome(log)
        terminal = self._ctx.session.close(
            status=resolved.status,
            error=str(resolved.pipeline_error) if resolved.pipeline_error else None,
            reason=resolved.reason,
        )
        self._ctx.runtime_sm.finish_terminal()
        user_meta = self._ctx.meta_impl._snapshot() if self._ctx.meta_impl else None
        finish_event = Event(
            EventType.FINISH,
            "system",
            PipelineEndData(
                status=terminal.status,
                duration_s=terminal.duration_s,
                error=terminal.error,
                reason=terminal.reason,
                failure_kind=resolved.failure_kind,
                failure_source=resolved.failure_source,
                failed_step=resolved.failed_step,
                errors=list(resolved.errors),
                metrics=self._metrics.snapshot(),
                user_meta=user_meta or None,
            ),
            node_kind=NodeKind.SYSTEM,
        )
        yield await self._publish(finish_event)

        if resolved.pipeline_error:
            await self._events.notify_error(resolved.pipeline_error, state)
        else:
            await self._events.notify_end(state, terminal.duration_s)

    async def _event_stream(
        self,
        state: StateT,
        context: ContextT | None,
        start: str | Callable[..., Any] | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[Event, None]:
        self._ctx = _RunContext(state=state, context=context)
        self._pending_owner_invocations.clear()

        # Detect and initialize Meta on user's context
        self._ctx.meta_impl = detect_and_init_meta(context, self._pipe_metadata)

        # Update orchestrator's context reference for this run
        self._orch._ctx = self._ctx

        try:
            roots, error_event = await self._startup_phase(start)
            if error_event:
                yield await self._publish(error_event)
                return

            start_event = Event(
                EventType.START,
                "system",
                self._ctx.state,
                node_kind=NodeKind.SYSTEM,
            )
            yield await self._publish(start_event)

            async for ev in self._execute_pipeline(roots, timeout):
                yield ev
        except GeneratorExit:
            await self._handle_generator_exit()
            raise
        except asyncio.CancelledError:
            await self._handle_cancel()
            raise
        except Exception as e:
            self._handle_runtime_error(e)
            raise
        finally:
            async for ev in self._shutdown_and_finish():
                yield ev

    async def run(
        self,
        state: StateT,
        context: ContextT | None = None,
        start: str | Callable[..., Any] | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the pipeline and apply event hooks to the stream."""
        stream = self._event_stream(state, context, start, timeout)
        try:
            async for event in stream:
                yield event
        except GeneratorExit:
            self._ctx.closing = True
            raise
