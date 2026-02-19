import asyncio
from typing import Any, TYPE_CHECKING

from justpipe.types import EventType, NodeKind

if TYPE_CHECKING:
    from justpipe._internal.runtime.orchestration.protocols import BarrierOrchestrator
    from justpipe._internal.graph.dependency_graph import _DependencyGraph
    from justpipe._internal.runtime.failure.failure_handler import _FailureHandler


class _BarrierManager:
    """Internal manager for barrier synchronization and timeouts."""

    def __init__(
        self,
        orchestrator: "BarrierOrchestrator",
        graph: "_DependencyGraph",
        failure_handler: "_FailureHandler",
        parents_map: dict[str, set[str]] | None = None,
    ):
        self._orchestrator = orchestrator
        self._graph = graph
        self._failure_handler = failure_handler
        self._parents_map = parents_map

        # State
        self._barrier_tasks: dict[str, asyncio.Task[Any]] = {}
        self._barrier_events: dict[str, asyncio.Event] = {}
        self._failed_barriers: set[str] = set()

    def stop(self) -> None:
        """Cancel and clear all orphaned barrier tasks."""
        for task in self._barrier_tasks.values():
            if not task.done():
                task.cancel()
        self._barrier_tasks.clear()
        self._barrier_events.clear()

    def handle_completion(self, owner: str) -> None:
        """Process step completion and trigger transitions/barriers."""
        if self._orchestrator.tracker.consume_skip(owner):
            return

        result = self._graph.transition(owner)

        for barrier_node in result.barriers_to_cancel:
            # Signal event to wake up watcher (satisfied before timeout)
            event = self._barrier_events.get(barrier_node)
            if event:
                event.set()

        for step_name in result.steps_to_start:
            if step_name not in self._failed_barriers:
                self._orchestrator.schedule(step_name)

        for barrier_node, timeout in result.barriers_to_schedule:
            if barrier_node not in self._failed_barriers:
                event = asyncio.Event()
                self._barrier_events[barrier_node] = event
                task = self._orchestrator.spawn(
                    self._barrier_timeout_watcher(barrier_node, timeout, event),
                    barrier_node,
                    track_owner=False,
                )
                if task:
                    self._barrier_tasks[barrier_node] = task

    async def _barrier_timeout_watcher(
        self, name: str, timeout: float, event: asyncio.Event
    ) -> None:
        """Watch for barrier satisfaction or timeout."""
        # Emit BARRIER_WAIT event when barrier starts waiting
        dependencies = (
            list(self._parents_map.get(name, [])) if self._parents_map else []
        )
        await self._orchestrator.emit(
            EventType.BARRIER_WAIT,
            name,
            {
                "timeout": timeout,
                "dependencies": dependencies,
                "expected_count": len(dependencies),
                "completed_count": 0,
                "waiting_for": dependencies,
            },
            node_kind=NodeKind.BARRIER,
        )

        try:
            # Wait for timeout OR satisfaction (via event.set())
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._failed_barriers.add(name)
            await self._failure_handler.handle_failure(
                name,
                name,
                TimeoutError(f"Barrier timeout for step '{name}' after {timeout}s"),
                None,
                self._orchestrator.state,
                self._orchestrator.context,
                track_owner=False,
            )
        else:
            # Satisfied before timeout
            await self._orchestrator.emit(
                EventType.BARRIER_RELEASE,
                name,
                {"duration": 0},
                node_kind=NodeKind.BARRIER,
            )
            await self._orchestrator.complete_step(name, name, None, track_owner=False)
        finally:
            self._barrier_events.pop(name, None)
            self._barrier_tasks.pop(name, None)
