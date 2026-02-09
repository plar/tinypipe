"""Export command for CLI."""

import json
from datetime import datetime
from typing import Any
from justpipe.storage.interface import StorageBackend


def _datetime_serializer(obj: Any) -> str:
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"type {type(obj)} not serializable")


async def export_command(
    storage: StorageBackend,
    run_id_prefix: str,
    output_file: str | None = None,
    format: str = "json",
) -> None:
    """Export run data to file.

    Args:
        storage: Storage backend
        run_id_prefix: Run identifier or prefix (min 4 chars)
        output_file: Output file path (default: run_{run_id[:8]}.json)
        format: Export format (only 'json' supported currently)
    """
    if format != "json":
        print(f"Unsupported format: {format}")
        print("Supported formats: json")
        return

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

    # Build export data
    # Note: timestamps are floats (UNIX timestamps), convert to ISO format
    export_data = {
        "run": {
            "id": run.id,
            "pipeline_name": run.pipeline_name,
            "status": run.status,
            "start_time": run.start_time if run.start_time else None,
            "start_time_iso": (
                datetime.fromtimestamp(run.start_time).isoformat()
                if run.start_time
                else None
            ),
            "end_time": run.end_time if run.end_time else None,
            "end_time_iso": (
                datetime.fromtimestamp(run.end_time).isoformat()
                if run.end_time
                else None
            ),
            "metadata": run.metadata,
        },
        "events": [
            {
                "id": event.id,
                "run_id": event.run_id,
                "event_type": event.event_type,
                "step_name": event.step_name,
                "timestamp": event.timestamp,
                "timestamp_iso": datetime.fromtimestamp(event.timestamp).isoformat(),
                "payload": event.payload,
            }
            for event in events
        ],
        "event_count": len(events),
        "exported_at": datetime.now().isoformat(),
    }

    # Calculate duration if available
    # Note: timestamps are floats, so subtraction gives duration directly
    if run.start_time and run.end_time:
        duration = run.end_time - run.start_time
        run_data: Any = export_data["run"]
        run_data["duration_seconds"] = duration

    # Determine output filename
    if output_file is None:
        output_file = f"run_{run.id[:8]}.json"

    # Write to file
    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2, default=_datetime_serializer)

    print(f"Run exported to: {output_file}")
    print(f"  Run ID: {run.id}")
    print(f"  Pipeline: {run.pipeline_name}")
    print(f"  Events: {len(events)}")
    print(f"  Status: {run.status}")
