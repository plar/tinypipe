"""Dashboard API — endpoint handlers backed by PipelineRegistry."""

from __future__ import annotations

import json
from typing import Any

from justpipe.cli.registry import PipelineInfo, PipelineRegistry
from justpipe.dashboard.serializers import (
    serialize_comparison,
    serialize_event,
    serialize_pipeline,
    serialize_run,
    serialize_stats,
    serialize_timeline,
)
from justpipe.observability.compare import compare_runs
from justpipe.storage.interface import MAX_QUERY_LIMIT
from justpipe.types import EventType, PipelineTerminalStatus


class DashboardAPI:
    """Stateless handler object — one per FastAPI app."""

    def __init__(self, registry: PipelineRegistry) -> None:
        self._registry = registry

    def _find_pipeline(self, pipeline_hash: str) -> PipelineInfo | None:
        return next(
            (
                info
                for info in self._registry.list_pipelines()
                if info.hash == pipeline_hash
            ),
            None,
        )

    def list_pipelines(self) -> list[dict[str, Any]]:
        """All pipelines with summary stats."""
        result = []
        for info in self._registry.list_pipelines():
            backend = self._registry.get_backend(info.hash)
            runs = backend.list_runs(limit=MAX_QUERY_LIMIT)
            result.append(serialize_pipeline(info, runs))
        return result

    def get_pipeline(self, pipeline_hash: str) -> dict[str, Any] | None:
        """Pipeline detail including topology from pipeline.json."""
        info = self._find_pipeline(pipeline_hash)
        if info is None:
            return None

        # Load pipeline.json for DAG topology
        pipeline_json_path = info.path.parent / "pipeline.json"
        topology: dict[str, Any] | None = None
        if pipeline_json_path.exists():
            try:
                topology = json.loads(pipeline_json_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        backend = self._registry.get_backend(info.hash)
        runs = backend.list_runs(limit=MAX_QUERY_LIMIT)
        summary = serialize_pipeline(info, runs)
        summary["topology"] = topology
        summary["visual_ast"] = topology.get("visual_ast") if topology else None
        return summary

    def list_runs(
        self,
        pipeline_hash: str,
        status: PipelineTerminalStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]] | None:
        """Paginated runs for one pipeline."""
        info = self._find_pipeline(pipeline_hash)
        if info is None:
            return None
        backend = self._registry.get_backend(info.hash)
        runs = backend.list_runs(status=status, limit=limit, offset=offset)
        return [serialize_run(r, info.name, info.hash) for r in runs]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Single run detail resolved across all pipelines."""
        result = self._registry.resolve_run(run_id)
        if result is None:
            return None
        annotated, _backend = result
        return serialize_run(
            annotated.run, annotated.pipeline_name, annotated.pipeline_hash
        )

    def get_events(
        self, run_id: str, event_type: EventType | None = None
    ) -> list[dict[str, Any]] | None:
        """All events for a run, optionally filtered by type."""
        result = self._registry.resolve_run(run_id)
        if result is None:
            return None
        annotated, backend = result
        full_id = annotated.run.run_id
        events = backend.get_events(full_id, event_type=event_type)
        return [serialize_event(e) for e in events]

    def get_timeline(self, run_id: str) -> list[dict[str, Any]] | None:
        """Processed timeline data for a run."""
        result = self._registry.resolve_run(run_id)
        if result is None:
            return None
        annotated, backend = result
        full_id = annotated.run.run_id
        events = backend.get_events(full_id)
        return serialize_timeline(events)

    def compare(self, run1_id: str, run2_id: str) -> dict[str, Any] | None:
        """Compare two runs."""
        result1 = self._registry.resolve_run(run1_id)
        result2 = self._registry.resolve_run(run2_id)
        if result1 is None or result2 is None:
            return None

        annotated1, backend1 = result1
        annotated2, backend2 = result2

        events1 = backend1.get_events(annotated1.run.run_id)
        events2 = backend2.get_events(annotated2.run.run_id)

        comparison = compare_runs(
            annotated1.run,
            events1,
            annotated2.run,
            events2,
            annotated1.pipeline_name,
            annotated2.pipeline_name,
        )
        return serialize_comparison(comparison)

    def get_stats(self, pipeline_hash: str, days: int = 7) -> dict[str, Any] | None:
        """Aggregated stats for a pipeline."""
        info = self._find_pipeline(pipeline_hash)
        if info is None:
            return None
        backend = self._registry.get_backend(info.hash)
        runs = backend.list_runs(limit=MAX_QUERY_LIMIT)
        return serialize_stats(runs, days=days)

    def search_runs(self, prefix: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search runs by ID prefix across all pipelines."""
        results: list[dict[str, Any]] = []
        for info in self._registry.list_pipelines():
            backend = self._registry.get_backend(info.hash)
            for run in backend.find_runs_by_prefix(prefix, limit=limit):
                results.append(serialize_run(run, info.name, info.hash))
        results.sort(key=lambda r: r["start_time"], reverse=True)
        return results[:limit]

    def cleanup_runs(
        self,
        pipeline_hash: str,
        older_than_days: int | None = None,
        status: PipelineTerminalStatus | None = None,
        keep: int = 10,
        dry_run: bool = True,
    ) -> dict[str, Any] | None:
        """Delete runs matching filters. Returns preview when dry_run=True."""
        info = self._find_pipeline(pipeline_hash)
        if info is None:
            return None
        backend = self._registry.get_backend(info.hash)
        runs = backend.list_runs(limit=MAX_QUERY_LIMIT)

        # Filter candidates
        candidates = list(runs)
        if status is not None:
            candidates = [r for r in candidates if r.status == status]
        if older_than_days is not None:
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=older_than_days)
            candidates = [r for r in candidates if r.start_time < cutoff]

        # Always keep the N most recent (by start_time DESC — already sorted)
        to_delete = candidates[keep:] if len(candidates) > keep else []

        result: dict[str, Any] = {
            "count": len(to_delete),
            "runs": [serialize_run(r, info.name, info.hash) for r in to_delete[:20]],
        }

        if not dry_run:
            for run in to_delete:
                backend.delete_run(run.run_id)

        return result
