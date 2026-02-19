from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from justpipe.types import (
    BarrierMetrics,
    Event,
    EventType,
    MapMetrics,
    QueueMetrics,
    RuntimeMetrics,
    StepTiming,
    TaskMetrics,
)


@dataclass
class _StepAccumulator:
    count: int = 0
    total: float = 0.0
    min: float = float("inf")
    max: float = 0.0


@dataclass
class _BarrierAccumulator:
    waits: int = 0
    releases: int = 0
    timeouts: int = 0
    total: float = 0.0
    max: float = 0.0


class _RuntimeMetricsRecorder:
    """Lightweight in-run metrics accumulator for built-in FINISH payload."""

    def __init__(self) -> None:
        # Queue depth
        self._max_queue_depth = 0

        # Task counts
        self._tasks_started = 0
        self._tasks_completed = 0
        self._active_tasks = 0
        self._peak_active = 0

        # Events
        self._event_counts: dict[str, int] = defaultdict(int)
        self._tokens = 0
        self._suspends = 0

        # Step timing (keyed by invocation_id to handle concurrent map workers)
        self._step_start_times: dict[
            str, tuple[str, float]
        ] = {}  # inv_id -> (stage, ts)
        self._step_stats: dict[str, _StepAccumulator] = defaultdict(_StepAccumulator)

        # Barriers
        self._barrier_starts: dict[str, float] = {}
        self._barrier_stats: dict[str, _BarrierAccumulator] = defaultdict(
            _BarrierAccumulator
        )

        # Map fan-out
        self._maps_started = 0
        self._maps_completed = 0
        self._map_workers_started = 0
        self._current_map_workers = 0
        self._peak_map_workers = 0

    def record_map_worker_started(self, owner: str, target: str) -> None:
        # owner/target kept for future per-map granularity.
        _ = (owner, target)
        self._map_workers_started += 1
        self._current_map_workers += 1
        self._peak_map_workers = max(self._peak_map_workers, self._current_map_workers)

    def record_map_worker_finished(self, owner: str, target: str) -> None:
        _ = (owner, target)
        if self._current_map_workers > 0:
            self._current_map_workers -= 1

    # --- Queue / task accounting -------------------------------------------------
    def record_queue_depth(self, depth: int) -> None:
        if depth > self._max_queue_depth:
            self._max_queue_depth = depth

    def record_task_spawn(self, active_after: int) -> None:
        self._tasks_started += 1
        self._active_tasks = active_after
        if self._active_tasks > self._peak_active:
            self._peak_active = self._active_tasks

    def record_task_completion(self, active_after: int) -> None:
        self._tasks_completed += 1
        self._active_tasks = active_after

    # --- Event processing --------------------------------------------------------
    async def on_event(self, event: Event) -> None:
        self._event_counts[event.type.value] += 1

        if event.type == EventType.TOKEN:
            self._tokens += 1
        elif event.type == EventType.SUSPEND:
            self._suspends += 1

        elif event.type == EventType.STEP_START:
            key = event.invocation_id or event.stage
            self._step_start_times[key] = (event.stage, event.timestamp)
        elif event.type == EventType.STEP_END:
            key = event.invocation_id or event.stage
            entry = self._step_start_times.pop(key, None)
            if entry is not None:
                stage, start = entry
                # Prefer monotonic duration from step meta when available
                meta_duration = None
                if isinstance(event.meta, dict):
                    fw = event.meta.get("framework")
                    if isinstance(fw, dict):
                        meta_duration = fw.get("duration_s")
                duration = (
                    meta_duration
                    if meta_duration is not None
                    else max(0.0, event.timestamp - start)
                )
                step_stats = self._step_stats[stage]
                step_stats.count += 1
                step_stats.total += duration
                step_stats.min = min(step_stats.min, duration)
                step_stats.max = max(step_stats.max, duration)

        elif event.type == EventType.BARRIER_WAIT:
            self._barrier_starts[event.stage] = event.timestamp
            barrier_stats = self._barrier_stats[event.stage]
            barrier_stats.waits += 1

        elif event.type == EventType.BARRIER_RELEASE:
            barrier_start: float | None = self._barrier_starts.pop(event.stage, None)
            barrier_stats = self._barrier_stats[event.stage]
            barrier_stats.releases += 1
            if barrier_start is not None:
                duration = max(0.0, event.timestamp - barrier_start)
                barrier_stats.total += duration
                barrier_stats.max = max(barrier_stats.max, duration)

        elif event.type == EventType.MAP_START:
            self._maps_started += 1
        elif event.type == EventType.MAP_COMPLETE:
            self._maps_completed += 1
            # MAP_COMPLETE is emitted after map workers drain; worker count should
            # already be near zero from worker STEP_END processing.
        elif event.type == EventType.STEP_ERROR:
            if event.stage in self._barrier_starts:
                barrier_stats = self._barrier_stats[event.stage]
                barrier_stats.timeouts += 1
                del self._barrier_starts[event.stage]

    # --- Snapshot ----------------------------------------------------------------
    def snapshot(self) -> RuntimeMetrics:
        step_latency = {
            name: StepTiming(
                count=stats.count,
                total_s=stats.total,
                min_s=0.0 if stats.count == 0 else stats.min,
                max_s=stats.max,
            )
            for name, stats in self._step_stats.items()
        }

        barrier_metrics = {
            name: BarrierMetrics(
                waits=stats.waits,
                releases=stats.releases,
                timeouts=stats.timeouts,
                total_wait_s=stats.total,
                max_wait_s=stats.max,
            )
            for name, stats in self._barrier_stats.items()
        }

        return RuntimeMetrics(
            queue=QueueMetrics(max_depth=self._max_queue_depth),
            tasks=TaskMetrics(
                started=self._tasks_started,
                completed=self._tasks_completed,
                peak_active=self._peak_active,
            ),
            step_latency=step_latency,
            barriers=barrier_metrics,
            maps=MapMetrics(
                maps_started=self._maps_started,
                maps_completed=self._maps_completed,
                workers_started=self._map_workers_started,
                peak_workers=self._peak_map_workers,
            ),
            events=dict(self._event_counts),
            tokens=self._tokens,
            suspends=self._suspends,
        )
