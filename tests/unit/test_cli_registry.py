"""Tests for CLI PipelineRegistry."""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from justpipe.cli.registry import PipelineRegistry
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import PipelineTerminalStatus
from tests.factories import make_run


def _make_pipeline_dir(
    storage_dir: Path, hash_name: str, pipeline_name: str
) -> SQLiteBackend:
    """Create a pipeline directory with pipeline.json and return its backend."""
    pipe_dir = storage_dir / hash_name
    pipe_dir.mkdir(parents=True)
    (pipe_dir / "pipeline.json").write_text(json.dumps({"name": pipeline_name}))
    return SQLiteBackend(pipe_dir / "runs.db")


class TestPipelineRegistry:
    def test_list_pipelines_empty(self, tmp_path: Path) -> None:
        registry = PipelineRegistry(tmp_path)
        assert registry.list_pipelines() == []

    def test_list_pipelines_finds_dirs(self, tmp_path: Path) -> None:
        _make_pipeline_dir(tmp_path, "abc123", "my_pipeline")
        _make_pipeline_dir(tmp_path, "def456", "other_pipeline")

        registry = PipelineRegistry(tmp_path)
        pipelines = registry.list_pipelines()

        assert len(pipelines) == 2
        names = {p.name for p in pipelines}
        assert names == {"my_pipeline", "other_pipeline"}

    def test_list_pipelines_ignores_dirs_without_db(self, tmp_path: Path) -> None:
        (tmp_path / "no_db_dir").mkdir()
        (tmp_path / "no_db_dir" / "pipeline.json").write_text('{"name": "x"}')
        _make_pipeline_dir(tmp_path, "valid", "valid_pipe")

        registry = PipelineRegistry(tmp_path)
        pipelines = registry.list_pipelines()

        assert len(pipelines) == 1
        assert pipelines[0].name == "valid_pipe"

    def test_list_pipelines_falls_back_to_hash_name(self, tmp_path: Path) -> None:
        pipe_dir = tmp_path / "abc123"
        pipe_dir.mkdir()
        SQLiteBackend(pipe_dir / "runs.db")  # creates DB
        # No pipeline.json

        registry = PipelineRegistry(tmp_path)
        pipelines = registry.list_pipelines()

        assert len(pipelines) == 1
        assert pipelines[0].name == "abc123"

    def test_get_backend(self, tmp_path: Path) -> None:
        _make_pipeline_dir(tmp_path, "abc123", "my_pipeline")
        registry = PipelineRegistry(tmp_path)
        backend = registry.get_backend("abc123")
        assert isinstance(backend, SQLiteBackend)

    def test_list_all_runs_empty(self, tmp_path: Path) -> None:
        _make_pipeline_dir(tmp_path, "abc123", "my_pipeline")
        registry = PipelineRegistry(tmp_path)
        assert registry.list_all_runs() == []

    def test_list_all_runs_aggregates(self, tmp_path: Path) -> None:
        backend1 = _make_pipeline_dir(tmp_path, "abc123", "pipeline_a")
        backend2 = _make_pipeline_dir(tmp_path, "def456", "pipeline_b")

        backend1.save_run(make_run("run-aaa-1"), [])
        backend2.save_run(
            make_run(
                "run-bbb-1", start_time=make_run().start_time - timedelta(hours=1)
            ),
            [],
        )

        registry = PipelineRegistry(tmp_path)
        runs = registry.list_all_runs()

        assert len(runs) == 2
        # Sorted by start_time DESC, so run-aaa-1 (newer) first
        assert runs[0].run.run_id == "run-aaa-1"
        assert runs[0].pipeline_name == "pipeline_a"
        assert runs[1].run.run_id == "run-bbb-1"
        assert runs[1].pipeline_name == "pipeline_b"

    def test_list_all_runs_filter_by_pipeline(self, tmp_path: Path) -> None:
        backend1 = _make_pipeline_dir(tmp_path, "abc123", "pipeline_a")
        backend2 = _make_pipeline_dir(tmp_path, "def456", "pipeline_b")

        backend1.save_run(make_run("run-aaa-1"), [])
        backend2.save_run(make_run("run-bbb-1"), [])

        registry = PipelineRegistry(tmp_path)
        runs = registry.list_all_runs(pipeline_name="pipeline_a")

        assert len(runs) == 1
        assert runs[0].pipeline_name == "pipeline_a"

    def test_list_all_runs_filter_by_status(self, tmp_path: Path) -> None:
        backend = _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        backend.save_run(make_run("run-1", PipelineTerminalStatus.SUCCESS), [])
        backend.save_run(make_run("run-2", PipelineTerminalStatus.FAILED), [])

        registry = PipelineRegistry(tmp_path)
        runs = registry.list_all_runs(status=PipelineTerminalStatus.FAILED)

        assert len(runs) == 1
        assert runs[0].run.run_id == "run-2"

    def test_list_all_runs_respects_limit(self, tmp_path: Path) -> None:
        backend = _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        for i in range(5):
            backend.save_run(
                make_run(
                    f"run-{i}",
                    start_time=make_run().start_time - timedelta(hours=i),
                ),
                [],
            )

        registry = PipelineRegistry(tmp_path)
        runs = registry.list_all_runs(limit=3)

        assert len(runs) == 3

    def test_resolve_run_exact_match(self, tmp_path: Path) -> None:
        backend = _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        backend.save_run(make_run("run-exact-id-1234"), [])

        registry = PipelineRegistry(tmp_path)
        result = registry.resolve_run("run-exact-id-1234")

        assert result is not None
        annotated, _ = result
        assert annotated.run.run_id == "run-exact-id-1234"
        assert annotated.pipeline_name == "my_pipe"

    def test_resolve_run_prefix_match(self, tmp_path: Path) -> None:
        backend = _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        backend.save_run(make_run("run-prefix-match-xyz"), [])

        registry = PipelineRegistry(tmp_path)
        result = registry.resolve_run("run-prefix")

        assert result is not None
        annotated, _ = result
        assert annotated.run.run_id == "run-prefix-match-xyz"

    def test_resolve_run_not_found(self, tmp_path: Path) -> None:
        _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        registry = PipelineRegistry(tmp_path)
        assert registry.resolve_run("nonexistent") is None

    def test_resolve_run_ambiguous(self, tmp_path: Path) -> None:
        backend = _make_pipeline_dir(tmp_path, "abc123", "my_pipe")
        backend.save_run(make_run("run-amb-1"), [])
        backend.save_run(make_run("run-amb-2"), [])

        registry = PipelineRegistry(tmp_path)
        with pytest.raises(ValueError, match="Ambiguous"):
            registry.resolve_run("run-amb")
