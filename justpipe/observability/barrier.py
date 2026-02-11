"""Barrier diagnostics for parallel execution debugging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from justpipe.observability import Observer, ObserverMeta
from justpipe.observability._worker_cleanup import remove_worker_entries
from justpipe.types import Event, EventType


@dataclass(frozen=True, slots=True)
class BarrierDebugRecord:
    """Structured barrier diagnostic emitted by BarrierDebugger."""

    kind: str
    barrier_name: str
    wait_time_s: float
    expected_count: int
    completed_count: int
    waiting_for: tuple[str, ...]
    message: str


BarrierDebugSink = Callable[[BarrierDebugRecord], None]


class BarrierDebugger(Observer):
    """Observer that detects and records barrier stalls.

    Diagnostics are emitted as ``BarrierDebugRecord`` instances through the
    configured sink, which makes assertions deterministic in tests.
    """

    def __init__(
        self,
        warn_after: float,
        clock: Callable[[], float],
        sink: BarrierDebugSink | None = None,
    ):
        """Initialize barrier debugger.

        Args:
            warn_after: Threshold in seconds before a waiting barrier is warned.
            clock: Time provider used for inactive-worker diagnostics.
            sink: Optional sink receiving structured debug records.
        """
        self.warn_after = warn_after
        self._clock = clock
        self.sink = sink

        self.waiting_barriers: dict[str, dict[str, Any]] = {}
        self.worker_activity: dict[str, float] = {}
        self.warned_barriers: set[str] = set()

    def _emit(self, record: BarrierDebugRecord) -> None:
        if self.sink is not None:
            self.sink(record)

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        _ = (state, context, meta)
        self.waiting_barriers.clear()
        self.worker_activity.clear()
        self.warned_barriers.clear()

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        _ = (state, context, meta)
        if event.type == EventType.BARRIER_WAIT:
            metadata = event.payload if isinstance(event.payload, dict) else {}
            self.waiting_barriers[event.stage] = {
                "start_time": event.timestamp,
                "expected_count": metadata.get("expected_count", 0),
                "completed_count": metadata.get("completed_count", 0),
                "waiting_for": metadata.get("waiting_for", []),
                "timeout": metadata.get("timeout", 0),
            }
            return

        if event.type == EventType.BARRIER_RELEASE:
            if event.stage in self.waiting_barriers:
                info = self.waiting_barriers[event.stage]
                wait_time = event.timestamp - info["start_time"]

                if (
                    wait_time > self.warn_after
                    and event.stage not in self.warned_barriers
                ):
                    self._emit(
                        BarrierDebugRecord(
                            kind="slow",
                            barrier_name=event.stage,
                            wait_time_s=wait_time,
                            expected_count=int(info.get("expected_count", 0)),
                            completed_count=int(info.get("completed_count", 0)),
                            waiting_for=tuple(info.get("waiting_for", [])),
                            message=(
                                f"SLOW BARRIER: {event.stage} waited {wait_time:.1f}s "
                                f"(threshold: {self.warn_after:.1f}s)"
                            ),
                        )
                    )
                    self.warned_barriers.add(event.stage)

                del self.waiting_barriers[event.stage]
            return

        if event.type in {EventType.STEP_START, EventType.MAP_WORKER}:
            self.worker_activity[event.stage] = event.timestamp
            self._check_waiting_barriers(event.timestamp)
            return

        if event.type in {EventType.STEP_END, EventType.MAP_COMPLETE}:
            self.worker_activity.pop(event.stage, None)
            if event.type == EventType.MAP_COMPLETE and isinstance(event.payload, dict):
                target = event.payload.get("target")
                if isinstance(target, str):
                    remove_worker_entries(self.worker_activity, target)
            return

        if event.type == EventType.STEP_ERROR:
            self.worker_activity.pop(event.stage, None)

    def _check_waiting_barriers(self, current_time: float) -> None:
        for barrier_name, info in list(self.waiting_barriers.items()):
            wait_time = current_time - info["start_time"]
            if wait_time > self.warn_after and barrier_name not in self.warned_barriers:
                self._warn_barrier_hang(barrier_name, info, wait_time)
                self.warned_barriers.add(barrier_name)

    def _warn_barrier_hang(
        self, barrier_name: str, info: dict[str, Any], wait_time: float
    ) -> None:
        waiting_for = tuple(str(worker) for worker in info.get("waiting_for", []))
        activity_segments: list[str] = []
        for worker in waiting_for:
            if worker in self.worker_activity:
                # Worker was seen but has made no new progress for this duration.
                inactive_for = self._clock() - self.worker_activity[worker]
                activity_segments.append(f"{worker}: inactive {inactive_for:.1f}s")
            else:
                activity_segments.append(f"{worker}: never started")

        details = (
            ", ".join(activity_segments) if activity_segments else "no worker detail"
        )
        self._emit(
            BarrierDebugRecord(
                kind="hang",
                barrier_name=barrier_name,
                wait_time_s=wait_time,
                expected_count=int(info.get("expected_count", 0)),
                completed_count=int(info.get("completed_count", 0)),
                waiting_for=waiting_for,
                message=(
                    f"BARRIER HANG DETECTED: {barrier_name}; "
                    f"wait={wait_time:.1f}s; {details}"
                ),
            )
        )

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        _ = (state, context, meta, duration_s)
        for barrier_name, info in self.waiting_barriers.items():
            self._emit(
                BarrierDebugRecord(
                    kind="unresolved",
                    barrier_name=barrier_name,
                    wait_time_s=duration_s,
                    expected_count=int(info.get("expected_count", 0)),
                    completed_count=int(info.get("completed_count", 0)),
                    waiting_for=tuple(str(w) for w in info.get("waiting_for", [])),
                    message=f"Pipeline completed with unresolved barrier: {barrier_name}",
                )
            )
        self.waiting_barriers.clear()
        self.worker_activity.clear()
        self.warned_barriers.clear()

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        _ = (state, context, meta, error)
        for barrier_name, info in self.waiting_barriers.items():
            waiting_for = tuple(str(w) for w in info.get("waiting_for", []))
            self._emit(
                BarrierDebugRecord(
                    kind="error_state",
                    barrier_name=barrier_name,
                    wait_time_s=0.0,
                    expected_count=int(info.get("expected_count", 0)),
                    completed_count=int(info.get("completed_count", 0)),
                    waiting_for=waiting_for,
                    message=(
                        f"Pipeline failed with waiting barrier: {barrier_name}; "
                        f"waiting_for={len(waiting_for)}"
                    ),
                )
            )
        self.waiting_barriers.clear()
        self.worker_activity.clear()
        self.warned_barriers.clear()
