from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
    Union,
    get_args,
)

from justpipe.middleware import Middleware
from justpipe.runner import _PipelineRunner
from justpipe.registry import _PipelineRegistry
from justpipe.steps import _BaseStep
from justpipe.types import (
    Event,
    HookSpec,
    StepInfo,
    _Stop,
)
from justpipe.visualization import generate_mermaid_graph

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


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
        self._validate_on_run = validate_on_run

        # Determine types for registry
        state_type, context_type = self._get_types()
        self.registry = _PipelineRegistry(
            pipe_name=name,
            middleware=middleware,
            state_type=state_type,
            context_type=context_type,
        )

    def _get_types(self) -> tuple[Any, Any]:
        orig = getattr(self, "__orig_class__", None)
        if orig:
            args = get_args(orig)
            if len(args) == 2:
                return args[0], args[1]
        return Any, Any

    def _refresh_registry_types(self) -> None:
        state_type, context_type = self._get_types()
        if state_type is not Any:
            self.registry.state_type = state_type
        if context_type is not Any:
            self.registry.context_type = context_type

    # Internal properties for introspection and runner access
    @property
    def _steps(self) -> Dict[str, _BaseStep]:
        return self.registry.steps

    @property
    def _topology(self) -> Dict[str, List[str]]:
        return self.registry.topology

    @property
    def _startup(self) -> List[Callable[..., Any]]:
        return [hook.func for hook in self.registry.startup_hooks]

    @property
    def _shutdown(self) -> List[Callable[..., Any]]:
        return [hook.func for hook in self.registry.shutdown_hooks]

    @property
    def _injection_metadata(self) -> Dict[str, Dict[str, str]]:
        return self.registry.injection_metadata

    @property
    def _error_hook(self) -> Optional[HookSpec]:
        return self.registry.error_hook

    @property
    def _event_hooks(self) -> List[Callable[[Event], Event]]:
        return self.registry.event_hooks

    @property
    def middleware(self) -> List[Middleware]:
        return self.registry.middleware

    def add_middleware(self, mw: Middleware) -> None:
        self.registry.add_middleware(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self.registry.add_event_hook(hook)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._refresh_registry_types()
        return self.registry.on_startup(func)

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._refresh_registry_types()
        return self.registry.on_shutdown(func)

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._refresh_registry_types()
        return self.registry.on_error(func)

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
        self._refresh_registry_types()
        return self.registry.step(name, to, barrier_timeout, on_error, **kwargs)

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
        self._refresh_registry_types()
        return self.registry.map(name, using, to, barrier_timeout, on_error, **kwargs)

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
        self._refresh_registry_types()
        return self.registry.switch(
            name,
            routes,
            default,
            barrier_timeout,
            on_error,
            **kwargs,
        )

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
        self._refresh_registry_types()
        return self.registry.sub(name, using, to, barrier_timeout, on_error, **kwargs)

    def graph(self) -> str:
        return generate_mermaid_graph(
            self.registry.steps,
            self.registry.topology,
            startup_hooks=[hook.func for hook in self.registry.startup_hooks],
            shutdown_hooks=[hook.func for hook in self.registry.shutdown_hooks],
        )

    def steps(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        return self.registry.get_steps_info()

    @property
    def topology(self) -> Dict[str, List[str]]:
        """Read-only view of the execution graph."""
        return dict(self.registry.topology)

    def validate(self) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            ValueError: if any unresolvable references or integrity issues are found.
        """
        from justpipe.graph import _DependencyGraph

        graph = _DependencyGraph(
            self.registry.steps,
            self.registry.topology,
        )
        graph.validate()

    async def run(
        self,
        state: StateT,
        context: Optional[ContextT] = None,
        start: Union[str, Callable[..., Any], None] = None,
        queue_size: Optional[int] = None,
    ) -> AsyncGenerator[Event, None]:
        if self._validate_on_run:
            self.validate()
        self.registry.finalize()
        runner: _PipelineRunner[StateT, ContextT] = _PipelineRunner(
            self.registry.steps,
            self.registry.topology,
            self.registry.injection_metadata,
            self.registry.startup_hooks,
            self.registry.shutdown_hooks,
            on_error=self.registry.error_hook,
            queue_size=queue_size if queue_size is not None else self.queue_size,
            event_hooks=self.registry.event_hooks,
        )
        async for event in runner.run(state, context, start):
            yield event
