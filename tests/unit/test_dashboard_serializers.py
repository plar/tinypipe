"""Tests for dashboard serializer functions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from justpipe.cli.registry import PipelineInfo
from justpipe.dashboard.serializers import (
    serialize_comparison,
    serialize_event,
    serialize_pipeline,
    serialize_run,
    serialize_stats,
    serialize_timeline,
)
from justpipe.observability.compare import RunComparison
from justpipe.storage.interface import RunRecord, StoredEvent
from justpipe.types import EventType, PipelineTerminalStatus
from tests.factories import make_run


class TestSerializeRun:
    def test_basic_fields(self) -> None:
        run = make_run("abc123", PipelineTerminalStatus.SUCCESS)
        result = serialize_run(run, "my_pipe", "hash1")

        assert result["run_id"] == "abc123"
        assert result["pipeline_name"] == "my_pipe"
        assert result["pipeline_hash"] == "hash1"
        assert result["status"] == "success"
        assert result["start_time"] == run.start_time.isoformat()
        assert result["duration_seconds"] == 5.0
        assert result["error_message"] is None
        assert result["run_meta"] is None

    def test_with_run_meta_json(self) -> None:
        meta = json.dumps({"tags": ["prod"], "counters": {"items": 5}})
        run = make_run("r1", run_meta=meta)
        result = serialize_run(run, "p", "h")

        assert result["run_meta"] == {"tags": ["prod"], "counters": {"items": 5}}

    def test_with_invalid_run_meta(self) -> None:
        run = make_run("r1", run_meta="not json{")
        result = serialize_run(run, "p", "h")
        assert result["run_meta"] == "not json{"

    def test_failed_run(self) -> None:
        run = make_run(
            "r1",
            PipelineTerminalStatus.FAILED,
            error_message="boom",
            error_step="step_a",
        )
        result = serialize_run(run, "p", "h")

        assert result["status"] == "failed"
        assert result["error_message"] == "boom"
        assert result["error_step"] == "step_a"

    def test_none_end_time(self) -> None:
        run = RunRecord(
            run_id="r1",
            start_time=datetime(2025, 1, 1),
            end_time=None,
            duration=None,
            status=PipelineTerminalStatus.FAILED,
        )
        result = serialize_run(run, "p", "h")
        assert result["end_time"] is None
        assert result["duration_seconds"] is None


class TestSerializeEvent:
    def test_basic(self) -> None:
        event = StoredEvent(
            seq=1,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            event_type=EventType.STEP_START,
            step_name="step_a",
            data='{"foo": "bar"}',
        )
        result = serialize_event(event)

        assert result["seq"] == 1
        assert result["event_type"] == "step_start"
        assert result["step_name"] == "step_a"
        assert result["data"] == {"foo": "bar"}

    def test_invalid_data_json(self) -> None:
        event = StoredEvent(
            seq=1,
            timestamp=datetime(2025, 1, 1),
            event_type=EventType.START,
            step_name="system",
            data="not-json",
        )
        result = serialize_event(event)
        assert result["data"] is None


class TestSerializePipeline:
    def test_basic(self, tmp_path: Path) -> None:
        info = PipelineInfo(name="my_pipe", hash="abc123", path=tmp_path / "runs.db")
        runs = [
            make_run("r1", PipelineTerminalStatus.SUCCESS),
            make_run("r2", PipelineTerminalStatus.SUCCESS),
            make_run("r3", PipelineTerminalStatus.FAILED),
        ]
        result = serialize_pipeline(info, runs)

        assert result["name"] == "my_pipe"
        assert result["hash"] == "abc123"
        assert result["total_runs"] == 3
        assert result["success_count"] == 2
        assert result["success_rate"] == 66.7
        assert result["avg_duration_seconds"] == 5.0

    def test_empty_runs(self, tmp_path: Path) -> None:
        info = PipelineInfo(name="empty", hash="h1", path=tmp_path / "runs.db")
        result = serialize_pipeline(info, [])

        assert result["total_runs"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_duration_seconds"] is None
        assert result["last_run_time"] is None


class TestSerializeComparison:
    def test_basic(self) -> None:
        comp = RunComparison(
            run1_id="r1",
            run2_id="r2",
            pipeline1_name="p1",
            pipeline2_name="p2",
            duration_diff=1.5,
            status_same=True,
            pipeline_same=False,
            step_timing_diff={"step_a": 0.3},
            new_steps=["step_b"],
            removed_steps=[],
            event_count_diff=2,
        )
        result = serialize_comparison(comp)

        assert result["run1_id"] == "r1"
        assert result["run2_id"] == "r2"
        assert result["duration_diff"] == 1.5
        assert result["new_steps"] == ["step_b"]
        assert result["event_count_diff"] == 2


class TestSerializeStats:
    def test_basic(self) -> None:
        now = datetime.now(tz=timezone.utc)
        runs = [
            make_run(
                "r1",
                PipelineTerminalStatus.SUCCESS,
                start_time=now - timedelta(hours=1),
            ),
            make_run(
                "r2",
                PipelineTerminalStatus.SUCCESS,
                start_time=now - timedelta(hours=2),
            ),
            make_run(
                "r3", PipelineTerminalStatus.FAILED, start_time=now - timedelta(hours=3)
            ),
        ]
        result = serialize_stats(runs, days=7)

        assert result["total_runs"] == 3
        assert result["success_count"] == 2
        assert result["failed_count"] == 1
        assert result["success_rate"] == 66.7
        assert result["duration_stats"] is not None
        assert result["duration_stats"]["avg"] == 5.0

    def test_filters_by_days(self) -> None:
        now = datetime.now(tz=timezone.utc)
        runs = [
            make_run("r1", start_time=now - timedelta(hours=1)),
            make_run("r2", start_time=now - timedelta(days=30)),
        ]
        result = serialize_stats(runs, days=7)

        assert result["total_runs"] == 1

    def test_empty(self) -> None:
        result = serialize_stats([], days=7)
        assert result["total_runs"] == 0
        assert result["duration_stats"] is None


class TestSerializeTimeline:
    def test_step_start_end_pairs(self) -> None:
        events = [
            StoredEvent(
                seq=1,
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                event_type=EventType.STEP_START,
                step_name="step_a",
                data="{}",
            ),
            StoredEvent(
                seq=2,
                timestamp=datetime(2025, 1, 1, 12, 0, 1),
                event_type=EventType.STEP_END,
                step_name="step_a",
                data="{}",
            ),
        ]
        result = serialize_timeline(events)

        assert len(result) == 1
        assert result[0]["step_name"] == "step_a"
        assert result[0]["duration_seconds"] == 1.0
        assert result[0]["status"] == "success"

    def test_step_error(self) -> None:
        events = [
            StoredEvent(
                seq=1,
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                event_type=EventType.STEP_START,
                step_name="step_b",
                data="{}",
            ),
            StoredEvent(
                seq=2,
                timestamp=datetime(2025, 1, 1, 12, 0, 2),
                event_type=EventType.STEP_ERROR,
                step_name="step_b",
                data="{}",
            ),
        ]
        result = serialize_timeline(events)

        assert len(result) == 1
        assert result[0]["status"] == "error"
        assert result[0]["duration_seconds"] == 2.0

    def test_empty(self) -> None:
        assert serialize_timeline([]) == []
