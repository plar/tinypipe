"""Metrics collection observer for pipeline performance analysis."""

import time
from collections import defaultdict
from typing import Any
from collections.abc import Callable

from justpipe.observability import Observer, ObserverMeta
from justpipe.observability._worker_cleanup import remove_worker_entries
from justpipe.types import Event, EventType


class MetricsCollector(Observer):
    """Observer that collects performance metrics during pipeline execution.

    Tracks:
    - Total pipeline duration
    - Per-step execution time (min/avg/max)
    - Parallel worker counts
    - Event counts by type
    - Error counts (total and per-step)
    - Token counts (for streaming steps)
    - Retry counts

    Example:
        from justpipe.observability import MetricsCollector

        # Uses time.monotonic() by default.
        metrics = MetricsCollector()
        pipe.add_observer(metrics)

        # For deterministic tests, provide a custom clock:
        # metrics = MetricsCollector(clock=fake_clock)

        async for event in pipe.run(state):
            pass

        # Print summary
        print(metrics.summary())

        # Or access metrics directly
        print(f"Total duration: {metrics.total_duration:.2f}s")
        print(f"Bottleneck: {metrics.get_bottleneck()}")
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        """Initialize MetricsCollector.

        Args:
            clock: Time provider used for duration calculations. Defaults to
                ``time.monotonic`` when not provided.
        """
        self._clock = clock if clock is not None else time.monotonic
        # Timing
        self.total_duration: float = 0.0
        self.start_time: float | None = None
        self.step_start_times: dict[str, float] = {}
        self.step_durations: dict[str, list[float]] = defaultdict(list)

        # Counts
        self.event_counts: dict[str, int] = defaultdict(int)
        self.error_count: int = 0
        self.error_counts_by_step: dict[str, int] = defaultdict(int)
        self.token_count: int = 0
        self.retry_count: int = 0

        # Parallel execution
        self.max_parallel_workers: int = 0
        self.active_workers: set[str] = set()

        # Barriers
        self.barrier_wait_times: dict[str, float] = {}
        self.barrier_start_times: dict[str, float] = {}

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Record pipeline start time."""
        _ = (state, context, meta)
        # Reset state for per-run metrics when observer is reused.
        self.total_duration = 0.0
        self.start_time = self._clock()
        self.step_start_times.clear()
        self.step_durations.clear()
        self.event_counts.clear()
        self.error_count = 0
        self.error_counts_by_step.clear()
        self.token_count = 0
        self.retry_count = 0
        self.max_parallel_workers = 0
        self.active_workers.clear()
        self.barrier_wait_times.clear()
        self.barrier_start_times.clear()

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Track metrics from events."""
        _ = (state, context, meta)
        # Count all events
        self.event_counts[event.type.value] += 1

        if event.type == EventType.STEP_START:
            self.step_start_times[event.stage] = event.timestamp
            self.active_workers.add(event.stage)
            self.max_parallel_workers = max(
                self.max_parallel_workers, len(self.active_workers)
            )

        elif event.type == EventType.STEP_END:
            if event.stage in self.step_start_times:
                duration = event.timestamp - self.step_start_times[event.stage]
                self.step_durations[event.stage].append(duration)
                del self.step_start_times[event.stage]

            if event.stage in self.active_workers:
                self.active_workers.remove(event.stage)

        elif event.type == EventType.STEP_ERROR:
            self.error_count += 1
            self.error_counts_by_step[event.stage] += 1

        elif event.type == EventType.TOKEN:
            self.token_count += 1

        elif event.type == EventType.BARRIER_WAIT:
            self.barrier_start_times[event.stage] = event.timestamp

        elif event.type == EventType.BARRIER_RELEASE:
            if event.stage in self.barrier_start_times:
                wait_time = event.timestamp - self.barrier_start_times[event.stage]
                self.barrier_wait_times[event.stage] = wait_time
                del self.barrier_start_times[event.stage]

        elif event.type == EventType.MAP_WORKER:
            self.active_workers.add(event.stage)
            self.max_parallel_workers = max(
                self.max_parallel_workers, len(self.active_workers)
            )
        elif event.type == EventType.MAP_COMPLETE and isinstance(event.payload, dict):
            target = event.payload.get("target")
            if isinstance(target, str):
                remove_worker_entries(self.active_workers, target)

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Record total pipeline duration."""
        _ = (state, context, meta)
        self.total_duration = duration_s
        self.step_start_times.clear()
        self.active_workers.clear()
        self.barrier_start_times.clear()

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        """Record pipeline failure."""
        _ = (context, meta, error)
        if self.start_time:
            self.total_duration = self._clock() - self.start_time
        self.step_start_times.clear()
        self.active_workers.clear()
        self.barrier_start_times.clear()

    def get_step_stats(self, step_name: str) -> dict[str, float]:
        """Get statistics for a specific step.

        Returns:
            dict with keys: count, min, max, avg, total
        """
        durations = self.step_durations.get(step_name, [])
        if not durations:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "total": 0.0,
            }

        return {
            "count": len(durations),
            "min": min(durations),
            "max": max(durations),
            "avg": sum(durations) / len(durations),
            "total": sum(durations),
        }

    def get_bottleneck(self) -> str | None:
        """Identify the bottleneck step (longest total time).

        Returns:
            Step name of the bottleneck, or None if no steps
        """
        if not self.step_durations:
            return None

        bottleneck = None
        max_total = 0.0

        for step_name in self.step_durations:
            stats = self.get_step_stats(step_name)
            if stats["total"] > max_total:
                max_total = stats["total"]
                bottleneck = step_name

        return bottleneck

    def get_bottleneck_percentage(self) -> float:
        """Get percentage of total time spent in bottleneck.

        Returns:
            Percentage (0-100)
        """
        if not self.total_duration or not self.step_durations:
            return 0.0

        bottleneck = self.get_bottleneck()
        if not bottleneck:
            return 0.0

        stats = self.get_step_stats(bottleneck)
        return (stats["total"] / self.total_duration) * 100

    def summary(self, detailed: bool = False) -> str:
        """Generate a human-readable summary of metrics.

        Args:
            detailed: Include detailed per-step breakdown

        Returns:
            Formatted summary string
        """
        lines = []

        # Header
        if self.total_duration > 0:
            lines.append(f"Pipeline Completed in {self.total_duration:.2f}s")
        else:
            lines.append("Pipeline Metrics")

        lines.append("=" * 60)
        lines.append("")

        # Overall stats
        steps_executed = len(self.step_durations)
        total_events = sum(self.event_counts.values())

        lines.append(f"Steps Executed: {steps_executed}")
        lines.append(f"Max Parallel Workers: {self.max_parallel_workers}")
        lines.append(f"Total Events: {total_events:,}")

        if self.error_count > 0:
            lines.append(f"Errors: {self.error_count}")

        if self.token_count > 0:
            lines.append(f"Tokens: {self.token_count:,}")

        lines.append("")

        # Step timings
        if self.step_durations:
            lines.append("Step Timings:")

            # Sort by total time (descending)
            sorted_steps = sorted(
                self.step_durations.keys(),
                key=lambda s: self.get_step_stats(s)["total"],
                reverse=True,
            )

            for step_name in sorted_steps:
                stats = self.get_step_stats(step_name)

                if stats["count"] == 1:
                    # Single execution
                    lines.append(f"  {step_name:<30} {stats['total']:>8.3f}s")
                else:
                    # Multiple executions (parallel)
                    lines.append(
                        f"  {step_name:<30} {stats['avg']:>8.3f}s avg "
                        f"({stats['count']} workers, range: {stats['min']:.3f}-{stats['max']:.3f}s)"
                    )

            lines.append("")

        # Bottleneck
        bottleneck = self.get_bottleneck()
        if bottleneck and self.total_duration > 0:
            percentage = self.get_bottleneck_percentage()
            lines.append(f"Bottleneck: {bottleneck} ({percentage:.1f}% of total time)")
            lines.append("")

        # Barrier wait times
        if self.barrier_wait_times:
            lines.append("Barrier Wait Times:")
            for barrier, wait_time in sorted(
                self.barrier_wait_times.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {barrier:<30} {wait_time:>8.3f}s")
            lines.append("")

        # Detailed event breakdown
        if detailed and self.event_counts:
            lines.append("Event Breakdown:")
            for event_type, count in sorted(
                self.event_counts.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {event_type:<20} {count:>8,}")
            lines.append("")

        # Error breakdown
        if detailed and self.error_counts_by_step:
            lines.append("Errors by Step:")
            for step, count in sorted(
                self.error_counts_by_step.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {step:<30} {count:>8}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as a dictionary.

        Returns:
            dict containing all metrics
        """
        return {
            "total_duration": self.total_duration,
            "steps_executed": len(self.step_durations),
            "max_parallel_workers": self.max_parallel_workers,
            "total_events": sum(self.event_counts.values()),
            "error_count": self.error_count,
            "token_count": self.token_count,
            "bottleneck": self.get_bottleneck(),
            "bottleneck_percentage": self.get_bottleneck_percentage(),
            "step_stats": {
                name: self.get_step_stats(name) for name in self.step_durations
            },
            "barrier_wait_times": dict(self.barrier_wait_times),
            "event_counts": dict(self.event_counts),
            "error_counts_by_step": dict(self.error_counts_by_step),
        }
