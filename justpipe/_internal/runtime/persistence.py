"""Auto-persistence observer — buffers events, flushes to StorageBackend at FINISH."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from justpipe._internal.shared.utils import resolve_storage_path
from justpipe.observability import Observer, ObserverMeta
from justpipe.storage.interface import RunRecord, StorageBackend
from justpipe.types import Event, EventType, PipelineTerminalStatus

logger = logging.getLogger("justpipe.persistence")


def _serialize_event(event: Event) -> str:
    """Serialize an Event to a JSON string for storage.

    Conversion rules:
    - Enums → .value strings
    - tuple → list
    - Non-serializable payloads → str() fallback
    """

    def _default(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        return str(obj)

    data: dict[str, Any] = {
        "type": event.type.value,
        "stage": event.stage,
        "timestamp": event.timestamp,
        "run_id": event.run_id,
        "origin_run_id": event.origin_run_id,
        "parent_run_id": event.parent_run_id,
        "seq": event.seq,
        "node_kind": event.node_kind.value,
        "invocation_id": event.invocation_id,
        "parent_invocation_id": event.parent_invocation_id,
        "owner_invocation_id": event.owner_invocation_id,
        "attempt": event.attempt,
        "scope": list(event.scope),
        "meta": event.meta,
    }

    # Serialize payload separately with fallback
    if event.payload is None:
        data["payload"] = None
    else:
        try:
            data["payload"] = json.loads(json.dumps(event.payload, default=_default))
        except (TypeError, ValueError):
            data["payload"] = str(event.payload)

    return json.dumps(data, default=_default)


class _AutoPersistenceObserver(Observer):
    """Observer that buffers events in memory and flushes to a StorageBackend at FINISH.

    When *flush_interval* is set, events are flushed incrementally via
    ``backend.append_events()`` every *flush_interval* events to bound
    memory usage for long-running pipelines.

    Pipeline execution NEVER fails due to persistence errors.
    """

    def __init__(
        self,
        backend: StorageBackend,
        pipeline_hash: str,
        describe_snapshot: dict[str, Any],
        flush_interval: int | None = None,
    ) -> None:
        self._backend = backend
        self._pipeline_hash = pipeline_hash
        self._describe_snapshot = describe_snapshot
        self._flush_interval = flush_interval

        # Per-run state
        self._events: list[str] = []
        self._flushed_count: int = 0
        self._run_id: str | None = None
        self._start_time: float = 0

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        self._events = []
        self._flushed_count = 0
        self._run_id = meta.run_id
        self._start_time = time.time()

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        try:
            self._events.append(_serialize_event(event))
        except Exception as exc:
            logger.warning("Failed to serialize event: %s", exc)
            return

        if (
            self._flush_interval
            and self._run_id
            and len(self._events) >= self._flush_interval
        ):
            await self._flush_intermediate()

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        await self._flush(duration_s=duration_s)

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        await self._flush(error=error)

    async def _flush_intermediate(self) -> None:
        """Flush buffered events incrementally without finalizing the run."""
        if not self._run_id or not self._events:
            return
        try:
            batch = list(self._events)
            await asyncio.to_thread(
                self._backend.append_events, self._run_id, batch
            )
            self._flushed_count += len(batch)
            self._events.clear()
        except Exception as exc:
            logger.warning(
                "Intermediate flush failed for run %s: %s", self._run_id, exc
            )

    async def _flush(
        self,
        duration_s: float | None = None,
        error: Exception | None = None,
    ) -> None:
        """Flush buffered events + run summary to the backend."""
        if self._run_id is None:
            return

        try:
            # Extract terminal info from FINISH event if present
            status = PipelineTerminalStatus.SUCCESS
            error_message: str | None = None
            error_step: str | None = None
            run_meta: str | None = None
            end_time = time.time()
            actual_duration = duration_s or (end_time - self._start_time)

            # The FINISH event is always the last event in the buffer.
            if self._events:
                parsed = json.loads(self._events[-1])
                if parsed.get("type") == EventType.FINISH.value and isinstance(
                    parsed.get("payload"), dict
                ):
                    payload = parsed["payload"]
                    status_val = payload.get("status")
                    if status_val:
                        try:
                            status = PipelineTerminalStatus(status_val)
                        except ValueError:
                            pass
                    error_message = payload.get("error")
                    error_step = payload.get("failed_step")
                    raw_meta = parsed.get("meta")
                    if raw_meta:
                        run_meta = json.dumps(raw_meta)
                    dur = payload.get("duration_s")
                    if dur is not None:
                        actual_duration = dur

            if error and status == PipelineTerminalStatus.SUCCESS:
                status = PipelineTerminalStatus.FAILED
                error_message = str(error)

            run = RunRecord(
                run_id=self._run_id,
                start_time=datetime.fromtimestamp(self._start_time),
                end_time=datetime.fromtimestamp(end_time),
                duration=timedelta(seconds=actual_duration),
                status=status,
                error_message=error_message,
                error_step=error_step,
                run_meta=run_meta,
            )

            if self._flushed_count > 0:
                # Some events were already flushed incrementally via
                # append_events. Flush remaining, then save_run with
                # an empty list (all events already in DB).
                if self._events:
                    await asyncio.to_thread(
                        self._backend.append_events,
                        self._run_id,
                        self._events,
                    )
                await asyncio.to_thread(self._backend.save_run, run, [])
            else:
                await asyncio.to_thread(
                    self._backend.save_run, run, self._events
                )

            # Write pipeline.json alongside the DB
            self._write_pipeline_json()

        except Exception as exc:
            logger.warning(
                "Failed to persist run %s (%d events lost): %s",
                self._run_id,
                len(self._events) + self._flushed_count,
                exc,
            )
        finally:
            self._events = []
            self._flushed_count = 0
            self._run_id = None

    def _write_pipeline_json(self) -> None:
        """Write pipeline descriptor alongside the storage."""
        pipeline_json: Path | None = None
        try:
            storage_dir = resolve_storage_path() / self._pipeline_hash
            storage_dir.mkdir(parents=True, exist_ok=True)
            pipeline_json = storage_dir / "pipeline.json"
            if not pipeline_json.exists():
                pipeline_json.write_text(json.dumps(self._describe_snapshot, indent=2))
        except Exception as exc:
            logger.warning("Failed to write pipeline.json for %s: %s", pipeline_json or self._pipeline_hash, exc)
