"""Export command for CLI."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from justpipe.cli.formatting import resolve_or_exit
from justpipe.cli.registry import PipelineRegistry


def _json_serializer(obj: Any) -> str | float:
    """JSON serializer for datetime/timedelta objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    raise TypeError(f"type {type(obj)} not serializable")


def _export_events(events: list[Any]) -> list[dict[str, Any]]:
    """Export events with per-event JSON parsing guard."""
    exported: list[dict[str, Any]] = []
    for event in events:
        try:
            event_data = json.loads(event.data)
        except json.JSONDecodeError:
            event_data = None
        exported.append(
            {
                "seq": event.seq,
                "event_type": event.event_type.value,
                "step_name": event.step_name,
                "timestamp": event.timestamp.isoformat(),
                "data": event_data,
            }
        )
    return exported


def export_command(
    registry: PipelineRegistry,
    run_id_prefix: str,
    output_file: str | None = None,
    format: str = "json",
) -> None:
    """Export run data to file."""
    if format != "json":
        print(f"Unsupported format: {format}")
        print("Supported formats: json")
        return

    result = resolve_or_exit(registry, run_id_prefix)
    if result is None:
        return

    annotated, backend = result
    run = annotated.run

    events = backend.get_events(run.run_id)

    # Parse user_meta JSON
    user_meta: Any = None
    if run.user_meta:
        try:
            user_meta = json.loads(run.user_meta)
        except json.JSONDecodeError:
            user_meta = run.user_meta

    export_data: dict[str, Any] = {
        "run": {
            "id": run.run_id,
            "pipeline_name": annotated.pipeline_name,
            "pipeline_hash": annotated.pipeline_hash,
            "status": run.status.value,
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "duration_seconds": (
                run.duration.total_seconds() if run.duration else None
            ),
            "error_message": run.error_message,
            "error_step": run.error_step,
            "user_meta": user_meta,
        },
        "events": _export_events(events),
        "event_count": len(events),
        "exported_at": datetime.now().isoformat(),
    }

    if output_file is None:
        output_file = f"run_{run.run_id[:8]}.json"

    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2, default=_json_serializer)

    print(f"Run exported to: {output_file}")
    print(f"  Run ID: {run.run_id}")
    print(f"  Pipeline: {annotated.pipeline_name}")
    print(f"  Events: {len(events)}")
    print(f"  Status: {run.status.value}")
