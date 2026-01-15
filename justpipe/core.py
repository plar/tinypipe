import asyncio
import contextlib
import inspect
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Optional,
    Union,
    TypeVar,
    Generic,
    Set,
    List,
    cast,
    get_args,
)

from justpipe.visualization import generate_mermaid_graph


try:
    from tenacity import retry, stop_after_attempt, wait_exponential

    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

# Parameter name aliases for smart injection
STATE_ALIASES: frozenset[str] = frozenset({"s", "state"})
CONTEXT_ALIASES: frozenset[str] = frozenset({"ctx", "context", "c"})


class EventType(Enum):
    START = "start"
    TOKEN = "token"
    STEP_START = "step_start"
    STEP_END = "step_end"
    ERROR = "error"
    FINISH = "finish"


@dataclass
class Event:
    type: EventType
    stage: str
    data: Any = None


def _resolve_name(target: Union[str, Callable[..., Any]]) -> str:
    if isinstance(target, str):
        return target

    if hasattr(target, "__name__"):
        return target.__name__

    raise ValueError(f"Cannot resolve name for {target}")


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
            raise ValueError(f"Unknown argument '{name}' in step '{func.__name__}'.")

    return mapping


@dataclass
class Next:
    target: Union[str, Callable[..., Any], None]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def stage(self) -> Optional[str]:
        if self.target is None:
            return None
        return _resolve_name(self.target)


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
        retry_wait_min = kwargs.get("retry_wait_min", 0.1)
        retry_wait_max = kwargs.get("retry_wait_max", 10)
        retry_reraise = kwargs.get("retry_reraise", True)
        return retry(
            stop=stop_after_attempt(retries + 1),
            wait=wait_exponential(min=retry_wait_min, max=retry_wait_max),
            reraise=retry_reraise,
        )(func)

    conf = retries.copy()
    if "reraise" not in conf:
        conf["reraise"] = True
    return retry(**conf)(func)  # type: ignore[no-any-return]


class _PipelineRunner(Generic[StateT, ContextT]):
    """Internal class that handles pipeline execution, event streaming, and worker management."""

    def __init__(
        self,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        injection_metadata: Dict[str, Dict[str, str]],
        startup_hooks: List[Callable[..., Any]],
        shutdown_hooks: List[Callable[..., Any]],
    ):
        self._steps = steps
        self._topology = topology
        self._injection_metadata = injection_metadata
        self._startup = startup_hooks
        self._shutdown = shutdown_hooks

    async def _drain_queue(
        self, queue: asyncio.Queue[Event]
    ) -> AsyncGenerator[Event, None]:
        """Yield all currently available events from the queue."""
        while not queue.empty():
            try:
                yield queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _wait_for_batch(
        self,
        tasks: List[asyncio.Task[tuple[Optional[Next], str]]],
        queue: asyncio.Queue[Event],
    ) -> AsyncGenerator[Event, None]:
        """Wait for a batch of tasks to complete while yielding events from the queue."""
        if not tasks:
            return

        queue_task: asyncio.Task[Event] = asyncio.create_task(queue.get())
        active_tasks: Set[asyncio.Task[tuple[Optional[Next], str]]] = set(tasks)

        try:
            while active_tasks:
                all_tasks: Set[asyncio.Task[Any]] = cast(
                    Set[asyncio.Task[Any]], active_tasks
                ) | {queue_task}
                done, _ = await asyncio.wait(
                    all_tasks, return_when=asyncio.FIRST_COMPLETED
                )

                for task in done:
                    if task is queue_task:
                        yield cast(asyncio.Task[Event], task).result()
                        queue_task = asyncio.create_task(queue.get())
                    else:
                        active_tasks.discard(
                            cast(asyncio.Task[tuple[Optional[Next], str]], task)
                        )
                        try:
                            task.result()
                        except Exception as e:
                            yield Event(EventType.ERROR, "system", str(e))

                async for event in self._drain_queue(queue):
                    yield event
        finally:
            queue_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await queue_task

    async def _worker(
        self,
        name: str,
        state: StateT,
        ctx: Optional[ContextT],
        queue: asyncio.Queue[Event],
    ) -> tuple[Optional[Next], str]:
        task = asyncio.current_task()
        if task:
            task.set_name(name)

        func = self._steps[name]
        metadata = self._injection_metadata.get(name, {})

        kwargs: Dict[str, Any] = {}
        for param_name, source in metadata.items():
            if source == "state":
                kwargs[param_name] = state
            elif source == "context":
                kwargs[param_name] = ctx

        if inspect.isasyncgenfunction(func):
            instr = None
            async for item in func(**kwargs):
                if isinstance(item, Next):
                    instr = item
                else:
                    await queue.put(Event(EventType.TOKEN, name, item))
            return instr, name
        else:
            res = await func(**kwargs)
            if isinstance(res, str):
                return Next(res), name
            return (res if isinstance(res, Next) else None), name

    async def _run_shutdown_hooks(
        self, context: Optional[ContextT]
    ) -> AsyncGenerator[Event, None]:
        """Run shutdown hooks, yielding errors if any fail."""
        for h in self._shutdown:
            try:
                await h(context)
            except Exception as e:
                yield Event(EventType.ERROR, "shutdown", str(e))

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        """Execute the pipeline starting from the specified step."""
        # Run startup hooks with error handling
        try:
            for h in self._startup:
                await h(context)
        except Exception as e:
            yield Event(EventType.ERROR, "startup", str(e))
            async for event in self._run_shutdown_hooks(context):
                yield event
            yield Event(EventType.FINISH, "system", state)
            return

        # Handle empty pipeline
        if start:
            first = _resolve_name(start)
        elif self._steps:
            first = next(iter(self._steps))
        else:
            yield Event(EventType.ERROR, "system", "No steps registered")
            async for event in self._run_shutdown_hooks(context):
                yield event
            yield Event(EventType.FINISH, "system", state)
            return

        current_batch = {first}
        yield Event(EventType.START, "system", state)

        queue: asyncio.Queue[Event] = asyncio.Queue()

        try:
            while current_batch:
                tasks = []
                for name in current_batch:
                    if name not in self._steps:
                        yield Event(EventType.ERROR, name, "Step not found")
                        continue
                    yield Event(EventType.STEP_START, name)
                    tasks.append(
                        asyncio.create_task(self._worker(name, state, context, queue))
                    )

                if not tasks:
                    break

                async for event in self._wait_for_batch(tasks, queue):
                    yield event

                next_batch: Set[str] = set()
                for task in tasks:
                    try:
                        res, stage_name = task.result()
                        yield Event(EventType.STEP_END, stage_name, state)

                        if res and res.stage:
                            next_batch.add(res.stage)
                        elif stage_name in self._topology:
                            next_batch.update(self._topology[stage_name])
                    except Exception:
                        # Exception already yielded as ERROR event in _wait_for_batch
                        continue

                current_batch = next_batch

        except Exception as e:
            yield Event(EventType.ERROR, "fatal", str(e))
            raise
        finally:
            async for event in self._run_shutdown_hooks(context):
                yield event
            yield Event(EventType.FINISH, "system", state)


class Pipe(Generic[StateT, ContextT]):
    """Async pipeline orchestrator for building event-driven DAGs.

    Example:
        pipe = Pipe[MyState, MyContext]()

        @pipe.step("start", to="process")
        async def start(state):
            state.data = "initialized"

        @pipe.step("process")
        async def process(state):
            yield f"Processing: {state.data}"

        async for event in pipe.run(MyState(), MyContext()):
            print(event)
    """

    def __init__(
        self, name: str = "Pipe", middleware: Optional[List[Middleware]] = None
    ):
        """Initialize a new pipeline.

        Args:
            name: Optional name for the pipeline (for debugging/logging).
            middleware: Optional list of middleware functions. Defaults to
                [tenacity_retry_middleware] for automatic retry support.
        """
        self.name = name
        self.middleware = (
            list(middleware) if middleware is not None else [tenacity_retry_middleware]
        )
        self._steps: Dict[str, Callable[..., Any]] = {}
        self._topology: Dict[str, List[str]] = {}
        self._startup: List[Callable[..., Any]] = []
        self._shutdown: List[Callable[..., Any]] = []
        self._injection_metadata: Dict[str, Dict[str, str]] = {}

    def _get_types(self) -> tuple[Any, Any]:
        """Extract StateT and ContextT from the Pipe instance."""
        # When Pipe[State, Ctx]() is called, __orig_class__ is set on the instance.
        orig = getattr(self, "__orig_class__", None)
        if orig:
            args = get_args(orig)
            if len(args) == 2:
                # Handle NoneType correctly (None in get_args returns type(None))
                return args[0], args[1]

        # Fallback to Any if no concrete types were provided
        return Any, Any

    def add_middleware(self, mw: Middleware) -> None:
        """Add a middleware function to the pipeline.

        Middleware wraps step functions and can modify behavior (e.g., retry, logging).

        Args:
            mw: Middleware function with signature (func, kwargs) -> wrapped_func.
        """
        self.middleware.append(mw)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Register a startup handler."""
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Register a shutdown handler."""
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
        """
        Register a step in the pipeline.

        Args:
            name: Optional name for the step. Defaults to function name.
            to: Optional target step(s) to execute next.
            **kwargs: Configuration passed to middleware.

        Smart Injection:
            Step functions can accept 'state' and/or 'context' arguments. The engine
            automatically injects these based on:
            1. Type Hints: If parameters match Pipe's StateT or ContextT.
            2. Parameter Names: Fallback to 's'/'state' and/or 'ctx'/'context'/'c'.
            Signatures are validated at registration time.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            # Analyze signature and store metadata
            state_type, context_type = self._get_types()
            self._injection_metadata[stage_name] = _analyze_signature(
                func, state_type, context_type
            )

            if to:
                targets = to if isinstance(to, list) else [to]
                self._topology[stage_name] = [_resolve_name(t) for t in targets]

            wrapped = func
            for mw in self.middleware:
                wrapped = mw(wrapped, kwargs)

            self._steps[stage_name] = wrapped
            return func

        if callable(name) and to is None and not kwargs:
            return decorator(name)
        return decorator

    def graph(self) -> str:
        """Generate a Mermaid diagram of the pipeline.

        Returns:
            Mermaid diagram string that can be rendered in markdown.
            Features:
            - Streaming steps marked with ⚡ and orange color
            - Start/End nodes for clear flow visualization
            - Isolated (unconnected) steps shown in separate subgraph
            - Color-coded: blue=regular, orange=streaming, pink=isolated
        """
        return generate_mermaid_graph(self._steps, self._topology)

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
    ) -> AsyncGenerator[Event, None]:
        """
        Execute the pipeline starting from the specified step.

        Args:
            state: The initial state object (mutable).
            context: Optional context object for side-effects (e.g., API clients).
            start: Optional name or function of the step to start from.

        Yields:
            Event: Stream of execution events (START, TOKEN, STEP_START, etc.).
        """
        runner: _PipelineRunner[StateT, ContextT] = _PipelineRunner(
            steps=self._steps,
            topology=self._topology,
            injection_metadata=self._injection_metadata,
            startup_hooks=self._startup,
            shutdown_hooks=self._shutdown,
        )
        async for event in runner.run(state, context, start):
            yield event
