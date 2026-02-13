"""Functional tests for CLI commands with real SQLiteBackend."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from justpipe.cli.main import cli
from justpipe.storage.interface import RunRecord
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import EventType, PipelineTerminalStatus


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


def _make_run(
    run_id: str = "test-run-id-abcdef1234567890",
    status: PipelineTerminalStatus = PipelineTerminalStatus.SUCCESS,
    start: datetime | None = None,
    duration_s: float = 1.5,
    error_message: str | None = None,
    user_meta: str | None = None,
) -> RunRecord:
    start = start or datetime(2024, 1, 15, 12, 0, 0)
    return RunRecord(
        run_id=run_id,
        start_time=start,
        end_time=start + timedelta(seconds=duration_s),
        duration=timedelta(seconds=duration_s),
        status=status,
        error_message=error_message,
        user_meta=user_meta,
    )


def _make_events() -> list[str]:
    """Create a minimal set of serialized events."""
    base_ts = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    return [
        json.dumps(
            {
                "type": EventType.STEP_START.value,
                "stage": "step_a",
                "timestamp": base_ts + 0.1,
                "run_id": "test-run",
                "origin_run_id": "test-run",
                "parent_run_id": None,
                "seq": 1,
                "node_kind": "step",
                "invocation_id": "inv-1",
                "parent_invocation_id": None,
                "owner_invocation_id": None,
                "attempt": 1,
                "scope": [],
                "meta": {},
                "payload": None,
            }
        ),
        json.dumps(
            {
                "type": EventType.STEP_END.value,
                "stage": "step_a",
                "timestamp": base_ts + 0.5,
                "run_id": "test-run",
                "origin_run_id": "test-run",
                "parent_run_id": None,
                "seq": 2,
                "node_kind": "step",
                "invocation_id": "inv-1",
                "parent_invocation_id": None,
                "owner_invocation_id": None,
                "attempt": 1,
                "scope": [],
                "meta": {},
                "payload": None,
            }
        ),
    ]


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
        backend.save_run(_make_run(), [])

        result = _invoke(tmp_path, ["list"])
        assert result.exit_code == 0
        assert "test_pipeline" in result.output
        assert "1 run(s)" in result.output

    def test_status_filter(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(_make_run("run-ok", PipelineTerminalStatus.SUCCESS), [])
        backend.save_run(_make_run("run-fail", PipelineTerminalStatus.FAILED), [])

        result = _invoke(tmp_path, ["list", "--status", "failed"])
        assert result.exit_code == 0
        assert "1 run(s)" in result.output


class TestShowCommand:
    def test_show_run(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(
            _make_run(user_meta='{"version": "1.0"}'),
            _make_events(),
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
        backend.save_run(_make_run(), _make_events())

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
        backend.save_run(_make_run("run-aaa-1234567890123456"), _make_events())
        backend.save_run(_make_run("run-bbb-1234567890123456"), _make_events())

        result = _invoke(tmp_path, ["compare", "run-aaa", "run-bbb"])
        assert result.exit_code == 0
        assert "Run Comparison" in result.output


class TestExportCommand:
    def test_export_json(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        backend.save_run(_make_run(), _make_events())

        result = _invoke(
            tmp_path, ["export", "test-run-id", "--output", str(tmp_path / "out.json")]
        )
        assert result.exit_code == 0
        assert "exported" in result.output.lower()

        data = json.loads((tmp_path / "out.json").read_text())
        assert data["run"]["pipeline_name"] == "test_pipeline"
        assert data["run"]["status"] == "success"
        assert data["event_count"] == 2

    def test_export_events_survives_malformed_json(self) -> None:
        """Test that _export_events handles malformed JSON gracefully."""
        from justpipe.cli.commands.export import _export_events
        from justpipe.storage.interface import StoredEvent

        events = [
            StoredEvent(
                seq=1,
                timestamp=datetime(2024, 1, 15, 12, 0, 0),
                event_type=EventType.STEP_START,
                step_name="step_a",
                data='{"type": "step_start", "stage": "step_a"}',
            ),
            StoredEvent(
                seq=2,
                timestamp=datetime(2024, 1, 15, 12, 0, 1),
                event_type=EventType.STEP_END,
                step_name="step_a",
                data="not valid json {{{",
            ),
        ]
        exported = _export_events(events)
        assert len(exported) == 2
        assert exported[0]["data"] is not None
        assert exported[1]["data"] is None


class TestStatsCommand:
    def test_stats(self, tmp_path: Path) -> None:
        backend = _setup_storage(tmp_path)
        now = datetime.now()
        backend.save_run(_make_run(start=now - timedelta(hours=1)), [])
        backend.save_run(
            _make_run(
                "run-fail",
                PipelineTerminalStatus.FAILED,
                error_message="boom",
                start=now - timedelta(hours=2),
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
                _make_run(
                    f"run-{i:03d}-padded-to-be-long",
                    start=datetime(2020, 1, 1) + timedelta(hours=i),
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
        backend.save_run(_make_run(), [])
        _setup_storage(tmp_path, "other_pipeline", "hash2")

        result = _invoke(tmp_path, ["pipelines"])
        assert result.exit_code == 0
        assert "my_pipeline" in result.output
        assert "2 pipeline(s)" in result.output
