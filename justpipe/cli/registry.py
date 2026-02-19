"""Pipeline registry — scans ~/.justpipe/ for per-pipeline storage dirs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from justpipe.storage.interface import RunRecord
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import PipelineTerminalStatus


@dataclass(frozen=True)
class PipelineInfo:
    """Metadata about a discovered pipeline."""

    name: str
    hash: str
    path: Path  # path to runs.db


@dataclass(frozen=True)
class AnnotatedRun:
    """RunRecord with pipeline context attached."""

    run: RunRecord
    pipeline_name: str
    pipeline_hash: str


class PipelineRegistry:
    """Scans a storage directory for per-pipeline databases.

    Each pipeline lives in ``<storage_dir>/<hash>/`` containing:
    - ``runs.db`` — SQLite database
    - ``pipeline.json`` — descriptor with ``name`` field
    """

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def list_pipelines(self) -> list[PipelineInfo]:
        """Scan storage_dir for ``<hash>/pipeline.json`` dirs."""
        if not self._storage_dir.is_dir():
            return []
        result: list[PipelineInfo] = []
        for child in sorted(self._storage_dir.iterdir()):
            if not child.is_dir():
                continue
            db_path = child / "runs.db"
            meta_path = child / "pipeline.json"
            if not db_path.exists():
                continue
            name = child.name  # fallback to hash
            if meta_path.exists():
                try:
                    data = json.loads(meta_path.read_text())
                    name = data.get("name", name)
                except (json.JSONDecodeError, OSError):
                    pass
            result.append(PipelineInfo(name=name, hash=child.name, path=db_path))
        return result

    def get_backend(self, pipeline_hash: str) -> SQLiteBackend:
        """Open SQLiteBackend for a specific pipeline."""
        db_path = self._storage_dir / pipeline_hash / "runs.db"
        return SQLiteBackend(db_path)

    def list_all_runs(
        self,
        pipeline_name: str | None = None,
        status: PipelineTerminalStatus | None = None,
        limit: int = 100,
    ) -> list[AnnotatedRun]:
        """Aggregate runs across all pipelines, sorted by start_time DESC."""
        pipelines = self.list_pipelines()
        if pipeline_name:
            pipelines = [p for p in pipelines if p.name == pipeline_name]

        all_runs: list[AnnotatedRun] = []
        for pipe in pipelines:
            backend = SQLiteBackend(pipe.path)
            runs = backend.list_runs(status=status, limit=limit)
            all_runs.extend(
                AnnotatedRun(run=run, pipeline_name=pipe.name, pipeline_hash=pipe.hash)
                for run in runs
            )

        # Sort by start_time DESC and apply limit
        all_runs.sort(key=lambda a: a.run.start_time, reverse=True)
        return all_runs[:limit]

    def resolve_run(
        self, run_id_prefix: str
    ) -> tuple[AnnotatedRun, SQLiteBackend] | None:
        """Find a run by ID prefix across all pipelines.

        Raises ValueError if prefix matches multiple runs.
        Returns None if no match found.
        """
        matches: list[tuple[AnnotatedRun, SQLiteBackend]] = []
        for pipe in self.list_pipelines():
            backend = SQLiteBackend(pipe.path)
            # Try exact match first
            run = backend.get_run(run_id_prefix)
            if run:
                annotated = AnnotatedRun(
                    run=run, pipeline_name=pipe.name, pipeline_hash=pipe.hash
                )
                return annotated, backend

            # Prefix search via SQL LIKE (replaces full scan)
            prefix_runs = backend.find_runs_by_prefix(run_id_prefix, limit=11)
            for run in prefix_runs:
                annotated = AnnotatedRun(
                    run=run, pipeline_name=pipe.name, pipeline_hash=pipe.hash
                )
                matches.append((annotated, backend))

        if not matches:
            return None
        if len(matches) > 1:
            ids = ", ".join(m[0].run.run_id[:12] for m in matches[:5])
            raise ValueError(
                f"Ambiguous run ID prefix '{run_id_prefix}' matches {len(matches)} runs: {ids}"
            )
        return matches[0]
