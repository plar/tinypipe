import asyncio
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from justpipe.types import (
    Event,
    EventType,
    InjectionMetadataMap,
    InjectionSource,
    NodeKind,
    _Map,
)
from justpipe._internal.runtime.orchestration.control import (
    InvocationContext,
    RuntimeEvent,
)

if TYPE_CHECKING:
    from justpipe._internal.runtime.orchestration.protocols import SchedulerOrchestrator
    from justpipe._internal.runtime.failure.failure_handler import _FailureHandler
    from justpipe._internal.definition.steps import _BaseStep


@dataclass(slots=True)
class _MapBatch:
    target: str
    item_count: int
    remaining: int
    owner_invocation_id: str | None
    owner_scope: tuple[str, ...]


class _Scheduler:
    """Internal scheduler for sub-pipelines and map operations."""

    def __init__(
        self,
        orchestrator: "SchedulerOrchestrator",
        failure_handler: "_FailureHandler",
        steps: dict[str, "_BaseStep"],
        injection_metadata: InjectionMetadataMap,
    ):
        self._orchestrator = orchestrator
        self._failure_handler = failure_handler
        self._steps = steps
        self._injection_metadata = injection_metadata
        self._map_batches: dict[str, list[_MapBatch]] = defaultdict(list)

    async def sub_pipe_wrapper(
        self,
        sub_pipe: Any,
        sub_state: Any,
        owner: str,
        context: Any,
        owner_invocation: InvocationContext | None = None,
    ) -> None:
        """Execute a sub-pipeline and stream its events."""
        name = f"{owner}:sub"
        owner_prefix = f"{owner}:"
        inv_id = owner_invocation.invocation_id if owner_invocation else None
        try:
            async for ev in sub_pipe.run(sub_state, context):
                meta = dict(ev.meta) if isinstance(ev.meta, dict) else None
                ev = Event(
                    type=ev.type,
                    stage=owner_prefix + ev.stage,
                    payload=ev.payload,
                    timestamp=ev.timestamp,
                    origin_run_id=ev.origin_run_id or ev.run_id,
                    parent_run_id=ev.run_id,
                    node_kind=ev.node_kind,
                    invocation_id=ev.invocation_id,
                    parent_invocation_id=inv_id,
                    owner_invocation_id=inv_id,
                    attempt=ev.attempt,
                    scope=((owner,) + ev.scope),
                    meta=meta,
                )
                await self._orchestrator.submit(RuntimeEvent(ev))
            await self._orchestrator.complete_step(name, owner, None)
        except Exception as e:
            await self._failure_handler.handle_failure(
                name,
                owner,
                e,
                None,
                self._orchestrator.state,
                context,
                invocation=owner_invocation,
            )

    async def handle_map(
        self,
        res: _Map,
        owner: str,
        owner_invocation: InvocationContext | None = None,
    ) -> None:
        """Handle fan-out mapping of items to workers."""
        item_count = len(res.items)

        # Extract invocation fields once to avoid repeated guards.
        inv_id = owner_invocation.invocation_id if owner_invocation else None
        parent_inv_id = (
            owner_invocation.parent_invocation_id if owner_invocation else None
        )
        owner_inv_id = (
            owner_invocation.owner_invocation_id if owner_invocation else None
        )
        attempt = owner_invocation.attempt if owner_invocation else 1
        scope = owner_invocation.scope if owner_invocation else ()

        self._map_batches[owner].append(
            _MapBatch(
                target=res.target,
                item_count=item_count,
                remaining=item_count,
                owner_invocation_id=inv_id,
                owner_scope=scope,
            )
        )

        # Emit MAP_START event
        await self._orchestrator.emit(
            EventType.MAP_START,
            owner,
            {
                "target": res.target,
                "item_count": item_count,
            },
            node_kind=NodeKind.MAP,
            invocation_id=inv_id,
            parent_invocation_id=parent_inv_id,
            owner_invocation_id=owner_inv_id,
            attempt=attempt,
            scope=scope,
        )

        # Check if max_concurrency is set for this map step
        step = self._steps.get(owner)
        semaphore: asyncio.Semaphore | None = None
        if step and hasattr(step, "max_concurrency") and step.max_concurrency:
            semaphore = asyncio.Semaphore(step.max_concurrency)

        for idx, m_item in enumerate(res.items):
            target_step = self._steps.get(res.target)
            payload = None
            if target_step:
                inj = self._injection_metadata.get(res.target, {})
                for p_name, p_source in inj.items():
                    if p_source == InjectionSource.UNKNOWN:
                        payload = {p_name: m_item}
                        break

            # Emit MAP_WORKER event for each item
            await self._orchestrator.emit(
                EventType.MAP_WORKER,
                f"{res.target}[{idx}]",
                {
                    "index": idx,
                    "total": item_count,
                    "target": res.target,
                    "owner": owner,
                },
                node_kind=NodeKind.MAP,
                invocation_id=inv_id,
                parent_invocation_id=parent_inv_id,
                owner_invocation_id=owner_inv_id,
                attempt=attempt,
                scope=scope,
            )

            # Schedule with optional throttling
            self._orchestrator.spawn(
                self.map_worker_wrapper(
                    res.target,
                    owner,
                    payload,
                    owner_invocation=owner_invocation,
                    map_index=idx,
                    semaphore=semaphore,
                ),
                owner,
            )

    def on_step_completed(self, owner: str, step_name: str) -> list[_MapBatch]:
        """Resolve any map batches that are now fully drained."""
        completed: list[_MapBatch] = []
        batches = self._map_batches.get(owner)
        if not batches:
            return completed

        # Empty maps complete when the map owner step itself completes.
        if step_name == owner:
            while batches and batches[0].remaining == 0:
                completed.append(batches.pop(0))
            if not batches:
                self._map_batches.pop(owner, None)
            return completed

        # Worker completion decrements the oldest matching batch.
        for batch in batches:
            if batch.target == step_name and batch.remaining > 0:
                batch.remaining -= 1
                if batch.remaining == 0:
                    completed.append(batch)
                break

        while batches and batches[0].remaining == 0:
            batches.pop(0)
        if not batches:
            self._map_batches.pop(owner, None)

        return completed

    async def map_worker_wrapper(
        self,
        name: str,
        owner: str,
        payload: dict[str, Any] | None,
        owner_invocation: InvocationContext | None = None,
        map_index: int | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        """Wrapper that tracks map-worker lifecycle with optional throttling."""
        inv_id = owner_invocation.invocation_id if owner_invocation else None
        scope = owner_invocation.scope if owner_invocation else ()
        if map_index is not None:
            scope = scope + (f"{name}[{map_index}]",)

        cm = semaphore if semaphore is not None else nullcontext()
        async with cm:
            self._orchestrator.map_worker_started(owner, name)
            try:
                await self._orchestrator.execute_step(
                    name,
                    owner,
                    payload,
                    parent_invocation_id=inv_id,
                    owner_invocation_id=inv_id,
                    scope=scope,
                )
            finally:
                self._orchestrator.map_worker_finished(owner, name)
