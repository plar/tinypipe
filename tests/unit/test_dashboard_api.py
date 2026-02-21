"""Tests for DashboardAPI endpoint handlers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from justpipe.cli.registry import PipelineRegistry
from justpipe.dashboard.api import DashboardAPI
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import EventType, PipelineTerminalStatus
from tests.factories import make_events, make_run


def _setup_pipeline(
    storage_dir: Path,
    hash_name: str,
    pipeline_name: str,
    topology: dict[str, Any] | None = None,
) -> SQLiteBackend:
    """Create a pipeline dir with pipeline.json and return its SQLiteBackend."""
    pipe_dir = storage_dir / hash_name
    pipe_dir.mkdir(parents=True)
    meta = {"name": pipeline_name}
    if topology:
        meta.update(topology)
    (pipe_dir / "pipeline.json").write_text(json.dumps(meta))
    return SQLiteBackend(pipe_dir / "runs.db")


@pytest.fixture()
def api_env(tmp_path: Path) -> tuple[DashboardAPI, SQLiteBackend]:
    """Create a DashboardAPI with one pipeline containing runs."""
    backend = _setup_pipeline(
        tmp_path,
        "abc123",
        "test_pipeline",
        {
            "nodes": {
                "step_a": {"kind": "step", "targets": ["step_b"]},
                "step_b": {"kind": "step", "targets": []},
            }
        },
    )
    backend.save_run(make_run("run-001", PipelineTerminalStatus.SUCCESS), make_events())
    backend.save_run(
        make_run(
            "run-002",
            PipelineTerminalStatus.FAILED,
            error_message="boom",
            error_step="step_a",
            start_time=datetime(2025, 1, 1, 11, 0, 0),
        ),
        make_events(),
    )
    registry = PipelineRegistry(tmp_path)
    return DashboardAPI(registry), backend


class TestListPipelines:
    def test_returns_pipelines(
        self, api_env: tuple[DashboardAPI, SQLiteBackend]
    ) -> None:
        api, _ = api_env
        result = api.list_pipelines()

        assert len(result) == 1
        assert result[0]["name"] == "test_pipeline"
        assert result[0]["hash"] == "abc123"
        assert result[0]["total_runs"] == 2
        assert result[0]["success_count"] == 1

    def test_empty(self, tmp_path: Path) -> None:
        api = DashboardAPI(PipelineRegistry(tmp_path))
        assert api.list_pipelines() == []


class TestGetPipeline:
    def test_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.get_pipeline("abc123")

        assert result is not None
        assert result["name"] == "test_pipeline"
        assert result["topology"] is not None
        assert "step_a" in result["topology"]["nodes"]

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.get_pipeline("nonexistent") is None


class TestListRuns:
    def test_all_runs(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.list_runs("abc123")

        assert result is not None
        assert len(result) == 2

    def test_filter_by_status(
        self, api_env: tuple[DashboardAPI, SQLiteBackend]
    ) -> None:
        api, _ = api_env
        result = api.list_runs("abc123", status=PipelineTerminalStatus.FAILED)

        assert result is not None
        assert len(result) == 1
        assert result[0]["status"] == "failed"

    def test_pagination(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.list_runs("abc123", limit=1, offset=0)

        assert result is not None
        assert len(result) == 1

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.list_runs("nonexistent") is None


class TestGetRun:
    def test_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.get_run("run-001")

        assert result is not None
        assert result["run_id"] == "run-001"
        assert result["status"] == "success"
        assert result["pipeline_name"] == "test_pipeline"

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.get_run("nonexistent") is None


class TestGetEvents:
    def test_all_events(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.get_events("run-001")

        assert result is not None
        assert len(result) == 4  # start, step_start, step_end, finish

    def test_filter_by_type(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.get_events("run-001", event_type=EventType.STEP_START)

        assert result is not None
        assert len(result) == 1
        assert result[0]["event_type"] == "step_start"

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.get_events("nonexistent") is None


class TestGetTimeline:
    def test_returns_entries(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.get_timeline("run-001")

        assert result is not None
        assert len(result) >= 1
        assert result[0]["step_name"] == "step_a"
        assert result[0]["status"] == "success"
        assert result[0]["duration_seconds"] > 0

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.get_timeline("nonexistent") is None


class TestCompare:
    def test_basic(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        result = api.compare("run-001", "run-002")

        assert result is not None
        assert result["run1_id"] == "run-001"
        assert result["run2_id"] == "run-002"
        assert isinstance(result["duration_diff"], float)
        assert isinstance(result["step_timing_diff"], dict)

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.compare("run-001", "nonexistent") is None


class TestGetStats:
    def test_basic(self, tmp_path: Path) -> None:
        """Stats require recent runs (within days window)."""
        now = datetime.now(tz=timezone.utc)
        backend = _setup_pipeline(tmp_path, "stat1", "stat_pipeline")
        backend.save_run(
            make_run(
                "r1",
                PipelineTerminalStatus.SUCCESS,
                start_time=now - timedelta(hours=1),
            ),
            [],
        )
        backend.save_run(
            make_run(
                "r2", PipelineTerminalStatus.FAILED, start_time=now - timedelta(hours=2)
            ),
            [],
        )
        api = DashboardAPI(PipelineRegistry(tmp_path))
        result = api.get_stats("stat1", days=7)

        assert result is not None
        assert result["total_runs"] == 2
        assert result["success_count"] == 1
        assert result["failed_count"] == 1

    def test_not_found(self, api_env: tuple[DashboardAPI, SQLiteBackend]) -> None:
        api, _ = api_env
        assert api.get_stats("nonexistent") is None
