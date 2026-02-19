"""Stats command for CLI."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from justpipe.cli.formatting import format_duration
from justpipe.cli.registry import PipelineRegistry
from justpipe.storage.interface import MAX_QUERY_LIMIT
from justpipe.types import PipelineTerminalStatus


def stats_command(
    registry: PipelineRegistry,
    pipeline: str | None = None,
    days: int = 7,
) -> None:
    """Show pipeline statistics."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    all_runs = registry.list_all_runs(pipeline_name=pipeline, limit=MAX_QUERY_LIMIT)

    if not all_runs:
        print("No runs found")
        return

    # Filter by date (start_time is already datetime)
    recent_runs = [a for a in all_runs if a.run.start_time >= cutoff]

    if not recent_runs:
        print(f"No runs found in the last {days} day(s)")
        return

    total_runs = len(recent_runs)
    status_counts: Counter[str] = Counter(a.run.status.value for a in recent_runs)
    pipeline_counts: Counter[str] = Counter(a.pipeline_name for a in recent_runs)

    # Duration statistics
    durations: list[float] = [
        a.run.duration.total_seconds()
        for a in recent_runs
        if a.run.duration is not None
    ]

    success_count = status_counts.get(PipelineTerminalStatus.SUCCESS.value, 0)
    failed_count = status_counts.get(PipelineTerminalStatus.FAILED.value, 0)
    success_rate = (success_count / total_runs * 100) if total_runs > 0 else 0

    # Print header
    print()
    print("=" * 60)
    if pipeline:
        print(f"Pipeline Statistics: {pipeline}")
    else:
        print("Overall Pipeline Statistics")
    print(f"Last {days} day(s)")
    print("=" * 60)
    print()

    print(f"Total Runs:        {total_runs:,}")
    print()

    # Status breakdown
    print("Status Breakdown:")
    status_indicators = {
        PipelineTerminalStatus.SUCCESS.value: "✓",
        PipelineTerminalStatus.FAILED.value: "✗",
        PipelineTerminalStatus.TIMEOUT.value: "⏱",
        PipelineTerminalStatus.CANCELLED.value: "◌",
        PipelineTerminalStatus.CLIENT_CLOSED.value: "◦",
    }
    for status_val in [s.value for s in PipelineTerminalStatus]:
        count = status_counts.get(status_val, 0)
        if count == 0:
            continue
        percentage = (count / total_runs * 100) if total_runs > 0 else 0
        indicator = status_indicators.get(status_val, "◦")
        print(
            f"  {indicator} {status_val.capitalize():<14} {count:>6,} ({percentage:>5.1f}%)"
        )

    print()

    # Success rate
    if success_count + failed_count > 0:
        print(
            f"Success Rate:      {success_rate:.1f}% ({success_count}/{success_count + failed_count})"
        )
        print()

    # Duration statistics
    avg_duration: float | None = None
    max_duration: float | None = None

    if durations:
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        total_duration = sum(durations)

        print("Duration Statistics:")
        print(f"  Average:         {format_duration(avg_duration)}")
        print(f"  Minimum:         {format_duration(min_duration)}")
        print(f"  Maximum:         {format_duration(max_duration)}")
        print(f"  Total:           {format_duration(total_duration)}")
        print()

    # Pipeline breakdown (if not filtered)
    if not pipeline and len(pipeline_counts) > 1:
        print("Top Pipelines:")
        for pipe_name, count in pipeline_counts.most_common(5):
            percentage = (count / total_runs * 100) if total_runs > 0 else 0
            print(f"  {pipe_name:<30} {count:>6,} ({percentage:>5.1f}%)")
        print()

    # Daily activity
    daily_counts: dict[date, int] = defaultdict(int)
    for a in recent_runs:
        day = a.run.start_time.date()
        daily_counts[day] += 1

    print(f"Daily Activity (last {days} days):")
    today = datetime.now(tz=timezone.utc).date()
    for i in range(days):
        day = today - timedelta(days=i)
        count = daily_counts.get(day, 0)
        bar = "█" * (count // 2) if count > 0 else ""
        day_str = (
            "Today" if i == 0 else ("Yesterday" if i == 1 else day.strftime("%Y-%m-%d"))
        )
        print(f"  {day_str:<12} {count:>4} {bar}")

    print()

    # Error runs
    error_runs = [
        a for a in recent_runs if a.run.status == PipelineTerminalStatus.FAILED
    ]
    if error_runs:
        print(f"Recent Errors:     {len(error_runs)} error(s)")

        error_runs.sort(key=lambda a: a.run.start_time, reverse=True)
        print()
        print("Most Recent Errors:")
        for a in error_runs[:3]:
            time_ago = datetime.now(tz=timezone.utc) - a.run.start_time
            if time_ago.days > 0:
                time_str = f"{time_ago.days}d ago"
            elif time_ago.seconds > 3600:
                time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = f"{time_ago.seconds // 60}m ago"

            error_msg = a.run.error_message or "Unknown error"
            if len(error_msg) > 50:
                error_msg = error_msg[:47] + "..."

            print(
                f"  {a.run.run_id[:12]}  {a.pipeline_name:<20}  {time_str:<8}  {error_msg}"
            )

        print()

    # Recommendations
    print("=" * 60)
    print()

    if failed_count > success_count:
        print("Warning: High error rate detected!")
        print(f"   {failed_count} errors vs {success_count} successes")
        print()

    if (
        durations
        and max_duration is not None
        and avg_duration is not None
        and max_duration > avg_duration * 3
    ):
        print("Warning: Performance outlier detected!")
        print(
            f"   Slowest run: {format_duration(max_duration)} vs avg: {format_duration(avg_duration)}"
        )
        print()

    print("Use 'justpipe list' to see recent runs")
    print("Use 'justpipe compare' to analyze performance differences")
    print()
