import asyncio
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
    TYPE_CHECKING,
)

from justpipe.types import EventType, NodeKind

if TYPE_CHECKING:
    from justpipe._internal.runtime.orchestration.control import InvocationContext

if TYPE_CHECKING:
    from justpipe._internal.shared.execution_tracker import _ExecutionTracker

StateT = TypeVar("StateT", covariant=True)
ContextT = TypeVar("ContextT", covariant=True)


@runtime_checkable
class StateContextView(Protocol):
    """Read-only state/context access for managers that need snapshots."""

    @property
    def state(self) -> Any | None: ...

    @property
    def context(self) -> Any | None: ...


@runtime_checkable
class TrackerView(Protocol):
    """Read-only execution tracker access."""

    @property
    def tracker(self) -> "_ExecutionTracker": ...


@runtime_checkable
class SchedulePort(Protocol):
    """Step scheduling control."""

    def schedule(
        self,
        name: str,
        owner: str | None = None,
        payload: dict[str, Any] | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None: ...


@runtime_checkable
class SpawnPort(Protocol):
    """Concurrent task spawning control."""

    def spawn(
        self,
        coro: Any,
        owner: str,
        track_owner: bool = True,
    ) -> asyncio.Task[Any] | None: ...


@runtime_checkable
class QueueSubmitPort(Protocol):
    """Low-level queue submit primitive."""

    async def submit(self, item: Any) -> None: ...


@runtime_checkable
class EventEmitPort(Protocol):
    """Event emission primitive."""

    async def emit(
        self,
        event_type: EventType,
        stage: str,
        payload: Any = None,
        *,
        node_kind: NodeKind = NodeKind.SYSTEM,
        invocation_id: str | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        attempt: int = 1,
        scope: tuple[str, ...] = (),
        meta: dict[str, Any] | None = None,
    ) -> None: ...


@runtime_checkable
class StepCompletionPort(Protocol):
    """Step completion reporting."""

    async def complete_step(
        self,
        owner: str,
        name: str,
        result: Any,
        payload: dict[str, Any] | None = None,
        track_owner: bool = True,
        invocation: "InvocationContext | None" = None,
        already_terminal: bool = False,
    ) -> None: ...


@runtime_checkable
class StepFailurePort(Protocol):
    """Step failure reporting."""

    async def fail_step(
        self,
        owner: str,
        name: str,
        error: Exception,
        track_owner: bool = True,
        invocation: "InvocationContext | None" = None,
    ) -> None: ...


@runtime_checkable
class StepExecutionPort(Protocol):
    """Direct step execution + map worker accounting."""

    async def execute_step(
        self,
        name: str,
        owner: str,
        payload: dict[str, Any] | None = None,
        invocation: "InvocationContext | None" = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None: ...

    def map_worker_started(self, owner: str, target: str) -> None: ...

    def map_worker_finished(self, owner: str, target: str) -> None: ...


@runtime_checkable
class StopPort(Protocol):
    """Stop further scheduling/execution."""

    def stop(self) -> None: ...


@runtime_checkable
class InvokerOrchestrator(EventEmitPort, Protocol):
    """Narrow contract required by _StepInvoker."""


@runtime_checkable
class FailureHandlingOrchestrator(
    StepCompletionPort,
    StepFailurePort,
    EventEmitPort,
    StopPort,
    Protocol,
):
    """Narrow contract required by _FailureHandler."""


@runtime_checkable
class BarrierOrchestrator(
    StateContextView,
    TrackerView,
    SchedulePort,
    SpawnPort,
    EventEmitPort,
    StepCompletionPort,
    Protocol,
):
    """Narrow contract required by _BarrierManager."""


@runtime_checkable
class SchedulerOrchestrator(
    StateContextView,
    QueueSubmitPort,
    EventEmitPort,
    SchedulePort,
    SpawnPort,
    StepCompletionPort,
    StepExecutionPort,
    Protocol,
):
    """Narrow contract required by _Scheduler."""


@runtime_checkable
class ResultOrchestrator(
    TrackerView,
    SchedulePort,
    SpawnPort,
    StopPort,
    Protocol,
):
    """Narrow contract required by _ResultHandler."""


@runtime_checkable
class TaskOrchestrator(
    StateContextView,
    TrackerView,
    SchedulePort,
    SpawnPort,
    QueueSubmitPort,
    EventEmitPort,
    StepCompletionPort,
    StepFailurePort,
    StepExecutionPort,
    StopPort,
    Protocol[StateT, ContextT],
):
    """Aggregate orchestrator contract for the concrete runtime runner."""
