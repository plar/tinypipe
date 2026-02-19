"""Cleanup command for CLI."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from justpipe.cli.formatting import format_timestamp
from justpipe.cli.registry import AnnotatedRun, PipelineRegistry
from justpipe.storage.interface import MAX_QUERY_LIMIT
from justpipe.types import PipelineTerminalStatus


def _format_run_line(a: AnnotatedRun) -> str:
    """Format a single run for cleanup display."""
    return (
        f"  {a.run.run_id[:12]}  {a.pipeline_name:<20}  {a.run.status.value:<14}  "
        f"{format_timestamp(a.run.start_time)}"
    )


def cleanup_command(
    registry: PipelineRegistry,
    older_than_days: int | None = None,
    status: PipelineTerminalStatus | None = None,
    keep: int = 10,
    dry_run: bool = False,
) -> None:
    """Clean up old pipeline runs."""
    all_runs = registry.list_all_runs(limit=MAX_QUERY_LIMIT)

    if not all_runs:
        print("No runs found")
        return

    # Calculate cutoff datetime if older_than_days specified
    cutoff: datetime | None = None
    if older_than_days is not None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=older_than_days)

    # Sort by start time (newest first)
    all_runs.sort(key=lambda a: a.run.start_time, reverse=True)

    # Always keep the N most recent runs
    candidate_runs = all_runs[keep:]

    runs_to_delete = []
    for annotated in candidate_runs:
        run = annotated.run
        # Check status filter
        if status and run.status != status:
            continue
        # Check age filter
        if cutoff and run.start_time >= cutoff:
            continue
        runs_to_delete.append(annotated)

    if not runs_to_delete:
        print("No runs to clean up")
        return

    print(f"Found {len(runs_to_delete)} run(s) to clean up")
    print()

    if dry_run:
        print("DRY RUN - No files will be deleted")
        print()

    # Group by status for summary
    status_counts: Counter[str] = Counter(a.run.status.value for a in runs_to_delete)

    print("Runs to delete by status:")
    for s, count in status_counts.most_common():
        print(f"  {s:<14} {count:>5} run(s)")
    print()

    # Show date range
    oldest = min(a.run.start_time for a in runs_to_delete)
    newest = max(a.run.start_time for a in runs_to_delete)

    print(f"Date range: {format_timestamp(oldest)} to {format_timestamp(newest)}")
    print()

    # Show sample runs
    if len(runs_to_delete) <= 10:
        print("Runs to delete:")
        for a in runs_to_delete:
            print(_format_run_line(a))
    else:
        print(f"Showing first 10 of {len(runs_to_delete)} runs:")
        for a in runs_to_delete[:10]:
            print(_format_run_line(a))
        print(f"  ... and {len(runs_to_delete) - 10} more")

    print()

    if dry_run:
        print("DRY RUN - Use without --dry-run to actually delete these runs")
        return

    # Confirm deletion
    try:
        response = input(f"Delete {len(runs_to_delete)} run(s)? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled")
            return
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled")
        return

    # Delete runs
    deleted_count = 0
    failed_count = 0

    print()
    print("Deleting runs...")

    for annotated in runs_to_delete:
        try:
            backend = registry.get_backend(annotated.pipeline_hash)
            success = backend.delete_run(annotated.run.run_id)
            if success:
                deleted_count += 1
            else:
                failed_count += 1
                print(f"  Failed to delete: {annotated.run.run_id[:12]}")
        except Exception as e:
            failed_count += 1
            print(f"  Error deleting {annotated.run.run_id[:12]}: {e}")

    print()
    print(f"Deleted {deleted_count} run(s)")

    if failed_count > 0:
        print(f"Failed to delete {failed_count} run(s)")

    remaining = registry.list_all_runs(limit=MAX_QUERY_LIMIT)
    print()
    print(f"Remaining: {len(remaining)} run(s)")
