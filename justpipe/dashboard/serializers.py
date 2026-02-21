"""Data → JSON-serializable dict conversion for dashboard API."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from justpipe.cli.formatting import parse_run_meta
from justpipe.cli.registry import PipelineInfo
from justpipe.observability._step_pairing import pair_step_events
from justpipe.observability.compare import RunComparison
from justpipe.storage.interface import RunRecord, StoredEvent
from justpipe.types import PipelineTerminalStatus


def serialize_run(
    run: RunRecord, pipeline_name: str, pipeline_hash: str
) -> dict[str, Any]:
    """RunRecord → JSON-serializable dict."""
    run_meta = parse_run_meta(run.run_meta)

    return {
        "run_id": run.run_id,
        "pipeline_name": pipeline_name,
        "pipeline_hash": pipeline_hash,
        "status": run.status.value,
        "start_time": run.start_time.isoformat(),
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "duration_seconds": run.duration.total_seconds() if run.duration else None,
        "error_message": run.error_message,
        "error_step": run.error_step,
        "run_meta": run_meta,
    }


def serialize_event(event: StoredEvent) -> dict[str, Any]:
    """StoredEvent → JSON-serializable dict."""
    try:
        event_data = json.loads(event.data)
    except json.JSONDecodeError:
        event_data = None

    return {
        "seq": event.seq,
        "event_type": event.event_type.value,
        "step_name": event.step_name,
        "timestamp": event.timestamp.isoformat(),
        "data": event_data,
    }


def serialize_pipeline(info: PipelineInfo, runs: list[RunRecord]) -> dict[str, Any]:
    """PipelineInfo + runs → JSON-serializable pipeline summary."""
    total = len(runs)
    success_count = sum(1 for r in runs if r.status == PipelineTerminalStatus.SUCCESS)
    success_rate = (success_count / total * 100) if total > 0 else 0.0

    durations = [r.duration.total_seconds() for r in runs if r.duration is not None]
    avg_duration = sum(durations) / len(durations) if durations else None

    last_run_time = runs[0].start_time.isoformat() if runs else None

    return {
        "name": info.name,
        "hash": info.hash,
        "total_runs": total,
        "success_count": success_count,
        "success_rate": round(success_rate, 1),
        "avg_duration_seconds": round(avg_duration, 3) if avg_duration else None,
        "last_run_time": last_run_time,
    }


def serialize_comparison(comp: RunComparison) -> dict[str, Any]:
    """RunComparison → JSON-serializable dict."""
    return {
        "run1_id": comp.run1_id,
        "run2_id": comp.run2_id,
        "pipeline1_name": comp.pipeline1_name,
        "pipeline2_name": comp.pipeline2_name,
        "duration_diff": comp.duration_diff,
        "status_same": comp.status_same,
        "pipeline_same": comp.pipeline_same,
        "step_timing_diff": comp.step_timing_diff,
        "new_steps": comp.new_steps,
        "removed_steps": comp.removed_steps,
        "event_count_diff": comp.event_count_diff,
    }


def serialize_stats(runs: list[RunRecord], days: int = 7) -> dict[str, Any]:
    """Compute aggregate stats from runs → JSON-serializable dict."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    recent = [r for r in runs if r.start_time >= cutoff]

    total = len(recent)
    status_counts: Counter[str] = Counter(r.status.value for r in recent)
    success_count = status_counts.get(PipelineTerminalStatus.SUCCESS.value, 0)
    failed_count = status_counts.get(PipelineTerminalStatus.FAILED.value, 0)
    success_rate = (success_count / total * 100) if total > 0 else 0.0

    durations = [r.duration.total_seconds() for r in recent if r.duration is not None]

    duration_stats: dict[str, Any] | None = None
    if durations:
        duration_stats = {
            "avg": round(sum(durations) / len(durations), 3),
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
            "total": round(sum(durations), 3),
        }

    # Daily activity
    daily: Counter[str] = Counter(r.start_time.strftime("%Y-%m-%d") for r in recent)

    # Recent errors
    errors = [
        {
            "run_id": r.run_id,
            "start_time": r.start_time.isoformat(),
            "error_message": r.error_message,
            "error_step": r.error_step,
        }
        for r in sorted(
            (r for r in recent if r.status == PipelineTerminalStatus.FAILED),
            key=lambda r: r.start_time,
            reverse=True,
        )
    ][:5]

    return {
        "total_runs": total,
        "days": days,
        "status_counts": dict(status_counts),
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round(success_rate, 1),
        "duration_stats": duration_stats,
        "daily_activity": daily,
        "recent_errors": errors,
    }


def serialize_timeline(events: list[StoredEvent]) -> list[dict[str, Any]]:
    """Extract step timing data from events for timeline visualization."""
    raw = [
        (event.step_name or "unknown", event.event_type, event.timestamp)
        for event in events
    ]
    spans = pair_step_events(raw)
    return [
        {
            "step_name": s.step_name,
            "start_time": s.start.isoformat(),
            "end_time": s.end.isoformat(),
            "duration_seconds": round(s.duration, 4),
            "status": s.status.value,
        }
        for s in spans
    ]
