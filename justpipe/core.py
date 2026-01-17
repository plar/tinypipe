import asyncio
import inspect
import warnings
from dataclasses import dataclass
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
    Generic,
    Union,
    get_args,
)

from justpipe.visualization import generate_mermaid_graph
from justpipe.types import (
    Event,
    EventType,
    Next,
    Map,
    Run,
    Suspend,
    _resolve_name,
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


def _analyze_signature(
    func: Callable[..., Any],
    state_type: Any,
    context_type: Any,
) -> Dict[str, str]:
    """Analyze function signature and map parameters to state or context."""
    mapping = {}
    sig = inspect.signature(func)
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
        # 3. Handle parameters with default values
        elif param.default is not inspect.Parameter.empty:
            continue
        else:
            mapping[name] = "unknown"
    return mapping


StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")
Middleware = Callable[
    [Callable[..., Any], Dict[str, Any]],
    Callable[..., Any],
]


def tenacity_retry_middleware(
    func: Callable[..., Any],
    kwargs: Dict[str, Any],
) -> Callable[..., Any]:
    retries = kwargs.get("retries", 0)
    if not retries:
        return func

    if not HAS_TENACITY:
        warnings.warn(
            f"Step '{func.__name__}' requested retries, but 'tenacity' not installed.",
            UserWarning,
        )
        return func

    if inspect.isasyncgenfunction(func):
        warnings.warn(
            f"Streaming step '{func.__name__}' cannot retry automatically.", UserWarning
        )
        return func

    if isinstance(retries, int):
        return retry(
            stop=stop_after_attempt(retries + 1),
            wait=wait_exponential(
                min=kwargs.get("retry_wait_min", 0.1),
                max=kwargs.get("retry_wait_max", 10),
            ),
            reraise=kwargs.get("retry_reraise", True),
        )(func)

    conf = retries.copy()
    if "reraise" not in conf:
        conf["reraise"] = True
    return retry(**conf)(func)  # type: ignore[no-any-return]


@dataclass
class _InternalTaskResult:
    owner: str
    name: str
    result: Any


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
    ):
        self._steps = steps
        self._topology = topology
        self._injection_metadata = injection_metadata
        self._step_metadata = step_metadata
        self._startup = startup_hooks
        self._shutdown = shutdown_hooks

        # Execution state
        self._state: Optional[StateT] = None
        self._context: Optional[ContextT] = None
        self._parents_map: Dict[str, Set[str]] = defaultdict(set)
        self._completed_parents: Dict[str, Set[str]] = defaultdict(set)
        self._logical_active: Dict[str, int] = defaultdict(int)
        self._total_active_tasks: int = 0
        self._queue: asyncio.Queue[Union[Event, _InternalTaskResult]] = asyncio.Queue()
        self._stopping: bool = False
        self._tg: Optional[asyncio.TaskGroup] = None

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
                    if isinstance(item, (Next, Map, Run, Suspend)):
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
            # collect uniq set of step's targets
            all_targets = {
                t for step_targets in self._topology.values() for t in step_targets
            }
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
            await self._queue.put(_InternalTaskResult(owner, name, res))
        except Exception as e:
            await self._report_error(name, owner, e)

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

    async def _process_queue(self) -> AsyncGenerator[Event, None]:
        while self._total_active_tasks > 0:
            item = await self._queue.get()

            if isinstance(item, Event):
                yield item
                if item.type == EventType.SUSPEND:
                    self._stopping = True
            elif isinstance(item, _InternalTaskResult):
                self._total_active_tasks -= 1
                self._logical_active[item.owner] -= 1

                async for event in self._handle_task_result(item):
                    yield event

                if self._logical_active[item.owner] == 0:
                    yield Event(EventType.STEP_END, item.owner, self._state)
                    self._handle_completion(item.owner)

    async def _handle_task_result(
        self, item: _InternalTaskResult
    ) -> AsyncGenerator[Event, None]:
        res = item.result
        if isinstance(res, str):
            res = Next(res)

        if isinstance(res, Suspend):
            yield Event(EventType.SUSPEND, item.name, res.reason)
            self._stopping = True
        elif isinstance(res, Next) and res.stage:
            self._schedule(res.stage)
        elif isinstance(res, Map):
            self._handle_map(res, item.owner)
        elif isinstance(res, Run):
            if self._tg:
                self._spawn(
                    self._sub_pipe_wrapper(res.pipe, res.state, item.owner), item.owner
                )

    def _handle_map(self, res: Map, owner: str) -> None:
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

    def _handle_completion(self, owner: str) -> None:
        for succ in self._topology.get(owner, []):
            self._completed_parents[succ].add(owner)
            if self._completed_parents[succ] >= self._parents_map[succ]:
                self._schedule(succ)

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
                yield error_event
                return

            roots = self._determine_roots(start)
            # Check if we have roots or steps to run
            if not roots and not self._steps:
                yield Event(EventType.ERROR, "system", "No steps registered")
                return

            # Build dependency graph
            self._build_dependency_graph()

            yield Event(EventType.START, "system", state)

            async with asyncio.TaskGroup() as tg:
                self._tg = tg
                for root in roots:
                    self._schedule(root)

                async for event in self._process_queue():
                    yield event

        finally:
            # Shutdown
            async for ev in self._execute_shutdown():
                yield ev

            yield Event(EventType.FINISH, "system", self._state)


class Pipe(Generic[StateT, ContextT]):
    def __init__(
        self, name: str = "Pipe", middleware: Optional[List[Middleware]] = None
    ):
        self.name = name
        self.middleware = (
            list(middleware) if middleware is not None else [tenacity_retry_middleware]
        )
        self._steps: Dict[str, Callable[..., Any]] = {}
        self._topology: Dict[str, List[str]] = {}
        self._startup: List[Callable[..., Any]] = []
        self._shutdown: List[Callable[..., Any]] = []
        self._injection_metadata: Dict[str, Dict[str, str]] = {}
        self._step_metadata: Dict[str, Dict[str, Any]] = {}

    def _get_types(self) -> tuple[Any, Any]:
        orig = getattr(self, "__orig_class__", None)
        if orig:
            args = get_args(orig)
            if len(args) == 2:
                return args[0], args[1]
        return Any, Any

    def add_middleware(self, mw: Middleware) -> None:
        self.middleware.append(mw)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._shutdown.append(func)
        return func

    def step(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)
            self._step_metadata[stage_name] = kwargs
            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type
            )
            if to:
                self._topology[stage_name] = [
                    _resolve_name(t) for t in (to if isinstance(to, list) else [to])
                ]
            wrapped = func
            for mw in self.middleware:
                wrapped = mw(wrapped, kwargs)
            self._steps[stage_name] = wrapped
            return func

        if callable(name) and to is None and not kwargs:
            return decorator(name)
        return decorator

    def graph(self) -> str:
        return generate_mermaid_graph(self._steps, self._topology)

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        runner: _PipelineRunner[StateT, ContextT] = _PipelineRunner(
            self._steps,
            self._topology,
            self._injection_metadata,
            self._step_metadata,
            self._startup,
            self._shutdown,
        )
        async for event in runner.run(state, context, start):
            yield event
