"""In-memory storage backend for testing."""

import time
import uuid
from typing import Any

from justpipe.storage.interface import StorageBackend, StoredEvent, StoredRun
from justpipe.types import Event, EventType


class InMemoryStorage(StorageBackend):
    """In-memory storage backend for testing and development.

    All data is stored in memory and lost when the process exits.
    Useful for tests and temporary debugging.

    Example:
        storage = InMemoryStorage()

        # Use same API as SQLiteStorage
        run_id = await storage.create_run("test_pipeline")
        await storage.add_event(run_id, event)
        runs = await storage.list_runs()
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self.runs: dict[str, StoredRun] = {}
        self.events: dict[str, list[StoredEvent]] = {}  # run_id -> events
        self.artifacts: dict[str, dict[str, bytes]] = {}  # run_id -> name -> data
        self._event_counter = 0

    async def create_run(
        self,
        pipeline_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new pipeline run."""
        run_id = uuid.uuid4().hex
        start_time = time.time()

        self.runs[run_id] = StoredRun(
            id=run_id,
            pipeline_name=pipeline_name,
            start_time=start_time,
            metadata=metadata or {},
        )

        self.events[run_id] = []
        self.artifacts[run_id] = {}

        return run_id

    async def update_run(
        self,
        run_id: str,
        status: str | None = None,
        end_time: float | None = None,
        duration: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update an existing run."""
        if run_id not in self.runs:
            return

        run = self.runs[run_id]

        if status is not None:
            run.status = status

        if end_time is not None:
            run.end_time = end_time

        if duration is not None:
            run.duration = duration

        if error_message is not None:
            run.error_message = error_message

    async def add_event(
        self,
        run_id: str,
        event: Event,
    ) -> None:
        """Add an event to a run."""
        if run_id not in self.events:
            self.events[run_id] = []

        self._event_counter += 1

        stored_event = StoredEvent(
            id=self._event_counter,
            run_id=run_id,
            timestamp=event.timestamp,
            event_type=event.type.value,
            step_name=event.stage,
            payload=event.payload,
        )

        self.events[run_id].append(stored_event)

    async def get_run(self, run_id: str) -> StoredRun | None:
        """Get a run by ID."""
        return self.runs.get(run_id)

    async def list_runs(
        self,
        pipeline_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredRun]:
        """list runs with optional filtering."""
        # Filter runs
        filtered = list(self.runs.values())

        if pipeline_name is not None:
            filtered = [r for r in filtered if r.pipeline_name == pipeline_name]

        if status is not None:
            filtered = [r for r in filtered if r.status == status]

        # Sort by start time (descending)
        filtered.sort(key=lambda r: r.start_time, reverse=True)

        # Apply pagination
        return filtered[offset : offset + limit]

    async def get_events(
        self,
        run_id: str,
        event_types: list[EventType] | None = None,
    ) -> list[StoredEvent]:
        """Get events for a run."""
        if run_id not in self.events:
            return []

        events = self.events[run_id]

        if event_types is not None:
            type_values = {et.value for et in event_types}
            events = [e for e in events if e.event_type in type_values]

        return events

    async def delete_run(self, run_id: str) -> bool:
        """Delete a run and its events."""
        if run_id not in self.runs:
            return False

        del self.runs[run_id]

        if run_id in self.events:
            del self.events[run_id]

        if run_id in self.artifacts:
            del self.artifacts[run_id]

        return True

    async def save_artifact(
        self,
        run_id: str,
        name: str,
        data: bytes,
    ) -> str:
        """Save a binary artifact."""
        if run_id not in self.artifacts:
            self.artifacts[run_id] = {}

        self.artifacts[run_id][name] = data
        return f"memory://{run_id}/{name}"

    async def load_artifact(
        self,
        run_id: str,
        name: str,
    ) -> bytes | None:
        """Load a binary artifact."""
        if run_id not in self.artifacts:
            return None

        return self.artifacts[run_id].get(name)
