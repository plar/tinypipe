"""Stats command for CLI."""

from datetime import datetime, timedelta, date
from collections import Counter, defaultdict
from justpipe.storage.interface import StorageBackend


def format_duration(seconds: float | None) -> str:
    """Format duration for display."""
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


async def stats_command(
    storage: StorageBackend,
    pipeline: str | None = None,
    days: int = 7,
) -> None:
    """Show pipeline statistics.

    Args:
        storage: Storage backend
        pipeline: Filter by pipeline name
        days: Number of days to include (default: 7)
    """
    # Calculate cutoff time
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_timestamp = cutoff.timestamp()

    # Get all runs
    all_runs = await storage.list_runs(pipeline_name=pipeline, limit=10000)

    if not all_runs:
        print("No runs found")
        return

    # Filter by date
    recent_runs = [r for r in all_runs if r.start_time >= cutoff_timestamp]

    if not recent_runs:
        print(f"No runs found in the last {days} day(s)")
        return

    # Calculate statistics
    total_runs = len(recent_runs)
    status_counts = Counter(r.status for r in recent_runs)
    pipeline_counts = Counter(r.pipeline_name for r in recent_runs)

    # Duration statistics
    completed_runs = [r for r in recent_runs if r.duration is not None]
    durations: list[float] = [
        r.duration for r in completed_runs if r.duration is not None
    ]

    # Success rate
    success_count = status_counts.get("success", 0)
    error_count = status_counts.get("error", 0)
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

    # Total runs
    print(f"Total Runs:        {total_runs:,}")
    print()

    # Status breakdown
    print("Status Breakdown:")
    for status in ["success", "error", "running", "suspended"]:
        count = status_counts.get(status, 0)
        percentage = (count / total_runs * 100) if total_runs > 0 else 0

        # Color indicator
        if status == "success":
            indicator = "✓"
        elif status == "error":
            indicator = "✗"
        elif status == "running":
            indicator = "⋯"
        else:
            indicator = "◦"

        print(
            f"  {indicator} {status.capitalize():<12} {count:>6,} ({percentage:>5.1f}%)"
        )

    print()

    # Success rate
    if success_count + error_count > 0:
        print(
            f"Success Rate:      {success_rate:.1f}% ({success_count}/{success_count + error_count})"
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
    for run in recent_runs:
        day = datetime.fromtimestamp(run.start_time).date()
        daily_counts[day] += 1

    # Show last 7 days
    print("Daily Activity (last 7 days):")
    today = datetime.now().date()
    for i in range(min(days, 7)):
        day = today - timedelta(days=i)
        count = daily_counts.get(day, 0)
        bar = "█" * (count // 2) if count > 0 else ""
        day_str = (
            "Today" if i == 0 else ("Yesterday" if i == 1 else day.strftime("%Y-%m-%d"))
        )
        print(f"  {day_str:<12} {count:>4} {bar}")

    print()

    # Error rate trend (if enough data)
    error_runs = [r for r in recent_runs if r.status == "error"]
    if error_runs:
        print(f"Recent Errors:     {len(error_runs)} error(s)")

        # Show most recent errors
        error_runs.sort(key=lambda r: r.start_time, reverse=True)
        print()
        print("Most Recent Errors:")
        for run in error_runs[:3]:
            time_ago = datetime.now() - datetime.fromtimestamp(run.start_time)
            if time_ago.days > 0:
                time_str = f"{time_ago.days}d ago"
            elif time_ago.seconds > 3600:
                time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = f"{time_ago.seconds // 60}m ago"

            error_msg = run.error_message or "Unknown error"
            if len(error_msg) > 50:
                error_msg = error_msg[:47] + "..."

            print(
                f"  {run.id[:12]}  {run.pipeline_name:<20}  {time_str:<8}  {error_msg}"
            )

        print()

    # Recommendations
    print("=" * 60)
    print()

    if error_count > success_count:
        print("⚠️  High error rate detected!")
        print(f"   {error_count} errors vs {success_count} successes")
        print()

    if (
        durations
        and max_duration is not None
        and avg_duration is not None
        and max_duration > avg_duration * 3
    ):
        print("⚠️  Performance outlier detected!")
        print(
            f"   Slowest run: {format_duration(max_duration)} vs avg: {format_duration(avg_duration)}"
        )
        print()

    print("Use 'justpipe list' to see recent runs")
    print("Use 'justpipe compare' to analyze performance differences")
    print()
