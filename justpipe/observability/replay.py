"""Replay observer for re-running pipelines from stored state."""

from typing import Any, TYPE_CHECKING
from justpipe.observability import Observer, ObserverMeta
from justpipe.storage.interface import StorageBackend
from justpipe.types import Event

if TYPE_CHECKING:
    from justpipe.storage.interface import StoredRun


class ReplayObserver(Observer):
    """Observer that loads initial state from a previous run.

    This observer does not mutate the running pipeline state automatically.
    It fetches the saved initial state so callers can decide how to replay.

    This enables:
    - Bug reproduction with exact same inputs
    - Testing changes with historical data
    - Comparing different pipeline versions

    Usage:
        storage = SQLiteStorage("~/.justpipe")
        replay = ReplayObserver(storage, source_run_id="abc123")

        pipe.add_observer(replay)
        await pipe.run(state)  # then inspect replay.get_initial_state()
    """

    def __init__(
        self,
        storage: StorageBackend,
        source_run_id: str,
    ):
        """Initialize replay observer.

        Args:
            storage: Storage backend to load state from
            source_run_id: Run ID to replay from
        """
        self.storage = storage
        self.source_run_id = source_run_id
        self.initial_state: Any | None = None
        self.source_run: "StoredRun" | None = None

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Load initial state from source run."""
        _ = (state, context, meta)
        import json

        # Get source run metadata
        self.source_run = await self.storage.get_run(self.source_run_id)

        if self.source_run is None:
            raise ValueError(f"Source run not found: {self.source_run_id}")

        # Load initial state artifact (saved as "initial_state.json")
        artifact_data = await self.storage.load_artifact(
            self.source_run_id, "initial_state.json"
        )

        if artifact_data is None:
            raise ValueError(
                f"Initial state not found for run: {self.source_run_id}. "
                "Make sure the original run was saved with StorageObserver."
            )

        # Decode JSON bytes to Python object
        self.initial_state = json.loads(artifact_data.decode("utf-8"))

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Track replay events."""
        _ = (state, context, meta, event)
        pass

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Record replay completion."""
        _ = (state, context, meta, duration_s)
        pass

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        """Record replay errors."""
        _ = (state, context, meta, error)
        pass

    def get_initial_state(self) -> Any:
        """Get the loaded initial state for replay.

        Returns:
            The initial state from the source run

        Raises:
            RuntimeError: If called before pipeline start
        """
        if self.initial_state is None:
            raise RuntimeError(
                "Initial state not loaded. Make sure pipeline has started."
            )
        return self.initial_state
