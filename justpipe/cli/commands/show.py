"""Show command for CLI."""

from collections import Counter

from justpipe.storage.interface import StorageBackend


def format_duration(seconds: float) -> str:
    """Format duration for display."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def format_timestamp(timestamp: float) -> str:
    """Format timestamp for display."""
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


async def show_command(storage: StorageBackend, run_id_prefix: str) -> None:
    """Show details of a specific run.

    Args:
        storage: Storage backend
        run_id_prefix: Run identifier or prefix (min 4 chars)
    """
    # Resolve prefix to full ID
    try:
        run = await storage.get_run_by_prefix(run_id_prefix)
    except ValueError as e:
        print(f"Error: {e}")
        return

    if run is None:
        print(f"Run not found: {run_id_prefix}")
        return

    # Get events
    events = await storage.get_events(run.id)

    # Display run info
    print()
    print(f"Run: {run.id}")
    print("=" * 60)
    print(f"Pipeline: {run.pipeline_name}")
    print(f"Status: {run.status}")
    print(f"Started: {format_timestamp(run.start_time)}")

    if run.end_time:
        print(f"Ended: {format_timestamp(run.end_time)}")

    if run.duration:
        print(f"Duration: {format_duration(run.duration)}")

    if run.error_message:
        print(f"\nError: {run.error_message}")

    # Event summary
    print(f"\nEvents: {len(events)} total")

    if events:
        # Count by type
        event_counts = Counter(e.event_type for e in events)

        print("\nEvent Breakdown:")
        for event_type, count in event_counts.most_common():
            print(f"  {event_type:<20} {count:>6,}")

        # Show step sequence
        print("\nStep Sequence:")
        step_starts = [e for e in events if e.event_type == "step_start"]

        if step_starts:
            for i, event in enumerate(step_starts, 1):
                print(f"  {i}. {event.step_name}")
        else:
            print("  (No step events)")

    # Metadata
    if run.metadata:
        print("\nMetadata:")
        for key, value in run.metadata.items():
            print(f"  {key}: {value}")

    print()
