from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from collections.abc import Callable
import asyncio
import time


class DefinitionError(Exception):
    """Raised when a pipeline or step is defined incorrectly."""

    pass


class EventType(Enum):
    # Pipeline lifecycle
    START = "start"
    FINISH = "finish"
    SUSPEND = "suspend"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

    # Step execution
    STEP_START = "step_start"
    STEP_END = "step_end"
    STEP_ERROR = "step_error"
    TOKEN = "token"

    # Parallel execution
    BARRIER_WAIT = "barrier_wait"
    BARRIER_RELEASE = "barrier_release"
    MAP_START = "map_start"
    MAP_WORKER = "map_worker"
    MAP_COMPLETE = "map_complete"

    # State tracking
    STATE_CHANGE = "state_change"


class NodeKind(Enum):
    """Classifies the runtime source node for an event."""

    SYSTEM = "system"
    STEP = "step"
    MAP = "map"
    SWITCH = "switch"
    SUB = "sub"
    BARRIER = "barrier"


class BarrierType(Enum):
    """Defines how a step waits for its upstream dependencies (parents)."""

    ALL = "all"  # Wait for ALL parents to complete (default)
    ANY = "any"  # Run as soon as ANY parent completes (first one wins, subsequent ignored)


class InjectionSource(str, Enum):
    """Sources for dependency injection in steps and hooks."""

    STATE = "state"
    CONTEXT = "context"
    ERROR = "error"
    STEP_NAME = "step_name"
    CANCEL = "cancel"
    UNKNOWN = "unknown"


InjectionMetadata = dict[str, InjectionSource]
InjectionMetadataMap = dict[str, InjectionMetadata]


@dataclass(frozen=True)
class Event:
    """Runtime event envelope emitted by pipeline execution.

    Correlation and ordering fields are split across:
    - run lineage (`run_id`, `origin_run_id`, `parent_run_id`, `seq`)
    - invocation lineage (`invocation_id`, `parent_invocation_id`,
      `owner_invocation_id`, `attempt`, `scope`)
    """

    # Event category (lifecycle, step, map, barrier, etc.).
    type: EventType

    # Logical pipeline node name that produced the event.
    stage: str

    # Primary payload for this event (token text, errors, terminal payload, etc.).
    payload: Any = None

    # Wall-clock timestamp (seconds since epoch).
    timestamp: float = field(default_factory=time.time)

    # Stream/root run ID for the current `pipe.run(...)` event stream.
    # This is stable for all events yielded by a single run.
    run_id: str | None = None

    # Original source run ID where this event was first produced.
    # For non-forwarded events this equals `run_id`.
    origin_run_id: str | None = None

    # Immediate parent run ID that forwarded this event into the current stream.
    # None when the event is native to the current run.
    parent_run_id: str | None = None

    # Monotonic sequence number within the current stream (`run_id`).
    # This is the authoritative event order for consumers.
    seq: int | None = None

    # Kind of runtime node that emitted the event.
    node_kind: NodeKind = NodeKind.SYSTEM

    # Unique ID for one concrete step invocation attempt.
    invocation_id: str | None = None

    # Direct causal parent invocation that scheduled this invocation.
    parent_invocation_id: str | None = None

    # Composite owner/grouping anchor (e.g., map owner, sub owner).
    owner_invocation_id: str | None = None

    # Retry attempt index for this invocation lineage.
    attempt: int = 1

    # Hierarchical scope path for nested execution contexts.
    scope: tuple[str, ...] = field(default_factory=tuple)

    # Optional extension bag for cross-cutting metadata.
    # Canonical event content must live in `payload` (not duplicated here).
    meta: dict[str, Any] | None = None


# Event schema version (for observability consumers)
EVENT_SCHEMA_VERSION = "1.0"


class PipelineTerminalStatus(Enum):
    """Top-level terminal outcomes for a pipeline run."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CLIENT_CLOSED = "client_closed"


class FailureKind(Enum):
    """Lifecycle area where a failure occurred."""

    NONE = "none"
    VALIDATION = "validation"
    STARTUP = "startup"
    STEP = "step"
    SHUTDOWN = "shutdown"
    INFRA = "infra"


class FailureSource(Enum):
    """Source responsible for a failure."""

    NONE = "none"
    USER_CODE = "user_code"
    FRAMEWORK = "framework"
    EXTERNAL_DEP = "external_dep"


class FailureReason(str, Enum):
    """Canonical machine-readable reason codes for terminal outcomes."""

    VALIDATION_ERROR = "validation_error"
    STARTUP_HOOK_ERROR = "startup_hook_error"
    STEP_ERROR = "step_error"
    SHUTDOWN_HOOK_ERROR = "shutdown_hook_error"
    INTERNAL_ERROR = "internal_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CLIENT_CLOSED = "client_closed"
    NO_STEPS = "no_steps"
    CLASSIFIER_ERROR = "classifier_error"


@dataclass(frozen=True)
class FailureClassificationContext:
    """Context passed to user-defined failure source classifiers."""

    error: Exception | None
    kind: FailureKind
    reason: FailureReason
    step: str | None
    default_source: FailureSource


FailureSourceClassifier = Callable[[FailureClassificationContext], FailureSource | None]


@dataclass(frozen=True)
class FailureClassificationConfig:
    """Configuration for failure source attribution."""

    source_classifier: FailureSourceClassifier | None = None
    external_dependency_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueueMetrics:
    """Queue depth statistics for a single pipeline run."""

    max_depth: int


@dataclass(frozen=True)
class TaskMetrics:
    """Execution task accounting."""

    started: int
    completed: int
    peak_active: int


@dataclass(frozen=True)
class StepTiming:
    """Per-step latency summary (seconds)."""

    count: int
    total_s: float
    min_s: float
    max_s: float

    @property
    def avg_s(self) -> float:
        return self.total_s / self.count if self.count else 0.0


@dataclass(frozen=True)
class BarrierMetrics:
    """Barrier wait statistics."""

    waits: int
    releases: int
    timeouts: int
    total_wait_s: float
    max_wait_s: float


@dataclass(frozen=True)
class MapMetrics:
    """Map fan-out / worker accounting."""

    maps_started: int
    maps_completed: int
    workers_started: int
    peak_workers: int


@dataclass(frozen=True)
class RuntimeMetrics:
    """Built-in runtime metrics emitted with the FINISH event."""

    queue: QueueMetrics
    tasks: TaskMetrics
    step_latency: dict[str, StepTiming]
    barriers: dict[str, BarrierMetrics]
    maps: MapMetrics
    events: dict[str, int]
    tokens: int
    suspends: int


@dataclass(frozen=True)
class FailureRecord:
    """Detailed failure entry for terminal diagnostics."""

    kind: FailureKind
    source: FailureSource
    reason: str
    error: str | None = None
    step: str | None = None


@dataclass(frozen=True)
class PipelineEndData:
    """Structured payload for FINISH events."""

    status: PipelineTerminalStatus
    duration_s: float
    error: str | None = None
    reason: str | None = None
    failure_kind: FailureKind = FailureKind.NONE
    failure_source: FailureSource = FailureSource.NONE
    failed_step: str | None = None
    errors: list[FailureRecord] = field(default_factory=list)
    metrics: RuntimeMetrics | None = None


@dataclass(frozen=True)
class Stop:
    """Sentinel to stop pipeline execution in switch routes."""

    pass


@dataclass
class _Next:
    target: str | Callable[..., Any] | None


@dataclass
class _Map:
    items: list[Any]
    target: str


@dataclass
class _Run:
    pipe: Any  # Avoid circular import, typed as Any
    state: Any


@dataclass
class Suspend:
    reason: str


@dataclass
class Retry:
    """Primitive to signal the runner to retry the current step."""

    pass


@dataclass
class Skip:
    """Primitive to signal the runner to skip the current step and its children."""

    pass


@dataclass
class Raise:
    """Primitive to signal the runner to propagate the exception."""

    exception: Exception | None = None


@dataclass
class StepContext:
    """Context passed to middleware containing step metadata."""

    name: str
    kwargs: dict[str, Any]
    pipe_name: str
    retries: int | dict[str, Any] = 0


@dataclass
class StepInfo:
    """Information about a registered step for introspection."""

    name: str
    timeout: float | None
    retries: int | dict[str, Any]
    barrier_timeout: float | None
    has_error_handler: bool
    targets: list[str]
    kind: str  # "step", "map", or "switch"


@dataclass
class HookSpec:
    """Lifecycle hook with its injection metadata."""

    func: Callable[..., Any]
    injection_metadata: InjectionMetadata


class PipelineCancelled(Exception):
    """Raised when pipeline is cancelled via CancellationToken."""

    pass


class CancellationToken:
    """Token for cooperative cancellation of pipeline execution.

    Example:
        cancel = CancellationToken()
        pipe = Pipe(cancellation_token=cancel)

        @pipe.step()
        async def long_task(state, cancel: CancellationToken):
            for i in range(1000):
                await cancel.checkpoint()  # Raises if cancelled
                await process_item(i)

        # From another task/thread
        cancel.cancel(reason="User requested cancellation")
    """

    def __init__(self) -> None:
        self._cancelled = asyncio.Event()
        self._reason: str | None = None

    def cancel(self, reason: str = "Cancelled") -> None:
        """Request cancellation.

        Args:
            reason: Human-readable reason for cancellation
        """
        if not self._cancelled.is_set():
            self._reason = reason
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested.

        Returns:
            True if cancel() has been called
        """
        return self._cancelled.is_set()

    async def checkpoint(self) -> None:
        """Check for cancellation and raise if cancelled.

        This is the main method to call in long-running steps to support
        cooperative cancellation.

        Raises:
            PipelineCancelled: If cancellation has been requested
        """
        if self.is_cancelled():
            raise PipelineCancelled(self._reason or "Cancelled")

    @property
    def reason(self) -> str | None:
        """Get the cancellation reason if cancelled, None otherwise."""
        return self._reason if self.is_cancelled() else None
