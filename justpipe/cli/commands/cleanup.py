"""Cleanup command for CLI."""

from datetime import datetime, timedelta
from justpipe.storage.interface import StorageBackend


async def cleanup_command(
    storage: StorageBackend,
    older_than_days: int | None = None,
    status: str | None = None,
    keep: int = 10,
    dry_run: bool = False,
) -> None:
    """Clean up old pipeline runs.

    Args:
        storage: Storage backend
        older_than_days: Delete runs older than N days
        status: Only delete runs with this status
        keep: Keep at least N most recent runs (default: 10)
        dry_run: Show what would be deleted without actually deleting
    """

    # Get all runs
    all_runs = await storage.list_runs(limit=10000)

    if not all_runs:
        print("No runs found")
        return

    # Filter runs to delete
    runs_to_delete = []

    # Calculate cutoff timestamp if older_than_days specified
    cutoff_timestamp = None
    if older_than_days:
        cutoff_time = datetime.now() - timedelta(days=older_than_days)
        cutoff_timestamp = cutoff_time.timestamp()

    # Sort by start time (newest first)
    all_runs.sort(key=lambda r: r.start_time, reverse=True)

    # Always keep the N most recent runs
    # runs_to_keep = all_runs[:keep]  # Not used, but kept for clarity
    candidate_runs = all_runs[keep:]

    for run in candidate_runs:
        # Check status filter
        if status and run.status != status:
            continue

        # Check age filter
        if cutoff_timestamp and run.start_time >= cutoff_timestamp:
            continue

        runs_to_delete.append(run)

    if not runs_to_delete:
        print("No runs to clean up")
        return

    # Show what will be deleted
    print(f"Found {len(runs_to_delete)} run(s) to clean up")
    print()

    if dry_run:
        print("DRY RUN - No files will be deleted")
        print()

    # Group by status for summary
    from collections import Counter

    status_counts = Counter(r.status for r in runs_to_delete)

    print("Runs to delete by status:")
    for s, count in status_counts.most_common():
        print(f"  {s:<10} {count:>5} run(s)")
    print()

    # Show date range
    if runs_to_delete:
        oldest = min(r.start_time for r in runs_to_delete)
        newest = max(r.start_time for r in runs_to_delete)

        print(
            f"Date range: {datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')} to "
            f"{datetime.fromtimestamp(newest).strftime('%Y-%m-%d')}"
        )
        print()

    # Show sample runs
    if len(runs_to_delete) <= 10:
        print("Runs to delete:")
        for run in runs_to_delete:
            print(
                f"  {run.id[:12]}  {run.pipeline_name:<20}  {run.status:<10}  "
                f"{datetime.fromtimestamp(run.start_time).strftime('%Y-%m-%d %H:%M')}"
            )
    else:
        print(f"Showing first 10 of {len(runs_to_delete)} runs:")
        for run in runs_to_delete[:10]:
            print(
                f"  {run.id[:12]}  {run.pipeline_name:<20}  {run.status:<10}  "
                f"{datetime.fromtimestamp(run.start_time).strftime('%Y-%m-%d %H:%M')}"
            )
        print(f"  ... and {len(runs_to_delete) - 10} more")

    print()

    if dry_run:
        print("DRY RUN - Use without --dry-run to actually delete these runs")
        return

    # Confirm deletion
    if len(runs_to_delete) > 0:
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

    for run in runs_to_delete:
        try:
            success = await storage.delete_run(run.id)
            if success:
                deleted_count += 1
            else:
                failed_count += 1
                print(f"  Failed to delete: {run.id[:12]}")
        except Exception as e:
            failed_count += 1
            print(f"  Error deleting {run.id[:12]}: {e}")

    print()
    print(f"✓ Deleted {deleted_count} run(s)")

    if failed_count > 0:
        print(f"✗ Failed to delete {failed_count} run(s)")

    # Show remaining runs
    remaining_runs = await storage.list_runs(limit=10000)
    print()
    print(f"Remaining: {len(remaining_runs)} run(s)")
