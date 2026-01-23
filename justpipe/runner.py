import asyncio
from collections import defaultdict
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
    Generic
)

from justpipe.graph import _DependencyGraph
from justpipe.invoker import _StepInvoker, _StepResult
from justpipe.types import (
    Event,
    EventType,
    Retry,
    Skip,
    Raise,
    Stop,
    Suspend,
    _Map,
    _Next,
    _Run,
    StepConfig,
)

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _PipelineRunner(Generic[StateT, ContextT]):
    """Internal class that handles pipeline execution, event streaming, and worker management."""

    def __init__(
        self,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        injection_metadata: Dict[str, Dict[str, str]],
        step_configs: Dict[str, StepConfig],
        startup_hooks: List[Callable[..., Any]],
        shutdown_hooks: List[Callable[..., Any]],
        on_error: Optional[Callable[..., Any]] = None,
        queue_size: int = 0,
        event_hooks: Optional[List[Callable[[Event], Event]]] = None,
    ):
        self._steps = steps
        self._topology = topology
        self._step_configs = step_configs
        self._startup = startup_hooks
        self._shutdown = shutdown_hooks
        self._event_hooks = event_hooks or []
        self._injection_metadata = injection_metadata

        # Execution state
        self._state: Optional[StateT] = None
        self._context: Optional[ContextT] = None
        self._logical_active: Dict[str, int] = defaultdict(int)
        self._total_active_tasks: int = 0
        self._queue: asyncio.Queue[Union[Event, _StepResult]] = asyncio.Queue(
            maxsize=queue_size
        )
        self._stopping: bool = False
        self._tg: Optional[asyncio.TaskGroup] = None
        self._barrier_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._skipped_owners: Set[str] = set()

        # Components
        self._invoker: _StepInvoker[StateT, ContextT] = _StepInvoker(
            steps, injection_metadata, step_configs, on_error
        )
        self._graph = _DependencyGraph(steps, topology, step_configs)

    async def _execute_startup(self) -> Optional[Event]:
        try:
            for h in self._startup:
                await h(self._context)
        except Exception as e:
            return Event(EventType.ERROR, "startup", str(e))
        return None

    async def _execute_shutdown(self) -> AsyncGenerator[Event, None]:
        for h in self._shutdown:
            try:
                await h(self._context)
            except Exception as e:
                yield Event(EventType.ERROR, "shutdown", str(e))

    def _spawn(self, coro: Any, owner: str) -> None:
        if self._stopping or not self._tg:
            coro.close()
            return
        self._logical_active[owner] += 1
        self._total_active_tasks += 1
        self._tg.create_task(coro)

    async def _report_error(self, name: str, owner: str, error: Exception) -> None:
        await self._queue.put(Event(EventType.ERROR, name, str(error)))
        await self._queue.put(_StepResult(owner, name, None))

    def _schedule(
        self,
        name: str,
        owner: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        target_owner = owner or name
        self._spawn(self._wrapper(name, target_owner, payload), target_owner)

    async def _wrapper(
        self, name: str, owner: str, payload: Optional[Dict[str, Any]]
    ) -> None:
        try:
            await self._queue.put(Event(EventType.STEP_START, name))
            res = await self._invoker.execute(name, self._queue, payload)
            await self._queue.put(_StepResult(owner, name, res, payload))
        except Exception as e:
            await self._handle_step_failure(name, owner, payload, e)

    async def _handle_step_failure(
        self, name: str, owner: str, payload: Optional[Dict[str, Any]], error: Exception
    ) -> None:
        """Centralized error handling logic with escalation."""
        config = self._step_configs.get(name)
        local_handler = config.on_error if config else None
        
        # 1. Try Local Handler
        if local_handler:
            try:
                res = await self._invoker.execute_handler(
                    local_handler, error, name, is_global=False
                )
                await self._queue.put(_StepResult(owner, name, res, payload))
                return
            except Exception as new_error:
                # Local handler failed, escalate to global
                error = new_error

        # 2. Try Global Handler
        global_handler = self._invoker._on_error
        if global_handler:
            try:
                res = await self._invoker.execute_handler(
                    global_handler, error, name, is_global=True
                )
                await self._queue.put(_StepResult(owner, name, res, payload))
                return
            except Exception as final_error:
                error = final_error

        # 3. Default Reporting (Terminal)
        self._log_error(name, error)
        await self._report_error(name, owner, error)

    def _log_error(self, name: str, error: Exception) -> None:
        import traceback
        import time
        import logging

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        stack = traceback.format_exc()
        state_str = str(self._state)[:1000]
        logging.error(
            f"[{timestamp}] Step '{name}' failed with {type(error).__name__}: {error}\n"
            f"State: {state_str}\n"
            f"Stack trace:\n{stack}"
        )

    async def _sub_pipe_wrapper(
        self, sub_pipe: Any, sub_state: Any, owner: str
    ) -> None:
        name = f"{owner}:sub"
        try:
            async for ev in sub_pipe.run(sub_state):
                ev.stage = f"{owner}:{ev.stage}"
                await self._queue.put(ev)
            await self._queue.put(_StepResult(owner, name, None))
        except Exception as e:
            await self._report_error(name, owner, e)

    def _apply_event_hooks(self, event: Event) -> Event:
        """Apply all registered event hooks to transform the event."""
        for hook in self._event_hooks:
            event = hook(event)
        return event

    async def _process_queue(self) -> AsyncGenerator[Event, None]:
        while self._total_active_tasks > 0:
            item = await self._queue.get()

            if isinstance(item, Event):
                yield item
                if item.type == EventType.SUSPEND:
                    self._stopping = True
            elif isinstance(item, _StepResult):
                self._total_active_tasks -= 1
                self._logical_active[item.owner] -= 1

                async for event in self._process_step_result(item):
                    yield event

                if self._logical_active[item.owner] == 0:
                    yield Event(EventType.STEP_END, item.owner, self._state)
                    self._handle_completion(item.owner)

    async def _process_step_result(
        self, item: _StepResult
    ) -> AsyncGenerator[Event, None]:
        res = item.result

        if isinstance(res, Raise):
            if res.exception:
                await self._report_error(item.name, item.owner, res.exception)
            return

        if isinstance(res, Skip):
            self._skipped_owners.add(item.owner)
            return

        if isinstance(res, Retry):
            self._schedule(item.name, owner=item.owner, payload=item.payload)
            return

        if res is Stop:
            self._stopping = True
            return

        if isinstance(res, str):
            res = _Next(res)

        if isinstance(res, Suspend):
            yield Event(EventType.SUSPEND, item.name, res.reason)
            self._stopping = True
        elif isinstance(res, _Next) and res.stage:
            self._schedule(res.stage)
        elif isinstance(res, _Map):
            self._handle_map(res, item.owner)
        elif isinstance(res, _Run):
            if self._tg:
                self._spawn(
                    self._sub_pipe_wrapper(res.pipe, res.state, item.owner), item.owner
                )

    def _handle_map(self, res: _Map, owner: str) -> None:
        for m_item in res.items:
            func = self._steps.get(res.target)
            payload = None
            if func:
                inj = self._injection_metadata.get(res.target, {})
                for p_name, p_source in inj.items():
                    if p_source == "unknown":
                        payload = {p_name: m_item}
                        break
            self._schedule(res.target, owner=owner, payload=payload)

    async def _barrier_timeout_watcher(self, name: str, timeout: float) -> None:
        try:
            await asyncio.sleep(timeout)
            if not self._graph.is_barrier_satisfied(name):
                await self._report_error(
                    name,
                    name,
                    TimeoutError(f"Barrier timeout for step '{name}' after {timeout}s"),
                )
        except asyncio.CancelledError:
            pass

    def _handle_completion(self, owner: str) -> None:
        if owner in self._skipped_owners:
            self._skipped_owners.remove(owner)
            return

        for succ in self._graph.get_successors(owner):
            is_ready, cancel_timeout, schedule_timeout = self._graph.mark_completed(
                owner, succ
            )
            
            if cancel_timeout and succ in self._barrier_tasks:
                self._barrier_tasks[succ].cancel()
                del self._barrier_tasks[succ]
            
            if is_ready:
                self._schedule(succ)
            elif schedule_timeout and self._tg:
                self._barrier_tasks[succ] = self._tg.create_task(
                    self._barrier_timeout_watcher(succ, schedule_timeout)
                )

    async def _execution_stream(
        self,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        """Internal generator for the pipeline lifecycle yielding raw events."""
        try:
            error_event = await self._execute_startup()
            if error_event:
                yield error_event
                return

            roots = self._graph.get_roots(start)
            if not roots and not self._steps:
                yield Event(EventType.ERROR, "system", "No steps registered")
                return

            self._graph.build()
            yield Event(EventType.START, "system", self._state)

            async with asyncio.TaskGroup() as tg:
                self._tg = tg
                for root in roots:
                    self._schedule(root)

                async for event in self._process_queue():
                    yield event
        finally:
            async for ev in self._execute_shutdown():
                yield ev

            yield Event(EventType.FINISH, "system", self._state)

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the pipeline and apply event hooks to the stream."""
        self._state = state
        self._context = context
        self._invoker.set_context(state, context)

        async for event in self._execution_stream(start):
            yield self._apply_event_hooks(event)