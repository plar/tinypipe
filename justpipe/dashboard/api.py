"""Dashboard API — endpoint handlers backed by PipelineRegistry."""

from __future__ import annotations

import json
from typing import Any

from justpipe.cli.registry import PipelineRegistry
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
        pipelines_by_hash = {info.hash: info for info in self._registry.list_pipelines()}
        info = pipelines_by_hash.get(pipeline_hash)
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
        return summary

    def list_runs(
        self,
        pipeline_hash: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]] | None:
        """Paginated runs for one pipeline."""
        for info in self._registry.list_pipelines():
            if info.hash == pipeline_hash:
                backend = self._registry.get_backend(info.hash)
                try:
                    enum_status = PipelineTerminalStatus(status) if status else None
                except ValueError:
                    return []
                runs = backend.list_runs(status=enum_status, limit=limit, offset=offset)
                return [serialize_run(r, info.name, info.hash) for r in runs]
        return None

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
        self, run_id: str, event_type: str | None = None
    ) -> list[dict[str, Any]] | None:
        """All events for a run, optionally filtered by type."""
        result = self._registry.resolve_run(run_id)
        if result is None:
            return None
        _annotated, backend = result
        try:
            enum_type = EventType(event_type) if event_type else None
        except ValueError:
            return []
        events = backend.get_events(run_id, event_type=enum_type)
        return [serialize_event(e) for e in events]

    def get_timeline(self, run_id: str) -> list[dict[str, Any]] | None:
        """Processed timeline data for a run."""
        result = self._registry.resolve_run(run_id)
        if result is None:
            return None
        _annotated, backend = result
        events = backend.get_events(run_id)
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
        for info in self._registry.list_pipelines():
            if info.hash == pipeline_hash:
                backend = self._registry.get_backend(info.hash)
                runs = backend.list_runs(limit=MAX_QUERY_LIMIT)
                return serialize_stats(runs, days=days)
        return None
