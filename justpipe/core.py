import asyncio
import inspect
import warnings
import time
import logging
from dataclasses import dataclass
from collections import defaultdict
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    TypeVar,
    Generic,
    Union,
    get_args,
)

from justpipe.visualization import generate_mermaid_graph
from justpipe.types import (
    Event,
    EventType,
    _Next,
    _Map,
    _Run,
    Suspend,
    Stop,
    _Stop,
    _resolve_name,
    DefinitionError,
    Retry,
    Skip,
    Raise,
    StepContext,
    StepInfo,
)

try:
    from tenacity import retry, stop_after_attempt, wait_exponential

    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

    def retry(  # type: ignore[no-redef]
        *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda f: f

    def stop_after_attempt(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None

    def wait_exponential(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None


STATE_ALIASES: frozenset[str] = frozenset({"s", "state"})
CONTEXT_ALIASES: frozenset[str] = frozenset({"c", "ctx", "context"})
ERROR_ALIASES: frozenset[str] = frozenset({"e", "error", "exception"})
STEP_NAME_ALIASES: frozenset[str] = frozenset({"step_name", "stage"})


def _analyze_signature(
    func: Callable[..., Any],
    state_type: Any,
    context_type: Any,
    expected_unknowns: int = 0,
) -> Dict[str, str]:
    """Analyze function signature and map parameters to state or context."""
    mapping = {}
    sig = inspect.signature(func)
    unknowns = []
    for name, param in sig.parameters.items():
        # 1. Match by Type (skip if type is Any to avoid collisions)
        if param.annotation is state_type and state_type is not Any:
            mapping[name] = "state"
        elif param.annotation is context_type and context_type is not Any:
            mapping[name] = "context"
        # 2. Match by Name (Fallback)
        elif name in STATE_ALIASES:
            mapping[name] = "state"
        elif name in CONTEXT_ALIASES:
            mapping[name] = "context"
        elif name in ERROR_ALIASES:
            mapping[name] = "error"
        elif name in STEP_NAME_ALIASES:
            mapping[name] = "step_name"
        # 3. Handle parameters with default values
        elif param.default is not inspect.Parameter.empty:
            continue
        else:
            mapping[name] = "unknown"
            unknowns.append(name)

    if len(unknowns) > expected_unknowns:
        raise DefinitionError(
            f"Step '{func.__name__}' has {len(unknowns)} unrecognized parameters: {unknowns}. "
            f"Expected {expected_unknowns} unknown parameter(s) for this step type. "
            f"Parameters must be typed as {state_type} or {context_type}, "
            f"or named 'state'/'context'/'error'/'step_name'."
        )

    return mapping


StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")
Middleware = Callable[
    [Callable[..., Any], StepContext],
    Callable[..., Any],
]


def tenacity_retry_middleware(
    func: Callable[..., Any],
    ctx: StepContext,
) -> Callable[..., Any]:
    retries = ctx.kwargs.get("retries", 0)
    if not retries:
        return func

    if not HAS_TENACITY:
        warnings.warn(
            f"Step '{ctx.name}' requested retries, but 'tenacity' not installed.",
            UserWarning,
        )
        return func

    if inspect.isasyncgenfunction(func):
        warnings.warn(
            f"Streaming step '{ctx.name}' cannot retry automatically.", UserWarning
        )
        return func

    if isinstance(retries, int):
        return retry(
            stop=stop_after_attempt(retries + 1),
            wait=wait_exponential(
                min=ctx.kwargs.get("retry_wait_min", 0.1),
                max=ctx.kwargs.get("retry_wait_max", 10),
            ),
            reraise=ctx.kwargs.get("retry_reraise", True),
        )(func)

    conf = retries.copy()
    if "reraise" not in conf:
        conf["reraise"] = True
    return retry(**conf)(func)  # type: ignore[no-any-return]


def simple_logging_middleware(
    func: Callable[..., Any], ctx: StepContext
) -> Callable[..., Any]:
    """A simple middleware that logs step execution time using the standard logging module."""
    logger = logging.getLogger("justpipe")

    if inspect.isasyncgenfunction(func):

        async def wrapped_gen(**inner_kwargs: Any) -> AsyncGenerator[Any, None]:
            start = time.perf_counter()
            try:
                async for item in func(**inner_kwargs):
                    yield item
            finally:
                elapsed = time.perf_counter() - start
                logger.debug(f"Step '{ctx.name}' took {elapsed:.4f}s")

        return wrapped_gen
    else:

        async def wrapped_func(**inner_kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return await func(**inner_kwargs)
            finally:
                elapsed = time.perf_counter() - start
                logger.debug(f"Step '{ctx.name}' took {elapsed:.4f}s")

        return wrapped_func


@dataclass
class _InternalTaskResult:
    owner: str
    name: str
    result: Any
    payload: Optional[Dict[str, Any]] = None


class _PipelineRunner(Generic[StateT, ContextT]):
    """Internal class that handles pipeline execution, event streaming, and worker management."""

    def __init__(
        self,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        injection_metadata: Dict[str, Dict[str, str]],
        step_metadata: Dict[str, Dict[str, Any]],
        startup_hooks: List[Callable[..., Any]],
        shutdown_hooks: List[Callable[..., Any]],
        on_error: Optional[Callable[..., Any]] = None,
        queue_size: int = 0,
        event_hooks: Optional[List[Callable[[Event], Event]]] = None,
    ):
        self._steps = steps
        self._topology = topology
        self._injection_metadata = injection_metadata
        self._step_metadata = step_metadata
        self._startup = startup_hooks
        self._shutdown = shutdown_hooks
        self._on_error = on_error
        self._event_hooks = event_hooks or []

        # Execution state
        self._state: Optional[StateT] = None
        self._context: Optional[ContextT] = None
        self._parents_map: Dict[str, Set[str]] = defaultdict(set)
        self._completed_parents: Dict[str, Set[str]] = defaultdict(set)
        self._logical_active: Dict[str, int] = defaultdict(int)
        self._total_active_tasks: int = 0
        self._queue: asyncio.Queue[Union[Event, _InternalTaskResult]] = asyncio.Queue(
            maxsize=queue_size
        )
        self._stopping: bool = False
        self._tg: Optional[asyncio.TaskGroup] = None
        self._barrier_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._skipped_owners: Set[str] = set()

    async def _worker(
        self,
        name: str,
        queue: asyncio.Queue[Union[Event, _InternalTaskResult]],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        func = self._steps.get(name)
        if not func:
            raise ValueError(f"Step not found: {name}")

        inj_meta = self._injection_metadata.get(name, {})
        step_meta = self._step_metadata.get(name, {})

        kwargs = (payload or {}).copy()
        for param_name, source in inj_meta.items():
            if source == "state":
                kwargs[param_name] = self._state
            elif source == "context":
                kwargs[param_name] = self._context

        timeout = step_meta.get("timeout")

        async def _exec() -> Any:
            if inspect.isasyncgenfunction(func):
                last_val = None
                async for item in func(**kwargs):
                    if isinstance(item, (_Next, _Map, _Run, Suspend)):
                        last_val = item
                    else:
                        await queue.put(Event(EventType.TOKEN, name, item))
                return last_val
            else:
                return await func(**kwargs)

        if timeout:
            try:
                return await asyncio.wait_for(_exec(), timeout=timeout)
            except (asyncio.TimeoutError, TimeoutError):
                raise TimeoutError(f"Step '{name}' timed out after {timeout}s")
        return await _exec()

    async def _execute_handler(
        self, name: str, error: Exception, use_global: bool = False
    ) -> Any:
        step_meta = self._step_metadata.get(name, {})
        handler = step_meta.get("on_error")
        meta_key = f"{name}:on_error"

        if not handler or use_global:
            handler = self._on_error
            meta_key = "system:on_error"

        if handler:
            inj_meta = self._injection_metadata.get(meta_key, {})
            kwargs: Dict[str, Any] = {}
            for param_name, source in inj_meta.items():
                if source == "state":
                    kwargs[param_name] = self._state
                elif source == "context":
                    kwargs[param_name] = self._context
                elif source == "error":
                    kwargs[param_name] = error
                elif source == "step_name":
                    kwargs[param_name] = name

            try:
                if inspect.iscoroutinefunction(handler):
                    return await handler(**kwargs)
                return handler(**kwargs)
            except Exception as e:
                if handler != self._on_error and self._on_error:
                    return await self._execute_handler(name, e, use_global=True)
                raise e

        self._default_error_handler(name, error)
        raise error

    def _default_error_handler(self, name: str, error: Exception) -> None:
        import traceback

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        stack = traceback.format_exc()
        state_str = str(self._state)[:1000]
        logging.error(
            f"[{timestamp}] Step '{name}' failed with {type(error).__name__}: {error}\n"
            f"State: {state_str}\n"
            f"Stack trace:\n{stack}"
        )

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

    def _determine_roots(self, start: Union[str, Callable[..., Any], None]) -> Set[str]:
        if start:
            return {_resolve_name(start)}
        elif self._steps:
            # collect uniq set of step's targets (from topology and map/switch metadata)
            all_targets = {
                t for step_targets in self._topology.values() for t in step_targets
            }
            for meta in self._step_metadata.values():
                if "map_target" in meta:
                    all_targets.add(meta["map_target"])
                if "switch_routes" in meta and isinstance(meta["switch_routes"], dict):
                    all_targets.update(meta["switch_routes"].values())
                if "switch_default" in meta and meta["switch_default"]:
                    all_targets.add(meta["switch_default"])

            roots = set(self._steps.keys()) - all_targets
            if not roots:
                roots = {next(iter(self._steps))}
            return roots
        return set()

    def _build_dependency_graph(self) -> None:
        for parent, children in self._topology.items():
            for child in children:
                self._parents_map[child].add(parent)

    def _spawn(self, coro: Any, owner: str) -> None:
        if self._stopping or not self._tg:
            coro.close()
            return
        self._logical_active[owner] += 1
        self._total_active_tasks += 1
        self._tg.create_task(coro)

    async def _report_error(self, name: str, owner: str, error: Exception) -> None:
        await self._queue.put(Event(EventType.ERROR, name, str(error)))
        await self._queue.put(_InternalTaskResult(owner, name, None))

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
            res = await self._worker(name, self._queue, payload)
            await self._queue.put(_InternalTaskResult(owner, name, res, payload))
        except Exception as e:
            try:
                res = await self._execute_handler(name, e)
                await self._queue.put(_InternalTaskResult(owner, name, res, payload))
            except Exception as final_error:
                await self._report_error(name, owner, final_error)

    async def _sub_pipe_wrapper(
        self, sub_pipe: Any, sub_state: Any, owner: str
    ) -> None:
        name = f"{owner}:sub"
        try:
            async for ev in sub_pipe.run(sub_state):
                ev.stage = f"{owner}:{ev.stage}"
                await self._queue.put(ev)
            await self._queue.put(_InternalTaskResult(owner, name, None))
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
                yield self._apply_event_hooks(item)
                if item.type == EventType.SUSPEND:
                    self._stopping = True
            elif isinstance(item, _InternalTaskResult):
                self._total_active_tasks -= 1
                self._logical_active[item.owner] -= 1

                async for event in self._handle_task_result(item):
                    yield self._apply_event_hooks(event)

                if self._logical_active[item.owner] == 0:
                    yield self._apply_event_hooks(
                        Event(EventType.STEP_END, item.owner, self._state)
                    )
                    self._handle_completion(item.owner)

    async def _handle_task_result(
        self, item: _InternalTaskResult
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
            if self._completed_parents[name] < self._parents_map[name]:
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

        for succ in self._topology.get(owner, []):
            is_first = len(self._completed_parents[succ]) == 0
            self._completed_parents[succ].add(owner)

            parents_needed = self._parents_map[succ]
            if self._completed_parents[succ] >= parents_needed:
                if succ in self._barrier_tasks:
                    self._barrier_tasks[succ].cancel()
                    del self._barrier_tasks[succ]
                self._schedule(succ)
            elif is_first and len(parents_needed) > 1:
                timeout = self._step_metadata.get(succ, {}).get("barrier_timeout")
                if timeout and self._tg:
                    self._barrier_tasks[succ] = self._tg.create_task(
                        self._barrier_timeout_watcher(succ, timeout)
                    )

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the pipeline starting from the specified step."""
        self._state = state
        self._context = context

        try:
            error_event = await self._execute_startup()
            if error_event:
                yield self._apply_event_hooks(error_event)
                return

            roots = self._determine_roots(start)
            # Check if we have roots or steps to run
            if not roots and not self._steps:
                yield self._apply_event_hooks(
                    Event(EventType.ERROR, "system", "No steps registered")
                )
                return

            # Build dependency graph
            self._build_dependency_graph()

            yield self._apply_event_hooks(Event(EventType.START, "system", state))

            async with asyncio.TaskGroup() as tg:
                self._tg = tg
                for root in roots:
                    self._schedule(root)

                async for event in self._process_queue():
                    yield event

        finally:
            # Shutdown
            async for ev in self._execute_shutdown():
                yield self._apply_event_hooks(ev)

            yield self._apply_event_hooks(
                Event(EventType.FINISH, "system", self._state)
            )


class Pipe(Generic[StateT, ContextT]):
    def __init__(
        self,
        name: str = "Pipe",
        middleware: Optional[List[Middleware]] = None,
        queue_size: int = 0,
        validate_on_run: bool = False,
    ):
        self.name = name
        self.queue_size = queue_size
        self.middleware = (
            list(middleware) if middleware is not None else [tenacity_retry_middleware]
        )
        self._validate_on_run = validate_on_run
        self._steps: Dict[str, Callable[..., Any]] = {}
        self._topology: Dict[str, List[str]] = {}
        self._startup: List[Callable[..., Any]] = []
        self._shutdown: List[Callable[..., Any]] = []
        self._on_error: Optional[Callable[..., Any]] = None
        self._injection_metadata: Dict[str, Dict[str, str]] = {}
        self._step_metadata: Dict[str, Dict[str, Any]] = {}
        self._event_hooks: List[Callable[[Event], Event]] = []

    def _get_types(self) -> tuple[Any, Any]:
        orig = getattr(self, "__orig_class__", None)
        if orig:
            args = get_args(orig)
            if len(args) == 2:
                return args[0], args[1]
        return Any, Any

    def add_middleware(self, mw: Middleware) -> None:
        self.middleware.append(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        """Add a hook that can transform events before they are yielded."""
        self._event_hooks.append(hook)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._shutdown.append(func)
        return func

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._on_error = func
        state_type, context_type = self._get_types()
        self._injection_metadata["system:on_error"] = _analyze_signature(
            func, state_type, context_type, expected_unknowns=0
        )
        return func

    def _validate_routing_target(self, target: Any) -> None:
        if isinstance(target, str):
            warnings.warn(
                f"String-based topology ('{target}') is deprecated. "
                "Use direct function references instead.",
                DeprecationWarning,
                stacklevel=3,
            )
        elif isinstance(target, list):
            for t in target:
                self._validate_routing_target(t)
        elif isinstance(target, dict):
            for t in target.values():
                if id(t) != id(Stop):
                    self._validate_routing_target(t)

    def step(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)
            self._step_metadata[stage_name] = {
                **kwargs,
                "barrier_timeout": barrier_timeout,
                "on_error": on_error,
            }
            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type, expected_unknowns=1
            )
            if on_error:
                self._injection_metadata[f"{stage_name}:on_error"] = _analyze_signature(
                    on_error, state_type, context_type, expected_unknowns=0
                )
            if to:
                self._validate_routing_target(to)
                self._topology[stage_name] = [
                    _resolve_name(t) for t in (to if isinstance(to, list) else [to])
                ]
            wrapped = func
            ctx = StepContext(name=stage_name, kwargs=kwargs, pipe_name=self.name)
            for mw in self.middleware:
                wrapped = mw(wrapped, ctx)
            self._steps[stage_name] = wrapped
            return func

        if callable(name) and to is None and not kwargs:
            return decorator(name)
        return decorator

    def map(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        using: Union[str, Callable[..., Any], None] = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if using is None:
            raise ValueError("@pipe.map requires 'using' parameter")

        self._validate_routing_target(using)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)
            target_name = _resolve_name(using)

            self._step_metadata[stage_name] = {
                **kwargs,
                "map_target": target_name,
                "barrier_timeout": barrier_timeout,
                "on_error": on_error,
            }
            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type, expected_unknowns=1
            )
            if on_error:
                self._injection_metadata[f"{stage_name}:on_error"] = _analyze_signature(
                    on_error, state_type, context_type, expected_unknowns=0
                )

            if to:
                self._validate_routing_target(to)
                self._topology[stage_name] = [
                    _resolve_name(t) for t in (to if isinstance(to, list) else [to])
                ]

            async def map_wrapper(**inner_kwargs: Any) -> _Map:
                if inspect.isasyncgenfunction(func):
                    items = []
                    async for item in func(**inner_kwargs):
                        items.append(item)
                    return _Map(items=items, target=target_name)
                else:
                    result = await func(**inner_kwargs)
                    try:
                        items = list(result)
                    except TypeError:
                        raise ValueError(
                            f"Step '{stage_name}' decorated with @pipe.map "
                            f"must return an iterable, got {type(result)}"
                        )
                    return _Map(items=items, target=target_name)

            wrapped = map_wrapper
            ctx = StepContext(name=stage_name, kwargs=kwargs, pipe_name=self.name)
            for mw in self.middleware:
                wrapped = mw(wrapped, ctx)
            self._steps[stage_name] = wrapped
            return func

        return decorator

    def switch(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        routes: Union[
            Dict[
                Any,
                Union[
                    str,
                    Callable[..., Any],
                    _Stop,
                ],
            ],
            Callable[[Any], Union[str, _Stop]],
            None,
        ] = None,
        default: Union[str, Callable[..., Any], None] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if routes is None:
            raise ValueError("@pipe.switch requires 'routes' parameter")

        self._validate_routing_target(routes)
        if default:
            self._validate_routing_target(default)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            normalized_routes = {}
            if isinstance(routes, dict):
                for key, target in routes.items():
                    if isinstance(target, _Stop):
                        normalized_routes[key] = "Stop"
                    else:
                        normalized_routes[key] = _resolve_name(target)

            self._step_metadata[stage_name] = {
                **kwargs,
                "switch_routes": normalized_routes
                if isinstance(routes, dict)
                else "dynamic",
                "switch_default": _resolve_name(default) if default else None,
                "barrier_timeout": barrier_timeout,
                "on_error": on_error,
            }

            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type, expected_unknowns=1
            )
            if on_error:
                self._injection_metadata[f"{stage_name}:on_error"] = _analyze_signature(
                    on_error, state_type, context_type, expected_unknowns=0
                )

            async def switch_wrapper(**inner_kwargs: Any) -> Any:
                result = await func(**inner_kwargs)

                target = None
                if isinstance(routes, dict):
                    target = routes.get(result, default)
                elif callable(routes):
                    target = routes(result)

                if target is None:
                    raise ValueError(
                        f"Step '{stage_name}' (switch) returned {result}, "
                        f"which matches no route and no default was provided."
                    )

                if isinstance(target, _Stop):
                    return Stop
                return _Next(target)

            wrapped = switch_wrapper
            ctx = StepContext(name=stage_name, kwargs=kwargs, pipe_name=self.name)
            for mw in self.middleware:
                wrapped = mw(wrapped, ctx)
            self._steps[stage_name] = wrapped
            return func

        return decorator

    def sub(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        using: Any = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if using is None:
            raise ValueError("@pipe.sub requires 'using' parameter")

        self._validate_routing_target(using)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            self._step_metadata[stage_name] = {
                **kwargs,
                "sub_pipeline": using.name if hasattr(using, "name") else "SubPipe",
                "sub_pipeline_obj": using,
                "barrier_timeout": barrier_timeout,
                "on_error": on_error,
            }

            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type, expected_unknowns=1
            )
            if on_error:
                self._injection_metadata[f"{stage_name}:on_error"] = _analyze_signature(
                    on_error, state_type, context_type, expected_unknowns=0
                )

            if to:
                self._validate_routing_target(to)
                self._topology[stage_name] = [
                    _resolve_name(t) for t in (to if isinstance(to, list) else [to])
                ]

            async def sub_wrapper(**inner_kwargs: Any) -> _Run:
                # Execute the adapter function to get the state/context for sub-pipe
                # The adapter should return the state object for the sub-pipeline
                result = await func(**inner_kwargs)
                return _Run(pipe=using, state=result)

            wrapped = sub_wrapper
            ctx = StepContext(name=stage_name, kwargs=kwargs, pipe_name=self.name)
            for mw in self.middleware:
                wrapped = mw(wrapped, ctx)
            self._steps[stage_name] = wrapped
            return func

        return decorator

    def graph(self) -> str:
        return generate_mermaid_graph(
            self._steps,
            self._topology,
            self._step_metadata,
            startup_hooks=self._startup,
            shutdown_hooks=self._shutdown,
        )

    def steps(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        for name, meta in self._step_metadata.items():
            # Determine the kind of step
            if "map_target" in meta:
                kind = "map"
            elif "switch_routes" in meta:
                kind = "switch"
            elif "sub_pipeline" in meta:
                kind = "sub"
            else:
                kind = "step"

            # Collect targets from topology and special routing
            targets = list(self._topology.get(name, []))
            if "map_target" in meta:
                targets.append(meta["map_target"])
            if "switch_routes" in meta and isinstance(meta["switch_routes"], dict):
                targets.extend(t for t in meta["switch_routes"].values() if t != "Stop")
            if meta.get("switch_default"):
                targets.append(meta["switch_default"])

            yield StepInfo(
                name=name,
                timeout=meta.get("timeout"),
                retries=meta.get("retries", 0) if meta.get("retries") else 0,
                barrier_timeout=meta.get("barrier_timeout"),
                has_error_handler=meta.get("on_error") is not None,
                targets=targets,
                kind=kind,
            )

    @property
    def topology(self) -> Dict[str, List[str]]:
        """Read-only view of the execution graph."""
        return dict(self._topology)

    def validate(self) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            ValueError: if any unresolvable references or integrity issues are found.
        """
        if not self._steps:
            return

        all_step_names = set(self._steps.keys())
        referenced_names: Set[str] = set()

        # 1. Check topology
        for parent, children in self._topology.items():
            for child in children:
                if child not in all_step_names:
                    raise ValueError(f"Step '{parent}' targets unknown step '{child}'")
                referenced_names.add(child)

        # 2. Check special metadata (map_target, switch_routes)
        for step_name, meta in self._step_metadata.items():
            if "map_target" in meta:
                target = meta["map_target"]
                if target not in all_step_names:
                    raise ValueError(
                        f"Step '{step_name}' (map) targets unknown step '{target}'"
                    )
                referenced_names.add(target)

            if "switch_routes" in meta:
                routes = meta["switch_routes"]
                if isinstance(routes, dict):
                    for route_name in routes.values():
                        if (
                            isinstance(route_name, str)
                            and route_name != "Stop"
                            and route_name not in all_step_names
                        ):
                            raise ValueError(
                                f"Step '{step_name}' (switch) routes to unknown step '{route_name}'"
                            )
                        if isinstance(route_name, str) and route_name != "Stop":
                            referenced_names.add(route_name)

                default = meta.get("switch_default")
                if default and default not in all_step_names:
                    raise ValueError(
                        f"Step '{step_name}' (switch) has unknown default route '{default}'"
                    )
                if default:
                    referenced_names.add(default)

        # 3. Detect roots (entry points)
        roots = all_step_names - referenced_names
        if not roots and all_step_names:
            raise ValueError(
                "Circular dependency detected or no entry points found in the pipeline."
            )

        # 4. Cycle detection and reachability
        visited: Set[str] = set()
        path: Set[str] = set()

        def check_cycle(node: str) -> None:
            visited.add(node)
            path.add(node)

            targets = self._topology.get(node, []).copy()
            meta = self._step_metadata.get(node, {})
            if "map_target" in meta:
                targets.append(meta["map_target"])
            if "switch_routes" in meta and isinstance(meta["switch_routes"], dict):
                targets.extend(
                    [t for t in meta["switch_routes"].values() if t != "Stop"]
                )
            if "switch_default" in meta and meta["switch_default"]:
                targets.append(meta["switch_default"])

            for target in targets:
                if target in path:
                    raise ValueError(
                        f"Circular dependency detected involving '{node}' and '{target}'"
                    )
                if target not in visited:
                    check_cycle(target)

            path.remove(node)

        for root in roots:
            check_cycle(root)

        unvisited = all_step_names - visited
        if unvisited:
            raise ValueError(
                f"Unreachable steps detected (possibly a cycle without an entry point): {unvisited}"
            )

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
        queue_size: Optional[int] = None,
    ) -> AsyncGenerator[Event, None]:
        if self._validate_on_run:
            self.validate()
        runner: _PipelineRunner[StateT, ContextT] = _PipelineRunner(
            self._steps,
            self._topology,
            self._injection_metadata,
            self._step_metadata,
            self._startup,
            self._shutdown,
            on_error=self._on_error,
            queue_size=queue_size if queue_size is not None else self.queue_size,
            event_hooks=self._event_hooks,
        )
        async for event in runner.run(state, context, start):
            yield event
