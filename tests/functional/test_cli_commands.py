"""Functional tests for CLI commands with real SQLiteBackend."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from justpipe.cli.main import cli
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import PipelineTerminalStatus
from tests.factories import make_events, make_run


def _setup_storage(
    tmp_path: Path,
    pipeline_name: str = "test_pipeline",
    pipeline_hash: str = "abc123hash",
) -> SQLiteBackend:
    """Create a pipeline storage dir with pipeline.json and return backend."""
    pipe_dir = tmp_path / pipeline_hash
    pipe_dir.mkdir(parents=True)
    (pipe_dir / "pipeline.json").write_text(json.dumps({"name": pipeline_name}))
    return SQLiteBackend(pipe_dir / "runs.db")


def _invoke(tmp_path: Path, args: list[str], monkeypatch: Any | None = None) -> Any:
    """Invoke CLI with JUSTPIPE_STORAGE_PATH set to tmp_path."""
    runner = CliRunner(env={"JUSTPIPE_STORAGE_PATH": str(tmp_path)})
    return runner.invoke(cli, args, catch_exceptions=False)


class TestListCommand:
    def test_no_runs(self, tmp_path: Path) -> None:
        _setup_storage(tmp_path)
        result = _invoke(tmp_path, ["list"])
        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_shows_runs(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(make_run(), [])

        result = _invoke(tmp_path, ["list"])
        assert result.exit_code == 0
        assert "test_pipeline" in result.output
        assert "1 run(s)" in result.output

    def test_status_filter(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(make_run("run-ok", PipelineTerminalStatus.SUCCESS), [])
        backend.save_run(make_run("run-fail", PipelineTerminalStatus.FAILED), [])

        result = _invoke(tmp_path, ["list", "--status", "failed"])
        assert result.exit_code == 0
        assert "1 run(s)" in result.output


class TestShowCommand:
    def test_show_run(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(
            make_run("test-run-id-abcdef1234567890", run_meta='{"version": "1.0"}'),
            make_events(),
        )

        result = _invoke(tmp_path, ["show", "test-run-id"])
        assert result.exit_code == 0
        assert "test_pipeline" in result.output
        assert "success" in result.output
        assert "step_a" in result.output
        assert "version" in result.output

    def test_show_not_found(self, tmp_path: Path) -> None:
        _setup_storage(tmp_path)
        result = _invoke(tmp_path, ["show", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestTimelineCommand:
    def test_timeline_ascii(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(make_run("test-run-id-abcdef1234567890"), make_events())

        result = _invoke(tmp_path, ["timeline", "test-run-id"])
        assert result.exit_code == 0
        assert "step_a" in result.output

    def test_timeline_not_found(self, tmp_path: Path) -> None:
        _setup_storage(tmp_path)
        result = _invoke(tmp_path, ["timeline", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestCompareCommand:
    def test_compare_two_runs(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(make_run("run-aaa-1234567890123456"), make_events())
        backend.save_run(make_run("run-bbb-1234567890123456"), make_events())

        result = _invoke(tmp_path, ["compare", "run-aaa", "run-bbb"])
        assert result.exit_code == 0
        assert "Run Comparison" in result.output


class TestExportCommand:
    def test_export_json(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(make_run("test-run-id-abcdef1234567890"), make_events())

        result = _invoke(
            tmp_path, ["export", "test-run-id", "--output", str(tmp_path / "out.json")]
        )
        assert result.exit_code == 0
        assert "exported" in result.output.lower()

        data = json.loads((tmp_path / "out.json").read_text())
        assert data["run"]["pipeline_name"] == "test_pipeline"
        assert data["run"]["status"] == "success"
        assert data["event_count"] == 4


class TestStatsCommand:
    def test_stats(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        now = datetime.now()
        backend.save_run(make_run(start_time=now - timedelta(hours=1)), [])
        backend.save_run(
            make_run(
                "run-fail",
                PipelineTerminalStatus.FAILED,
                start_time=now - timedelta(hours=2),
                error_message="boom",
            ),
            [],
        )

        result = _invoke(tmp_path, ["stats", "--days", "7"])
        assert result.exit_code == 0
        assert "Total Runs" in result.output


class TestCleanupCommand:
    def test_cleanup_dry_run(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        for i in range(15):
            backend.save_run(
                make_run(
                    f"run-{i:03d}-padded-to-be-long",
                    start_time=datetime(2020, 1, 1) + timedelta(hours=i),
                ),
                [],
            )

        result = _invoke(tmp_path, ["cleanup", "--keep", "5", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output


class TestPipelinesCommand:
    def test_no_pipelines(self, tmp_path: Path) -> None:
        result = _invoke(tmp_path, ["pipelines"])
        assert result.exit_code == 0
        assert "No pipelines found" in result.output

    def test_lists_pipelines(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path, "my_pipeline", "hash1")
        backend.save_run(make_run(), [])
        _setup_storage(tmp_path, "other_pipeline", "hash2")

        result = _invoke(tmp_path, ["pipelines"])
        assert result.exit_code == 0
        assert "my_pipeline" in result.output
        assert "2 pipeline(s)" in result.output
