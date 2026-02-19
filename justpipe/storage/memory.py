"""In-memory storage backend for testing."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from justpipe.storage.interface import RunRecord, StoredEvent
from justpipe.types import EventType, PipelineTerminalStatus


class InMemoryBackend:
    """In-memory storage backend matching the StorageBackend protocol.

    All data is stored in memory and lost when the process exits.
    Useful for tests and temporary debugging.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._events: dict[str, list[str]] = {}  # run_id -> serialized JSON

    def save_run(self, run: RunRecord, events: list[str]) -> None:
        self._runs[run.run_id] = run
        if events:
            existing = self._events.get(run.run_id, [])
            existing.extend(events)
            self._events[run.run_id] = existing
        # If events is empty, keep any previously appended events

    def append_events(self, run_id: str, events: list[str]) -> None:
        existing = self._events.setdefault(run_id, [])
        existing.extend(events)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def list_runs(
        self,
        status: PipelineTerminalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        runs = list(self._runs.values())
        if status is not None:
            runs = [r for r in runs if r.status == status]
        runs.sort(key=lambda r: r.start_time, reverse=True)
        return runs[offset : offset + limit]

    def get_events(
        self,
        run_id: str,
        event_type: EventType | None = None,
    ) -> list[StoredEvent]:
        raw = self._events.get(run_id, [])
        result: list[StoredEvent] = []
        for seq, data_str in enumerate(raw, start=1):
            parsed = json.loads(data_str)
            et = parsed.get("type", "")
            try:
                event_type_val = EventType(et)
            except ValueError:
                continue
            if event_type is not None and event_type_val != event_type:
                continue
            result.append(
                StoredEvent(
                    seq=seq,
                    timestamp=datetime.fromtimestamp(
                        parsed.get("timestamp", 0), tz=timezone.utc
                    ),
                    event_type=event_type_val,
                    step_name=parsed.get("stage", ""),
                    data=data_str,
                )
            )
        return result

    def find_runs_by_prefix(
        self, run_id_prefix: str, limit: int = 10
    ) -> list[RunRecord]:
        matches = [r for r in self._runs.values() if r.run_id.startswith(run_id_prefix)]
        matches.sort(key=lambda r: r.start_time, reverse=True)
        return matches[:limit]

    def delete_run(self, run_id: str) -> bool:
        if run_id not in self._runs:
            return False
        del self._runs[run_id]
        self._events.pop(run_id, None)
        return True
