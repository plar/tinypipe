"""Consolidated tests for storage backends."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from justpipe.storage.memory import InMemoryBackend
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import EventType, PipelineTerminalStatus
from tests.factories import make_events, make_run


class TestInMemoryBackend:
    def test_save_and_get_run(self) -> None:
        backend = InMemoryBackend()
        run = make_run()
        backend.save_run(run, make_events())
        result = backend.get_run("run1")
        assert result is not None
        assert result.run_id == "run1"
        assert result.status == PipelineTerminalStatus.SUCCESS

    def test_get_run_not_found(self) -> None:
        backend = InMemoryBackend()
        assert backend.get_run("missing") is None

    def test_list_runs(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run("r1"), [])
        backend.save_run(make_run("r2", PipelineTerminalStatus.FAILED), [])
        assert len(backend.list_runs()) == 2
        assert len(backend.list_runs(status=PipelineTerminalStatus.FAILED)) == 1

    def test_list_runs_pagination(self) -> None:
        backend = InMemoryBackend()
        for i in range(5):
            backend.save_run(make_run(f"r{i}"), [])
        assert len(backend.list_runs(limit=2)) == 2
        assert len(backend.list_runs(limit=2, offset=3)) == 2

    def test_get_events(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run(), make_events())
        events = backend.get_events("run1")
        assert len(events) == 4
        assert events[0].event_type == EventType.START

    def test_get_events_filtered(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run(), make_events())
        events = backend.get_events("run1", event_type=EventType.STEP_START)
        assert len(events) == 1
        assert events[0].step_name == "step_a"

    def test_delete_run(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run(), make_events())
        assert backend.delete_run("run1") is True
        assert backend.get_run("run1") is None
        assert backend.delete_run("run1") is False

    def test_find_runs_by_prefix_matches(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run("run-abc-123"), [])
        backend.save_run(make_run("run-abc-456"), [])
        backend.save_run(make_run("run-xyz-789"), [])
        matches = backend.find_runs_by_prefix("run-abc")
        assert len(matches) == 2
        assert all(r.run_id.startswith("run-abc") for r in matches)

    def test_find_runs_by_prefix_no_match(self) -> None:
        backend = InMemoryBackend()
        backend.save_run(make_run("run-abc-123"), [])
        assert backend.find_runs_by_prefix("run-xyz") == []

    def test_find_runs_by_prefix_respects_limit(self) -> None:
        backend = InMemoryBackend()
        for i in range(5):
            backend.save_run(make_run(f"run-{i}"), [])
        matches = backend.find_runs_by_prefix("run-", limit=2)
        assert len(matches) == 2

    def test_get_events_skips_invalid_event_type(self) -> None:
        """Events with invalid/missing type field are skipped, not crash."""
        backend = InMemoryBackend()
        run = make_run("r1")

        events = [
            json.dumps({"type": "step_start", "stage": "a", "timestamp": 100.0}),
            json.dumps({"type": "", "stage": "bad", "timestamp": 101.0}),
            json.dumps({"stage": "missing_type", "timestamp": 102.0}),
            json.dumps({"type": "step_end", "stage": "a", "timestamp": 103.0}),
        ]
        backend.save_run(run, events)

        result = backend.get_events("r1")
        assert len(result) == 2

    def test_get_events_filtered_with_invalid_types(self) -> None:
        """Filtering by event_type works even when some events have bad types."""
        backend = InMemoryBackend()
        run = make_run("r1")

        events = [
            json.dumps({"type": "step_start", "stage": "a", "timestamp": 100.0}),
            json.dumps({"type": "bogus", "stage": "bad", "timestamp": 101.0}),
            json.dumps({"type": "step_end", "stage": "a", "timestamp": 102.0}),
        ]
        backend.save_run(run, events)

        result = backend.get_events("r1", event_type=EventType.STEP_END)
        assert len(result) == 1


class TestSQLiteBackend:
    @pytest.fixture()
    def backend(self, tmp_path: Path) -> SQLiteBackend:
        return SQLiteBackend(tmp_path / "runs.db")

    def test_save_and_get_run(self, backend: SQLiteBackend) -> None:
        run = make_run()
        backend.save_run(run, make_events())
        result = backend.get_run("run1")
        assert result is not None
        assert result.run_id == "run1"
        assert result.status == PipelineTerminalStatus.SUCCESS

    def test_get_run_not_found(self, backend: SQLiteBackend) -> None:
        assert backend.get_run("missing") is None

    def test_list_runs_with_status_filter(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run("r1"), [])
        backend.save_run(make_run("r2", PipelineTerminalStatus.FAILED), [])
        assert len(backend.list_runs()) == 2
        assert len(backend.list_runs(status=PipelineTerminalStatus.SUCCESS)) == 1
        assert len(backend.list_runs(status=PipelineTerminalStatus.FAILED)) == 1

    def test_get_events(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run(), make_events())
        events = backend.get_events("run1")
        assert len(events) == 4

    def test_get_events_filtered_by_type(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run(), make_events())
        events = backend.get_events("run1", event_type=EventType.STEP_START)
        assert len(events) == 1
        assert events[0].step_name == "step_a"

    def test_delete_run_cascades(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run(), make_events())
        assert backend.delete_run("run1") is True
        assert backend.get_run("run1") is None
        assert backend.get_events("run1") == []
        assert backend.delete_run("run1") is False

    def test_generated_columns(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run(), make_events())
        events = backend.get_events("run1")
        assert events[0].event_type == EventType.START
        assert events[1].event_type == EventType.STEP_START
        assert events[1].step_name == "step_a"

    def test_find_runs_by_prefix_matches(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run("run-abc-123"), [])
        backend.save_run(make_run("run-abc-456"), [])
        backend.save_run(make_run("run-xyz-789"), [])
        matches = backend.find_runs_by_prefix("run-abc")
        assert len(matches) == 2
        assert all(r.run_id.startswith("run-abc") for r in matches)

    def test_find_runs_by_prefix_no_match(self, backend: SQLiteBackend) -> None:
        backend.save_run(make_run("run-abc-123"), [])
        assert backend.find_runs_by_prefix("run-xyz") == []

    def test_find_runs_by_prefix_respects_limit(self, backend: SQLiteBackend) -> None:
        for i in range(5):
            backend.save_run(make_run(f"run-{i}"), [])
        matches = backend.find_runs_by_prefix("run-", limit=2)
        assert len(matches) == 2

    def test_find_runs_by_prefix_rejects_invalid_chars(
        self, backend: SQLiteBackend
    ) -> None:
        backend.save_run(make_run("run-abc"), [])
        assert backend.find_runs_by_prefix("run%") == []
        assert backend.find_runs_by_prefix("run;DROP") == []
        assert backend.find_runs_by_prefix("") == []

    def test_atomic_save(self, backend: SQLiteBackend) -> None:
        """If event insertion fails, run should not be saved."""
        bad_events = ["not valid json"]
        with pytest.raises(Exception):
            backend.save_run(make_run(), bad_events)
        assert backend.get_run("run1") is None
