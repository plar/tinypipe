import asyncio
from dataclasses import dataclass
from typing import Any

from justpipe._internal.runtime.orchestration.control import (
    InvocationContext,
    StepCompleted,
)
from justpipe._internal.runtime.orchestration.protocols import TaskOrchestrator
from justpipe._internal.shared.execution_tracker import _ExecutionTracker
from justpipe.types import Event, EventType, NodeKind


@dataclass
class RecordedSpawn:
    coro: Any
    owner: str


@dataclass
class RecordedSchedule:
    name: str
    owner: str | None
    payload: dict[str, Any] | None
    parent_invocation_id: str | None = None
    owner_invocation_id: str | None = None
    scope: tuple[str, ...] = ()


class FakeOrchestrator(TaskOrchestrator[Any, Any]):
    def __init__(self, state: Any = None, context: Any = None):
        self._state = state
        self._context = context
        self._tracker = _ExecutionTracker()
        self.spawns: list[RecordedSpawn] = []
        self.schedules: list[RecordedSchedule] = []
        self.submissions: list[Any] = []

    @property
    def state(self) -> Any:
        return self._state

    @property
    def context(self) -> Any:
        return self._context

    @property
    def tracker(self) -> _ExecutionTracker:
        return self._tracker

    def schedule(
        self,
        name: str,
        owner: str | None = None,
        payload: dict[str, Any] | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None:
        self.schedules.append(
            RecordedSchedule(
                name,
                owner,
                payload,
                parent_invocation_id=parent_invocation_id,
                owner_invocation_id=owner_invocation_id,
                scope=scope,
            )
        )

    def spawn(
        self, coro: Any, owner: str, track_owner: bool = True
    ) -> asyncio.Task[Any] | None:
        self.spawns.append(RecordedSpawn(coro, owner))
        from unittest.mock import MagicMock

        return MagicMock(spec=asyncio.Task)

    async def submit(self, item: Any) -> None:
        self.submissions.append(item)

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
    ) -> None:
        self.submissions.append(
            Event(
                event_type,
                stage,
                payload,
                node_kind=node_kind,
                invocation_id=invocation_id,
                parent_invocation_id=parent_invocation_id,
                owner_invocation_id=owner_invocation_id,
                attempt=attempt,
                scope=scope,
                meta=meta,
            )
        )

    async def complete_step(
        self,
        name: str,
        owner: str,
        result: Any,
        payload: dict[str, Any] | None = None,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
        already_terminal: bool = False,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        self.submissions.append(
            StepCompleted(
                name,
                owner,
                result,
                payload,
                track_owner=track_owner,
                invocation=invocation,
                already_terminal=already_terminal,
                step_meta=step_meta,
            )
        )

    async def fail_step(
        self,
        name: str,
        owner: str,
        error: Exception,
        track_owner: bool = True,
        invocation: InvocationContext | None = None,
        step_meta: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            EventType.STEP_ERROR,
            name,
            str(error),
            node_kind=invocation.node_kind if invocation else NodeKind.STEP,
            invocation_id=invocation.invocation_id if invocation else None,
            parent_invocation_id=(
                invocation.parent_invocation_id if invocation else None
            ),
            owner_invocation_id=(
                invocation.owner_invocation_id if invocation else None
            ),
            attempt=invocation.attempt if invocation else 1,
            scope=invocation.scope if invocation else (),
        )
        await self.complete_step(
            owner,
            name,
            None,
            track_owner=track_owner,
            invocation=invocation,
            already_terminal=True,
        )

    async def execute_step(
        self,
        name: str,
        owner: str,
        payload: dict[str, Any] | None = None,
        invocation: InvocationContext | None = None,
        parent_invocation_id: str | None = None,
        owner_invocation_id: str | None = None,
        scope: tuple[str, ...] = (),
    ) -> None:
        pass

    def stop(self) -> None:
        pass

    def map_worker_started(self, owner: str, target: str) -> None:
        pass

    def map_worker_finished(self, owner: str, target: str) -> None:
        pass
