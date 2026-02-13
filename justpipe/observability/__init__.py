"""Observability and debugging tools for justpipe pipelines."""

import inspect
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from justpipe.types import Event


@dataclass(frozen=True, slots=True)
class ObserverMeta:
    """Framework metadata provided to all observer hooks."""

    pipe_name: str
    run_id: str | None = None
    started_at: float | None = None
    observer_version: int = 1


@runtime_checkable
class ObserverProtocol(Protocol):
    """Structural contract for pipeline observers."""

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None: ...

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None: ...

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None: ...

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None: ...


class Observer:
    """Optional mixin base class for pipeline observers.

    Observers receive lifecycle events and can implement custom monitoring,
    logging, storage, or debugging logic.

    Example:
        class MetricsCollector(Observer):
            def __init__(self):
                self.metrics = {}

            async def on_pipeline_start(self, state, context, meta):
                self.start_time = time.time()

            async def on_event(self, state, context, meta, event: Event):
                if event.type == EventType.STEP_END:
                    # Collect metrics
                    pass

            async def on_pipeline_end(self, state, context, meta, duration_s: float):
                print(f"Pipeline completed in {duration_s:.2f}s")

        pipe.add_observer(MetricsCollector())
    """

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Called before pipeline execution starts.

        Args:
            state: The initial pipeline state
            context: The pipeline context
            meta: Framework metadata for this pipeline run
        """
        return None

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Called for every pipeline event.

        Args:
            state: The current pipeline state
            context: The pipeline context
            meta: Framework metadata for this pipeline run
            event: The event emitted by the pipeline runtime
        """
        return None

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Called after pipeline completes successfully.

        Args:
            state: The final pipeline state
            context: The pipeline context
            meta: Framework metadata for this pipeline run
            duration_s: Total pipeline execution time in seconds
        """
        return None

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        """Called when pipeline fails with an unhandled error.

        Args:
            state: The pipeline state at time of error
            context: The pipeline context
            meta: Framework metadata for this pipeline run
            error: The exception that caused the failure
        """
        return None


def validate_observer(observer: object) -> None:
    """Validate observer contract and required async hook methods."""
    required_methods = tuple(
        name
        for name, obj in ObserverProtocol.__dict__.items()
        if callable(obj) and not name.startswith("_")
    )

    if not isinstance(observer, ObserverProtocol):
        missing = [
            name
            for name in required_methods
            if not callable(getattr(observer, name, None))
        ]
        if missing:
            missing_list = ", ".join(missing)
            raise TypeError(
                f"Observer {type(observer).__name__} is missing required hooks: "
                f"{missing_list}. Implement async methods matching "
                f"justpipe.observability.ObserverProtocol."
            )

    for name in required_methods:
        method = getattr(observer, name, None)
        if not callable(method) or not inspect.iscoroutinefunction(method):
            raise TypeError(
                f"Observer {type(observer).__name__}.{name} must be declared with "
                f"'async def' to match justpipe.observability.ObserverProtocol."
            )


# Import concrete observer implementations (after protocol/base definitions)
from justpipe.observability.logger import (  # noqa: E402
    EventLogger,
    LogRecord,
    LogSink,
    StreamLogSink,
)
from justpipe.observability.barrier import (  # noqa: E402
    BarrierDebugger,
    BarrierDebugRecord,
    BarrierDebugSink,
)
from justpipe.observability.metrics import MetricsCollector  # noqa: E402
from justpipe.observability.timeline import TimelineVisualizer  # noqa: E402
from justpipe.observability.state import StateDiffTracker  # noqa: E402
from justpipe.observability.compare import (  # noqa: E402
    compare_runs,
    RunComparison,
    format_comparison,
)

__all__ = [
    "Observer",
    "ObserverProtocol",
    "ObserverMeta",
    "validate_observer",
    "EventLogger",
    "LogRecord",
    "LogSink",
    "StreamLogSink",
    "BarrierDebugger",
    "BarrierDebugRecord",
    "BarrierDebugSink",
    "MetricsCollector",
    "TimelineVisualizer",
    "StateDiffTracker",
    "compare_runs",
    "RunComparison",
    "format_comparison",
]
