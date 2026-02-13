"""Show command for CLI."""

from __future__ import annotations

import json
from collections import Counter

from justpipe.cli.formatting import format_duration, format_timestamp, resolve_or_exit
from justpipe.cli.registry import PipelineRegistry
from justpipe.types import EventType


def show_command(registry: PipelineRegistry, run_id_prefix: str) -> None:
    """Show details of a specific run."""
    result = resolve_or_exit(registry, run_id_prefix)
    if result is None:
        return

    annotated, backend = result
    run = annotated.run

    events = backend.get_events(run.run_id)

    print()
    print(f"Run: {run.run_id}")
    print("=" * 60)
    print(f"Pipeline: {annotated.pipeline_name}")
    print(f"Status: {run.status.value}")
    print(f"Started: {format_timestamp(run.start_time)}")

    if run.end_time:
        print(f"Ended: {format_timestamp(run.end_time)}")

    if run.duration:
        print(f"Duration: {format_duration(run.duration.total_seconds())}")

    if run.error_message:
        print(f"\nError: {run.error_message}")

    # Event summary
    print(f"\nEvents: {len(events)} total")

    if events:
        event_counts = Counter(e.event_type for e in events)

        print("\nEvent Breakdown:")
        for event_type, count in event_counts.most_common():
            print(f"  {event_type.value:<20} {count:>6,}")

        # Show step sequence
        print("\nStep Sequence:")
        step_starts = [e for e in events if e.event_type == EventType.STEP_START]

        if step_starts:
            for i, event in enumerate(step_starts, 1):
                print(f"  {i}. {event.step_name}")
        else:
            print("  (No step events)")

    # User meta
    if run.user_meta:
        try:
            meta = json.loads(run.user_meta)
            print("\nUser Meta:")
            for key, value in meta.items():
                print(f"  {key}: {value}")
        except (json.JSONDecodeError, AttributeError):
            print(f"\nUser Meta: {run.user_meta}")

    print()
