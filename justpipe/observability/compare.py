"""Run comparison utilities for analyzing differences between pipeline executions."""

from __future__ import annotations

from dataclasses import dataclass

from justpipe.storage.interface import RunRecord, StoredEvent
from justpipe.types import EventType


@dataclass
class RunComparison:
    """Comparison result between two pipeline runs."""

    run1_id: str
    run2_id: str
    pipeline1_name: str
    pipeline2_name: str

    duration_diff: float  # run2 - run1 (positive = run2 slower)
    status_same: bool
    pipeline_same: bool

    step_timing_diff: dict[str, float]  # step -> time difference
    new_steps: list[str]  # Steps in run2 not in run1
    removed_steps: list[str]  # Steps in run1 not in run2

    event_count_diff: int  # run2 - run1


def _calculate_duration(run: RunRecord) -> float:
    """Calculate run duration in seconds."""
    if run.duration is not None:
        return run.duration.total_seconds()
    return 0.0


def _build_step_times(events: list[StoredEvent]) -> dict[str, float]:
    """Build a step-name → duration mapping from stored events."""
    step_starts: dict[str, float] = {}
    step_times: dict[str, float] = {}

    for event in events:
        step_name = event.step_name or "unknown"
        if event.event_type == EventType.STEP_START:
            step_starts[step_name] = event.timestamp.timestamp()
        elif event.event_type == EventType.STEP_END and step_name in step_starts:
            duration = event.timestamp.timestamp() - step_starts.pop(step_name)
            step_times[step_name] = duration

    return step_times


def compare_runs(
    run1: RunRecord,
    events1: list[StoredEvent],
    run2: RunRecord,
    events2: list[StoredEvent],
    pipeline1_name: str = "",
    pipeline2_name: str = "",
) -> RunComparison:
    """Compare two pipeline runs (pure sync function).

    Data loading is the caller's responsibility.
    """
    # Calculate durations
    duration1 = _calculate_duration(run1)
    duration2 = _calculate_duration(run2)
    duration_diff = duration2 - duration1

    # Check status and pipeline
    status_same = run1.status == run2.status
    pipeline_same = pipeline1_name == pipeline2_name

    # Build step timing maps
    step_times1 = _build_step_times(events1)
    step_times2 = _build_step_times(events2)

    # Calculate differences
    all_steps = set(step_times1.keys()) | set(step_times2.keys())
    step_timing_diff = {}
    for step in all_steps:
        time1 = step_times1.get(step, 0.0)
        time2 = step_times2.get(step, 0.0)
        step_timing_diff[step] = time2 - time1

    new_steps = [s for s in step_times2 if s not in step_times1]
    removed_steps = [s for s in step_times1 if s not in step_times2]

    event_count_diff = len(events2) - len(events1)

    return RunComparison(
        run1_id=run1.run_id,
        run2_id=run2.run_id,
        pipeline1_name=pipeline1_name,
        pipeline2_name=pipeline2_name,
        duration_diff=duration_diff,
        status_same=status_same,
        pipeline_same=pipeline_same,
        step_timing_diff=step_timing_diff,
        new_steps=new_steps,
        removed_steps=removed_steps,
        event_count_diff=event_count_diff,
    )


def format_comparison(comparison: RunComparison) -> str:
    """Format comparison as human-readable text."""
    lines: list[str] = []
    lines.append("Run Comparison")
    lines.append("=" * 60)
    lines.append("")

    # Run IDs
    lines.append(f"Run 1 (baseline): {comparison.run1_id[:16]}...")
    lines.append(f"Run 2 (compare):  {comparison.run2_id[:16]}...")
    lines.append("")

    # Basic info
    if not comparison.pipeline_same:
        lines.append(
            f"Pipeline: {comparison.pipeline1_name} → {comparison.pipeline2_name}"
        )
    else:
        lines.append(f"Pipeline: {comparison.pipeline1_name}")

    if not comparison.status_same:
        lines.append("Status:   changed")
    else:
        lines.append("Status:   same")

    lines.append("")

    # Duration
    if comparison.duration_diff > 0:
        duration_str = f"Duration change: +{comparison.duration_diff:.3f}s (slower)"
    elif comparison.duration_diff < 0:
        duration_str = f"Duration change: {comparison.duration_diff:.3f}s (faster)"
    else:
        duration_str = "Duration change: none"

    lines.append(duration_str)
    lines.append("")

    # Step timing differences
    if comparison.step_timing_diff:
        lines.append("Step Timing Differences:")
        lines.append("")

        sorted_steps = sorted(
            comparison.step_timing_diff.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )

        for step, diff in sorted_steps:
            if step in comparison.new_steps:
                lines.append(f"  + {step:<30} (new step)")
            elif step in comparison.removed_steps:
                lines.append(f"  - {step:<30} (removed)")
            elif abs(diff) > 0.001:
                sign = "+" if diff > 0 else ""
                lines.append(f"  ~ {step:<30} {sign}{diff:.3f}s")

        lines.append("")

    # Event count
    lines.append(f"Event Count Difference: {comparison.event_count_diff:+d} events")

    return "\n".join(lines)
