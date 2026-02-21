from __future__ import annotations

import os
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
from justpipe.visualization.builder import _PipelineASTBuilder

from justpipe._internal.runtime.engine.composition import RunnerConfig, build_runner
from justpipe._internal.shared.pipeline_hash import compute_pipeline_hash
from justpipe._internal.definition.pipeline_registry import _PipelineRegistry

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep
    from justpipe.observability import ObserverProtocol

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


def _resolve_bool_flag(explicit: bool | None, env_var: str) -> bool:
    """Resolve a boolean flag from explicit value or environment variable."""
    if explicit is not None:
        return explicit

    raw = os.getenv(env_var)
    if raw is None:
        return False

    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Pipe(Generic[StateT, ContextT]):
    def __init__(
        self,
        state_type: type[StateT] | None = None,
        context_type: type[ContextT] | None = None,
        *,
        name: str = "Pipe",
        strict: bool = True,
        allow_multi_root: bool = False,
        middleware: list[Middleware] | None = None,
        queue_size: int = 1000,
        max_map_items: int | None = None,
        debug: bool | None = None,
        cancellation_token: CancellationToken | None = None,
        failure_classification: FailureClassificationConfig | None = None,
        metadata: dict[str, Any] | None = None,
        persist: bool | None = None,
        flush_interval: int | None = None,
        max_retries: int = 100,
    ):
        """Create a new pipeline with explicit type parameters.

        Args:
            state_type: The type of state (defaults to type(None))
            context_type: The type of context (defaults to type(None))
            name: Pipeline name
            strict: Enable strict graph validation on run (default: True)
            allow_multi_root: Allow multiple roots when run() is called
                without start=. In strict mode this must be True to opt in.
            middleware: list of middleware to apply
            queue_size: Max events in queue (backpressure)
            max_map_items: Max items to materialize from async generators in @pipe.map
            debug: Enable debug logging. If None, uses JUSTPIPE_DEBUG env var.
            cancellation_token: Token for cooperative cancellation
            failure_classification: Optional config for terminal failure source
                classification. Supports a source classifier callback and extra
                external dependency module prefixes.
            metadata: Pipeline-level definition metadata (read-only at runtime
                via ``ctx.meta.pipeline``).
            persist: Enable local persistence of runs and events. If None,
                uses JUSTPIPE_PERSIST env var. Default: False.
            flush_interval: When persist is enabled, flush events to storage
                every *flush_interval* events to bound memory. None (default)
                buffers all events until pipeline completion.
            max_retries: Maximum number of retry attempts per step before
                treating as an error. Default: 100.
        """
        self.name = name
        self.strict = strict
        self.allow_multi_root = allow_multi_root
        self.queue_size = queue_size
        self.cancellation_token = cancellation_token or CancellationToken()
        self._failure_classification = (
            failure_classification or FailureClassificationConfig()
        )
        self._metadata = metadata or {}
        self._persist = _resolve_bool_flag(persist, "JUSTPIPE_PERSIST")
        self._flush_interval = flush_interval
        self._max_retries = max_retries

        # Lazy-cached persistence objects (stable after registry.freeze())
        self._cached_backend: Any = None
        self._cached_pipeline_hash: str | None = None
        self._cached_describe: dict[str, Any] | None = None

        self.state_type: type[Any] = state_type or type(None)
        self.context_type: type[Any] = context_type or type(None)

        self.registry = _PipelineRegistry(
            pipe_name=name,
            middleware=middleware,
            state_type=self.state_type,
            context_type=self.context_type,
            max_map_items=max_map_items,
        )

        # Add debug observer if requested (explicit flag or JUSTPIPE_DEBUG env var)
        if _resolve_bool_flag(debug, "JUSTPIPE_DEBUG"):
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
        """Register a fan-out map step that spawns a worker per item.

        Warning:
            Map workers execute concurrently and share the same state
            reference. If you use a mutable dataclass as state, writes
            from different workers can race. Use a frozen dataclass or
            explicit synchronization if workers need to update state.
        """
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

    def describe(self) -> dict[str, Any]:
        """Return a JSON-serializable pipeline snapshot.

        Includes pipeline identity, node definitions, topology, and metadata.
        """
        nodes: dict[str, dict[str, Any]] = {}
        for info in self.registry.step_registry.get_steps_info():
            node: dict[str, Any] = {
                "kind": info.kind.value,
                "targets": info.targets,
            }
            if info.timeout is not None:
                node["timeout"] = info.timeout
            if info.retries:
                node["retries"] = info.retries
            if info.barrier_timeout is not None:
                node["barrier_timeout"] = info.barrier_timeout
            if info.has_error_handler:
                node["has_error_handler"] = True
            if info.sub_pipeline_hash:
                node["sub_pipeline_hash"] = info.sub_pipeline_hash
            nodes[info.name] = node

        roots = [
            name
            for name in self.registry.steps
            if not any(name in targets for targets in self.registry.topology.values())
        ]

        hooks: dict[str, Any] = {}
        if self.registry.startup_hooks:
            hooks["startup"] = [h.func.__name__ for h in self.registry.startup_hooks]
        if self.registry.shutdown_hooks:
            hooks["shutdown"] = [h.func.__name__ for h in self.registry.shutdown_hooks]
        if self.registry.error_hook:
            hooks["on_error"] = self.registry.error_hook.func.__name__

        visual = _PipelineASTBuilder.build(
            self.registry.steps,
            dict(self.registry.topology),
            startup_hooks=[h.func for h in self.registry.startup_hooks],
            shutdown_hooks=[h.func for h in self.registry.shutdown_hooks],
        )

        return {
            "name": self.name,
            "pipeline_hash": compute_pipeline_hash(
                self.name, self.registry.steps, self.registry.topology
            ),
            "nodes": nodes,
            "topology": dict(self.registry.topology),
            "roots": roots,
            "metadata": dict(self._metadata),
            "hooks": hooks,
            "visual_ast": visual.to_dict(),
        }

    def steps(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        return self.registry.step_registry.get_steps_info()

    @property
    def topology(self) -> dict[str, list[str]]:
        """Read-only view of the execution graph."""
        return dict(self.registry.topology)

    def validate(
        self,
        start: str | Callable[..., Any] | None = None,
        strict: bool | None = None,
        allow_multi_root: bool | None = None,
    ) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            DefinitionError: if any unresolvable references or integrity issues are found.
        """
        from justpipe._internal.graph.graph_validator import _GraphValidator

        effective_strict = self.strict if strict is None else strict
        effective_allow_multi_root = (
            self.allow_multi_root if allow_multi_root is None else allow_multi_root
        )
        graph = _GraphValidator(
            self.registry.steps,
            self.registry.topology,
            state_type=self.state_type,
        )
        graph.validate(
            start=start,
            strict=effective_strict,
            allow_multi_root=effective_allow_multi_root,
        )

    def _get_observers(self) -> list[ObserverProtocol]:
        """Assemble the observer list for a pipeline run."""
        observers = list(self.registry.observers)

        if self._persist:
            from justpipe._internal.runtime.persistence import (
                _AutoPersistenceObserver,
            )

            if self._cached_backend is None:
                from justpipe._internal.shared.utils import resolve_storage_path
                from justpipe.storage.sqlite import SQLiteBackend

                self._cached_pipeline_hash = compute_pipeline_hash(
                    self.name, self.registry.steps, self.registry.topology
                )
                storage_dir = resolve_storage_path() / self._cached_pipeline_hash
                storage_dir.mkdir(parents=True, exist_ok=True)
                self._cached_backend = SQLiteBackend(storage_dir / "runs.db")
                self._cached_describe = self.describe()

            observers.append(
                _AutoPersistenceObserver(
                    backend=self._cached_backend,
                    pipeline_hash=self._cached_pipeline_hash,  # type: ignore[arg-type]
                    describe_snapshot=self._cached_describe,  # type: ignore[arg-type]
                    flush_interval=self._flush_interval,
                )
            )

        return observers

    async def run(
        self,
        state: StateT,
        context: ContextT | None = None,
        start: str | Callable[..., Any] | None = None,
        queue_size: int | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[Event, None]:
        self.validate(start=start)
        self.registry.finalize()
        self.registry.freeze()

        observers = self._get_observers()

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
            observers=observers or None,
            pipe_name=self.name,
            cancellation_token=self.cancellation_token,
            failure_classification=self._failure_classification,
            pipe_metadata=self._metadata,
            max_retries=self._max_retries,
        )
        runner = build_runner(config)

        async for event in runner.run(state, context, start, timeout):
            yield event
