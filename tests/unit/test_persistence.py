"""Unit tests for _AutoPersistenceObserver and _serialize_event."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from justpipe._internal.runtime.persistence import (
    _AutoPersistenceObserver,
    _serialize_event,
)
from justpipe.observability import ObserverMeta
from justpipe.storage.memory import InMemoryBackend
from justpipe.types import Event, EventType, NodeKind, PipelineTerminalStatus


# ---------------------------------------------------------------------------
# _serialize_event
# ---------------------------------------------------------------------------


class TestSerializeEvent:
    def test_basic_event(self) -> None:
        event = Event(
            type=EventType.STEP_START,
            stage="step_a",
            timestamp=1704110400.0,
            run_id="r1",
            node_kind=NodeKind.STEP,
            attempt=1,
            scope=("root",),
        )
        raw = _serialize_event(event)
        data = json.loads(raw)
        assert data["type"] == "step_start"
        assert data["stage"] == "step_a"
        assert data["node_kind"] == "step"
        assert data["timestamp"] == 1704110400.0
        assert data["attempt"] == 1
        assert data["scope"] == ["root"]  # tuple → list

    def test_enum_serialization(self) -> None:
        event = Event(
            type=EventType.MAP_START,
            stage="map_step",
            node_kind=NodeKind.MAP,
            attempt=2,
            scope=(),
        )
        data = json.loads(_serialize_event(event))
        assert data["type"] == "map_start"
        assert data["node_kind"] == "map"

    def test_payload_dict(self) -> None:
        event = Event(
            type=EventType.FINISH,
            stage="system",
            payload={"status": "success", "duration_s": 1.5},
            node_kind=NodeKind.SYSTEM,
            attempt=1,
            scope=(),
        )
        data = json.loads(_serialize_event(event))
        assert data["payload"]["status"] == "success"
        assert data["payload"]["duration_s"] == 1.5

    def test_payload_none(self) -> None:
        event = Event(
            type=EventType.STEP_START,
            stage="step_a",
            payload=None,
            node_kind=NodeKind.STEP,
            attempt=1,
            scope=(),
        )
        data = json.loads(_serialize_event(event))
        assert data["payload"] is None

    def test_payload_with_enum_values(self) -> None:
        event = Event(
            type=EventType.FINISH,
            stage="system",
            payload={
                "status": PipelineTerminalStatus.FAILED,
                "error": "boom",
            },
            node_kind=NodeKind.SYSTEM,
            attempt=1,
            scope=(),
        )
        data = json.loads(_serialize_event(event))
        assert data["payload"]["status"] == "failed"

    def test_non_serializable_payload_fallback(self) -> None:
        """Non-JSON-serializable payloads fall back to str()."""

        class Custom:
            def __str__(self) -> str:
                return "custom_repr"

        event = Event(
            type=EventType.STEP_END,
            stage="step_a",
            payload={"obj": Custom()},
            node_kind=NodeKind.STEP,
            attempt=1,
            scope=(),
        )
        data = json.loads(_serialize_event(event))
        assert "custom_repr" in str(data["payload"])

    def test_all_event_types(self) -> None:
        """Every EventType value produces valid JSON."""
        for et in EventType:
            event = Event(
                type=et,
                stage="test",
                node_kind=NodeKind.SYSTEM,
                attempt=1,
                scope=(),
            )
            raw = _serialize_event(event)
            data = json.loads(raw)
            assert data["type"] == et.value


# ---------------------------------------------------------------------------
# _AutoPersistenceObserver
# ---------------------------------------------------------------------------


def _make_meta(run_id: str = "test-run-123") -> ObserverMeta:
    return ObserverMeta(run_id=run_id, pipe_name="test_pipe")


def _make_event(
    event_type: EventType = EventType.STEP_START,
    stage: str = "step_a",
    **kwargs: Any,
) -> Event:
    return Event(
        type=event_type,
        stage=stage,
        node_kind=kwargs.pop("node_kind", NodeKind.STEP),
        attempt=kwargs.pop("attempt", 1),
        scope=kwargs.pop("scope", ()),
        **kwargs,
    )


class TestAutoPersistenceObserver:
    def _make_observer(
        self, backend: InMemoryBackend | None = None
    ) -> tuple[_AutoPersistenceObserver, InMemoryBackend]:
        backend = backend or InMemoryBackend()
        obs = _AutoPersistenceObserver(
            backend=backend,
            pipeline_hash="abc123",
            describe_snapshot={"name": "test_pipe"},
        )
        return obs, backend

    @pytest.mark.asyncio
    async def test_buffers_events_and_flushes_on_end(self) -> None:
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_event(None, None, meta, _make_event())
        await obs.on_event(None, None, meta, _make_event(stage="step_b"))

        # Not flushed yet
        assert backend.get_run("test-run-123") is None

        await obs.on_pipeline_end(None, None, meta, 1.5)

        # Now flushed
        run = backend.get_run("test-run-123")
        assert run is not None
        assert run.status == PipelineTerminalStatus.SUCCESS
        events = backend.get_events("test-run-123")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_flush_on_error(self) -> None:
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_event(None, None, meta, _make_event())
        await obs.on_pipeline_error(None, None, meta, RuntimeError("boom"))

        run = backend.get_run("test-run-123")
        assert run is not None
        assert run.status == PipelineTerminalStatus.FAILED
        assert run.error_message == "boom"

    @pytest.mark.asyncio
    async def test_extracts_status_from_finish_event(self) -> None:
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)

        finish_event = _make_event(
            event_type=EventType.FINISH,
            stage="system",
            node_kind=NodeKind.SYSTEM,
            payload={
                "status": "failed",
                "error": "step exploded",
                "failed_step": "step_a",
                "duration_s": 2.5,
            },
        )
        await obs.on_event(None, None, meta, finish_event)
        await obs.on_pipeline_end(None, None, meta, 2.5)

        run = backend.get_run("test-run-123")
        assert run is not None
        assert run.status == PipelineTerminalStatus.FAILED
        assert run.error_message == "step exploded"
        assert run.error_step == "step_a"

    @pytest.mark.asyncio
    async def test_extracts_user_meta_from_finish(self) -> None:
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)

        finish_event = _make_event(
            event_type=EventType.FINISH,
            stage="system",
            node_kind=NodeKind.SYSTEM,
            payload={
                "status": "success",
                "duration_s": 1.0,
                "user_meta": {"run": {"tags": ["prod"]}},
            },
        )
        await obs.on_event(None, None, meta, finish_event)
        await obs.on_pipeline_end(None, None, meta, 1.0)

        run = backend.get_run("test-run-123")
        assert run is not None
        assert run.user_meta is not None
        parsed = json.loads(run.user_meta)
        assert parsed["run"]["tags"] == ["prod"]

    @pytest.mark.asyncio
    async def test_clears_buffer_after_flush(self) -> None:
        obs, backend = self._make_observer()

        # First run
        meta1 = _make_meta("run-1")
        await obs.on_pipeline_start(None, None, meta1)
        await obs.on_event(None, None, meta1, _make_event())
        await obs.on_event(None, None, meta1, _make_event())
        await obs.on_event(None, None, meta1, _make_event())
        await obs.on_pipeline_end(None, None, meta1, 1.0)

        # Second run
        meta2 = _make_meta("run-2")
        await obs.on_pipeline_start(None, None, meta2)
        await obs.on_event(None, None, meta2, _make_event())
        await obs.on_pipeline_end(None, None, meta2, 0.5)

        # Second run should only have 1 event, not 4
        events = backend.get_events("run-2")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_persistence_failure_does_not_raise(self) -> None:
        """Pipeline execution NEVER fails due to persistence errors."""
        broken_backend = MagicMock()
        broken_backend.save_run.side_effect = OSError("disk full")

        obs = _AutoPersistenceObserver(
            backend=broken_backend,
            pipeline_hash="abc123",
            describe_snapshot={},
        )
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_event(None, None, meta, _make_event())
        # Should not raise
        await obs.on_pipeline_end(None, None, meta, 1.0)

    @pytest.mark.asyncio
    async def test_no_flush_without_start(self) -> None:
        """Flush is a no-op if on_pipeline_start was never called."""
        obs, backend = self._make_observer()
        meta = _make_meta()

        # Call end without start — run_id is None
        await obs.on_pipeline_end(None, None, meta, 1.0)

        assert backend.get_run("test-run-123") is None

    @pytest.mark.asyncio
    async def test_run_record_has_timestamps(self) -> None:
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_pipeline_end(None, None, meta, 1.0)

        run = backend.get_run("test-run-123")
        assert run is not None
        assert isinstance(run.start_time, datetime)
        assert isinstance(run.end_time, datetime)
        assert isinstance(run.duration, timedelta)
        assert run.duration.total_seconds() >= 0

    @pytest.mark.asyncio
    async def test_backend_save_error_suppressed_on_end(self) -> None:
        """Backend raising on save_run is suppressed during on_pipeline_end."""
        broken = MagicMock()
        broken.save_run.side_effect = RuntimeError("connection lost")

        obs = _AutoPersistenceObserver(
            backend=broken,
            pipeline_hash="abc123",
            describe_snapshot={},
        )
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_event(None, None, meta, _make_event())
        # Must not propagate
        await obs.on_pipeline_end(None, None, meta, 1.0)

        # Buffer should be cleared despite the error
        assert obs._events == []
        assert obs._run_id is None

    @pytest.mark.asyncio
    async def test_backend_save_error_suppressed_on_error(self) -> None:
        """Backend raising on save_run is suppressed during on_pipeline_error."""
        broken = MagicMock()
        broken.save_run.side_effect = PermissionError("read-only fs")

        obs = _AutoPersistenceObserver(
            backend=broken,
            pipeline_hash="abc123",
            describe_snapshot={},
        )
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)
        await obs.on_event(None, None, meta, _make_event())
        # Must not propagate
        await obs.on_pipeline_error(None, None, meta, ValueError("step boom"))

        # Buffer should be cleared despite the error
        assert obs._events == []
        assert obs._run_id is None

    @pytest.mark.asyncio
    async def test_serialize_event_error_suppressed(self) -> None:
        """Serialization failure for a single event logs warning, does not crash."""
        obs, backend = self._make_observer()
        meta = _make_meta()

        await obs.on_pipeline_start(None, None, meta)

        # Good event followed by an event with a payload that breaks json.dumps
        await obs.on_event(None, None, meta, _make_event())

        class Unserializable:
            def __str__(self) -> str:
                raise RuntimeError("cannot serialize")

            def __repr__(self) -> str:
                raise RuntimeError("cannot repr")

        bad_event = _make_event(stage="bad_step", payload=Unserializable())
        # Should not raise
        await obs.on_event(None, None, meta, bad_event)

        await obs.on_pipeline_end(None, None, meta, 1.0)

        # First event was saved; bad event may or may not be depending on fallback
        run = backend.get_run("test-run-123")
        assert run is not None
