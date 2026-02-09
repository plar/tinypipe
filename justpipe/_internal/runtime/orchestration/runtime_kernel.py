from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import Callable

from justpipe._internal.shared.execution_tracker import _ExecutionTracker


class _RuntimeKernel:
    """Owns runtime queue/task-group/spawn/stop primitives."""

    def __init__(
        self,
        tracker: _ExecutionTracker,
        queue: asyncio.Queue[Any],
    ):
        self._tracker = tracker
        self._queue = queue
        self._task_group: asyncio.TaskGroup | None = None
        self._on_spawn: Callable[[int], None] | None = None
        self._on_submit_queue_depth: Callable[[int], None] | None = None

    @property
    def queue(self) -> asyncio.Queue[Any]:
        return self._queue

    def set_hooks(
        self,
        *,
        on_spawn: Callable[[int], None] | None = None,
        on_submit_queue_depth: Callable[[int], None] | None = None,
    ) -> None:
        self._on_spawn = on_spawn
        self._on_submit_queue_depth = on_submit_queue_depth

    def attach_task_group(self, task_group: asyncio.TaskGroup | None) -> None:
        self._task_group = task_group

    def request_stop(self) -> None:
        self._tracker.request_stop()

    def spawn(
        self,
        coro: Any,
        owner: str,
        track_owner: bool = True,
    ) -> asyncio.Task[Any] | None:
        if self._tracker.stopping or self._task_group is None:
            coro.close()
            return None

        self._tracker.record_spawn(owner, track_owner=track_owner)
        if self._on_spawn is not None:
            self._on_spawn(self._tracker.total_active_tasks)
        return self._task_group.create_task(coro)

    async def submit(self, item: Any) -> None:
        await self._queue.put(item)
        if self._on_submit_queue_depth is not None:
            self._on_submit_queue_depth(self._queue.qsize())
