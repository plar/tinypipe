"""Run comparison utilities for analyzing differences between pipeline executions."""

from dataclasses import dataclass
from justpipe.storage.interface import StorageBackend, StoredRun


@dataclass
class RunComparison:
    """Comparison result between two pipeline runs."""

    run1_id: str
    run2_id: str
    run1: StoredRun
    run2: StoredRun

    duration_diff: float  # run2 - run1 (positive = run2 slower)
    status_same: bool
    pipeline_same: bool

    step_timing_diff: dict[str, float]  # step -> time difference
    new_steps: list[str]  # Steps in run2 not in run1
    removed_steps: list[str]  # Steps in run1 not in run2

    event_count_diff: int  # run2 - run1


def _calculate_duration(run: StoredRun) -> float:
    """Calculate run duration in seconds."""
    if run.end_time and run.start_time:
        # Both are floats (UNIX timestamps)
        return run.end_time - run.start_time
    return 0.0


async def compare_runs(
    storage: StorageBackend,
    run1_id: str,
    run2_id: str,
) -> RunComparison:
    """Compare two pipeline runs.

    Args:
        storage: Storage backend
        run1_id: First run ID (baseline)
        run2_id: Second run ID (comparison)

    Returns:
        RunComparison object with detailed differences

    Raises:
        ValueError: If either run is not found
    """
    # Load runs
    run1 = await storage.get_run(run1_id)
    run2 = await storage.get_run(run2_id)

    if run1 is None:
        raise ValueError(f"Run not found: {run1_id}")
    if run2 is None:
        raise ValueError(f"Run not found: {run2_id}")

    # Load events
    events1 = await storage.get_events(run1_id)
    events2 = await storage.get_events(run2_id)

    # Calculate durations
    duration1 = _calculate_duration(run1)
    duration2 = _calculate_duration(run2)
    duration_diff = duration2 - duration1

    # Check status and pipeline
    status_same = run1.status == run2.status
    pipeline_same = run1.pipeline_name == run2.pipeline_name

    # Build step timing maps
    step_times1: dict[str, float] = {}
    step_times2: dict[str, float] = {}

    # Track step_start events to calculate durations
    for event in events1:
        if event.event_type == "step_start":
            step_name = event.step_name or "unknown"
            step_times1[step_name] = 0.0

    for event in events2:
        if event.event_type == "step_start":
            step_name = event.step_name or "unknown"
            step_times2[step_name] = 0.0

    # Calculate step durations from step_start/step_end pairs
    # Note: event.timestamp is a float (UNIX timestamp)
    step_starts1: dict[str, float] = {}
    for event in events1:
        step_name = event.step_name or "unknown"
        if event.event_type == "step_start":
            step_starts1[step_name] = event.timestamp
        elif event.event_type == "step_end" and step_name in step_starts1:
            # Both timestamps are floats, so delta is already in seconds
            duration = event.timestamp - step_starts1[step_name]
            step_times1[step_name] = duration

    step_starts2: dict[str, float] = {}
    for event in events2:
        step_name = event.step_name or "unknown"
        if event.event_type == "step_start":
            step_starts2[step_name] = event.timestamp
        elif event.event_type == "step_end" and step_name in step_starts2:
            # Both timestamps are floats, so delta is already in seconds
            duration = event.timestamp - step_starts2[step_name]
            step_times2[step_name] = duration

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
        run1_id=run1_id,
        run2_id=run2_id,
        run1=run1,
        run2=run2,
        duration_diff=duration_diff,
        status_same=status_same,
        pipeline_same=pipeline_same,
        step_timing_diff=step_timing_diff,
        new_steps=new_steps,
        removed_steps=removed_steps,
        event_count_diff=event_count_diff,
    )


def format_comparison(comparison: RunComparison) -> str:
    """Format comparison as human-readable text.

    Args:
        comparison: RunComparison object

    Returns:
        Formatted string report
    """
    lines = []
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
            f"Pipeline: {comparison.run1.pipeline_name} → {comparison.run2.pipeline_name}"
        )
    else:
        lines.append(f"Pipeline: {comparison.run1.pipeline_name}")

    if not comparison.status_same:
        lines.append(f"Status:   {comparison.run1.status} → {comparison.run2.status}")
    else:
        lines.append(f"Status:   {comparison.run1.status}")

    lines.append("")

    # Duration
    duration1 = _calculate_duration(comparison.run1)
    duration2 = _calculate_duration(comparison.run2)

    if comparison.duration_diff > 0:
        duration_str = (
            f"Duration: {duration1:.3f}s → {duration2:.3f}s "
            f"(+{comparison.duration_diff:.3f}s slower)"
        )
    elif comparison.duration_diff < 0:
        duration_str = (
            f"Duration: {duration1:.3f}s → {duration2:.3f}s "
            f"({comparison.duration_diff:.3f}s faster)"
        )
    else:
        duration_str = f"Duration: {duration1:.3f}s → {duration2:.3f}s (same)"

    lines.append(duration_str)

    lines.append("")

    # Step timing differences
    if comparison.step_timing_diff:
        lines.append("Step Timing Differences:")
        lines.append("")

        # Sort by absolute difference (largest first)
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
            elif abs(diff) > 0.001:  # Only show meaningful differences
                sign = "+" if diff > 0 else ""
                lines.append(f"  ~ {step:<30} {sign}{diff:.3f}s")

        lines.append("")

    # Event count
    lines.append(f"Event Count Difference: {comparison.event_count_diff:+d} events")

    return "\n".join(lines)
