"""Storage backend interface for pipeline observability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from justpipe.types import EventType, PipelineTerminalStatus


@dataclass(frozen=True)
class RunRecord:
    """Stored run summary."""

    run_id: str
    start_time: datetime
    end_time: datetime | None
    duration: timedelta | None
    status: PipelineTerminalStatus
    error_message: str | None = None
    error_step: str | None = None
    user_meta: str | None = None  # JSON string or None


@dataclass(frozen=True)
class StoredEvent:
    """Stored pipeline event with extracted fields for efficient querying."""

    seq: int
    timestamp: datetime
    event_type: EventType
    step_name: str
    data: str  # full Event JSON blob (source of truth)


class StorageBackend(Protocol):
    """Synchronous storage contract — one instance per pipeline.

    Async wrapping (``asyncio.to_thread``) is the observer's responsibility.
    """

    def save_run(self, run: RunRecord, events: list[str]) -> None:
        """Atomically persist a complete run with all its events.

        Called once at pipeline FINISH (batch+flush). The *events* list
        contains pre-serialized JSON strings.
        """
        ...

    def get_run(self, run_id: str) -> RunRecord | None:
        """Retrieve a single run by ID."""
        ...

    def list_runs(
        self,
        status: PipelineTerminalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        """List runs ordered by start_time DESC with optional status filter."""
        ...

    def get_events(
        self,
        run_id: str,
        event_type: EventType | None = None,
    ) -> list[StoredEvent]:
        """Get events for a run, ordered by seq ASC."""
        ...

    def find_runs_by_prefix(
        self, run_id_prefix: str, limit: int = 10
    ) -> list[RunRecord]:
        """Find runs whose ID starts with the given prefix."""
        ...

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its events. Returns True if found."""
        ...
