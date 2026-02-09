"""Storage backend interface for pipeline observability."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from justpipe.types import Event, EventType


@dataclass
class StoredRun:
    """Represents a stored pipeline run."""

    id: str
    pipeline_name: str
    start_time: float
    end_time: float | None = None
    duration: float | None = None
    status: str = "running"  # running, success, error, suspended
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredEvent:
    """Represents a stored pipeline event."""

    id: int
    run_id: str
    timestamp: float
    event_type: str  # EventType value
    step_name: str
    payload: Any | None = None
    metadata: dict[str, Any] | None = None


class StorageBackend(ABC):
    """Abstract interface for storing pipeline runs and events.

    Implementations must handle:
    - Concurrent writes from multiple pipelines
    - Efficient querying of runs and events
    - Artifact storage (optional)
    - Cleanup and retention

    Example:
        from justpipe.storage import SQLiteStorage

        storage = SQLiteStorage("~/.justpipe")
        run_id = await storage.create_run("my_pipeline", metadata={})

        # Later
        runs = await storage.list_runs(pipeline_name="my_pipeline", status="success")
    """

    @abstractmethod
    async def create_run(
        self,
        pipeline_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new pipeline run.

        Args:
            pipeline_name: Name of the pipeline
            metadata: Optional metadata about the run

        Returns:
            run_id: Unique identifier for this run
        """
        pass

    @abstractmethod
    async def update_run(
        self,
        run_id: str,
        status: str | None = None,
        end_time: float | None = None,
        duration: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update an existing run.

        Args:
            run_id: Run identifier
            status: New status (running, success, error, suspended)
            end_time: End timestamp
            duration: Total duration in seconds
            error_message: Error message if failed
        """
        pass

    @abstractmethod
    async def add_event(
        self,
        run_id: str,
        event: Event,
    ) -> None:
        """Add an event to a run.

        Args:
            run_id: Run identifier
            event: Event to store
        """
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> StoredRun | None:
        """Get a run by ID.

        Args:
            run_id: Run identifier

        Returns:
            StoredRun if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_runs(
        self,
        pipeline_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredRun]:
        """list runs with optional filtering.

        Args:
            pipeline_name: Filter by pipeline name
            status: Filter by status (running, success, error, suspended)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            list of StoredRun objects
        """
        pass

    @abstractmethod
    async def get_events(
        self,
        run_id: str,
        event_types: list[EventType] | None = None,
    ) -> list[StoredEvent]:
        """Get events for a run.

        Args:
            run_id: Run identifier
            event_types: Optional filter by event types

        Returns:
            list of StoredEvent objects
        """
        pass

    @abstractmethod
    async def delete_run(self, run_id: str) -> bool:
        """Delete a run and its events.

        Args:
            run_id: Run identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def save_artifact(
        self,
        run_id: str,
        name: str,
        data: bytes,
    ) -> str:
        """Save a binary artifact associated with a run.

        Args:
            run_id: Run identifier
            name: Artifact name (e.g., "initial_state.json", "input.pdf")
            data: Binary data to store

        Returns:
            Path or URL to the stored artifact
        """
        pass

    @abstractmethod
    async def load_artifact(
        self,
        run_id: str,
        name: str,
    ) -> bytes | None:
        """Load a binary artifact.

        Args:
            run_id: Run identifier
            name: Artifact name

        Returns:
            Binary data if found, None otherwise
        """
        pass

    async def resolve_run_id(self, prefix: str) -> str | None:
        """Resolve a run ID prefix to full ID (Docker-style).

        Args:
            prefix: Run ID prefix (minimum 4 characters)

        Returns:
            Full run ID if exactly one match found, None otherwise

        Raises:
            ValueError: If prefix matches multiple runs or is too short
        """
        # Validate prefix length
        if len(prefix) < 4:
            raise ValueError("Run ID prefix must be at least 4 characters")

        # If it's already a full ID (32 chars), return it
        if len(prefix) == 32:
            run = await self.get_run(prefix)
            return prefix if run else None

        # list all runs and filter by prefix
        all_runs = await self.list_runs(limit=1000)
        matches = [run for run in all_runs if run.id.startswith(prefix)]

        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0].id
        else:
            # Multiple matches - show user which ones
            match_ids = [m.id[:12] + "..." for m in matches[:5]]
            raise ValueError(
                f"Prefix '{prefix}' matches {len(matches)} runs: {', '.join(match_ids)}"
            )

    async def get_run_by_prefix(self, prefix: str) -> StoredRun | None:
        """Get a run by ID prefix (convenience method).

        Args:
            prefix: Run ID or prefix (minimum 4 characters)

        Returns:
            StoredRun if found, None otherwise

        Raises:
            ValueError: If prefix matches multiple runs or is too short
        """
        run_id = await self.resolve_run_id(prefix)
        if run_id:
            return await self.get_run(run_id)
        return None
