from __future__ import annotations

from typing import (
    Any,
    Generic,
    TypeVar,
    TYPE_CHECKING,
)
from collections.abc import AsyncGenerator, Callable, Iterator

from justpipe.middleware import Middleware
from justpipe.observability import validate_observer
from justpipe.types import (
    BarrierType,
    CancellationToken,
    Event,
    FailureClassificationConfig,
    Stop,
    StepInfo,
)
from justpipe.visualization import GraphRenderer, MermaidRenderer

from justpipe._internal.runtime.engine.composition import RunnerConfig, build_runner
from justpipe._internal.definition.pipeline_registry import _PipelineRegistry

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep
    from justpipe.observability import ObserverProtocol

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class Pipe(Generic[StateT, ContextT]):
    def __init__(
        self,
        state_type: type[StateT] | None = None,
        context_type: type[ContextT] | None = None,
        *,
        name: str = "Pipe",
        middleware: list[Middleware] | None = None,
        queue_size: int = 1000,
        max_map_items: int | None = None,
        debug: bool = False,
        cancellation_token: CancellationToken | None = None,
        failure_classification: FailureClassificationConfig | None = None,
    ):
        """Create a new pipeline with explicit type parameters.

        Args:
            state_type: The type of state (defaults to type(None))
            context_type: The type of context (defaults to type(None))
            name: Pipeline name
            middleware: list of middleware to apply
            queue_size: Max events in queue (backpressure)
            max_map_items: Max items to materialize from async generators in @pipe.map
            debug: Enable debug logging
            cancellation_token: Token for cooperative cancellation
            failure_classification: Optional config for terminal failure source
                classification. Supports a source classifier callback and extra
                external dependency module prefixes.
        """
        self.name = name
        self.queue_size = queue_size
        self.cancellation_token = cancellation_token or CancellationToken()
        self._failure_classification = (
            failure_classification or FailureClassificationConfig()
        )

        self.state_type: type[Any] = state_type or type(None)
        self.context_type: type[Any] = context_type or type(None)

        self.registry = _PipelineRegistry(
            pipe_name=name,
            middleware=middleware,
            state_type=self.state_type,
            context_type=self.context_type,
            max_map_items=max_map_items,
        )

        # Add debug observer if requested
        if debug:
            from justpipe.observability.logger import EventLogger

            self.add_observer(
                EventLogger(
                    level="INFO",
                    sink=EventLogger.stderr_sink(),
                    use_colors=True,
                )
            )

    # Internal properties for introspection and runner access
    @property
    def _steps(self) -> dict[str, _BaseStep]:
        return self.registry.steps

    @property
    def _topology(self) -> dict[str, list[str]]:
        return self.registry.topology

    @property
    def middleware(self) -> list[Middleware]:
        return self.registry.middleware

    def add_middleware(self, mw: Middleware) -> None:
        self.registry.add_middleware(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self.registry.add_event_hook(hook)

    def add_observer(self, observer: ObserverProtocol) -> None:
        """Add an observer to receive pipeline lifecycle events.

        Args:
            observer: An observer implementing on_pipeline_start,
                     on_event, on_pipeline_end, and on_pipeline_error methods.

        Raises:
            TypeError: If observer does not implement the required async hooks.

        Example:
            from justpipe.observability import Observer

            class MyObserver(Observer):
                async def on_event(self, state, context, meta, event):
                    print(f"Event: {event.type}")

            pipe.add_observer(MyObserver())
        """

        validate_observer(observer)
        self.registry.add_observer(observer)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.registry.on_startup(func)

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.registry.on_shutdown(func)

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.registry.on_error(func)

    def step(
        self,
        name: str | Callable[..., Any] | None = None,
        to: str
        | list[str]
        | Callable[..., Any]
        | list[Callable[..., Any]]
        | None = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        return self.registry.step_registry.step(
            name, to, barrier_timeout, barrier_type, on_error, **kwargs
        )

    def map(
        self,
        name: str | Callable[..., Any] | None = None,
        each: str | Callable[..., Any] | None = None,
        to: str
        | list[str]
        | Callable[..., Any]
        | list[Callable[..., Any]]
        | None = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        max_concurrency: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.registry.step_registry.map(
            name,
            each,
            to,
            barrier_timeout,
            barrier_type,
            on_error,
            max_concurrency,
            **kwargs,
        )

    def switch(
        self,
        name: str | Callable[..., Any] | None = None,
        to: dict[Any, str | Callable[..., Any] | type[Stop]]
        | Callable[[Any], str | type[Stop]]
        | None = None,
        default: str | Callable[..., Any] | None = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.registry.step_registry.switch(
            name,
            to,
            default,
            barrier_timeout,
            barrier_type,
            on_error,
            **kwargs,
        )

    def sub(
        self,
        name: str | Callable[..., Any] | None = None,
        pipeline: Any = None,
        to: str
        | list[str]
        | Callable[..., Any]
        | list[Callable[..., Any]]
        | None = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self.registry.step_registry.sub(
            name, pipeline, to, barrier_timeout, barrier_type, on_error, **kwargs
        )

    def graph(self, renderer: GraphRenderer | None = None) -> str:
        """
        Generate a visual representation of the pipeline.

        Args:
            renderer: Optional GraphRenderer instance (defaults to MermaidRenderer).

        Returns:
            A string representation of the graph.
        """
        effective_renderer = renderer or MermaidRenderer()
        return effective_renderer.render(
            self.registry.steps,
            self.registry.topology,
            startup_hooks=[hook.func for hook in self.registry.startup_hooks],
            shutdown_hooks=[hook.func for hook in self.registry.shutdown_hooks],
        )

    def steps(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        return self.registry.step_registry.get_steps_info()

    @property
    def topology(self) -> dict[str, list[str]]:
        """Read-only view of the execution graph."""
        return dict(self.registry.topology)

    def validate(self) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            DefinitionError: if any unresolvable references or integrity issues are found.
        """
        from justpipe._internal.graph.graph_validator import _GraphValidator

        graph = _GraphValidator(
            self.registry.steps,
            self.registry.topology,
        )
        graph.validate()

    async def run(
        self,
        state: StateT,
        context: ContextT | None = None,
        start: str | Callable[..., Any] | None = None,
        queue_size: int | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[Event, None]:
        self.validate()
        self.registry.finalize()
        self.registry.freeze()

        effective_queue_size = queue_size if queue_size is not None else self.queue_size
        config: RunnerConfig[StateT, ContextT] = RunnerConfig(
            steps=self.registry.steps,
            topology=self.registry.topology,
            injection_metadata=self.registry.injection_metadata,
            startup_hooks=self.registry.startup_hooks,
            shutdown_hooks=self.registry.shutdown_hooks,
            on_error=self.registry.error_hook,
            queue_size=effective_queue_size,
            event_hooks=self.registry.event_hooks,
            observers=self.registry.observers,
            pipe_name=self.name,
            cancellation_token=self.cancellation_token,
            failure_classification=self._failure_classification,
        )
        runner = build_runner(config)

        async for event in runner.run(state, context, start, timeout):
            yield event
