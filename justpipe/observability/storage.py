"""Storage observer for persisting pipeline runs and events."""

import json
import time
from typing import Any

from justpipe.observability import Observer, ObserverMeta
from justpipe.storage.interface import StorageBackend
from justpipe.types import Event


class StorageObserver(Observer):
    """Observer that persists pipeline runs and events to a storage backend.

    Automatically saves:
    - Run metadata (pipeline name, start/end times, status)
    - All events during execution
    - Initial state as an artifact
    - Error messages on failure

    Example:
        from justpipe.storage import SQLiteStorage
        from justpipe.observability import StorageObserver

        storage = SQLiteStorage("~/.justpipe")
        pipe = Pipe()
        pipe.add_observer(StorageObserver(storage))

        async for event in pipe.run(state):
            pass

        # Later, query runs:
        runs = await storage.list_runs(status="success")
    """

    def __init__(
        self,
        storage: StorageBackend,
        save_initial_state: bool = True,
        pipeline_name: str | None = None,
    ):
        """Initialize StorageObserver.

        Args:
            storage: Storage backend to use
            save_initial_state: Whether to save initial state as artifact
            pipeline_name: Override pipeline name (default: use context)
        """
        self.storage = storage
        self.save_initial_state = save_initial_state
        self.pipeline_name_override = pipeline_name

        self.run_id: str | None = None
        self.start_time: float | None = None

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Create run and save initial state."""
        _ = context
        # Determine pipeline name
        pipeline_name = self.pipeline_name_override or meta.pipe_name
        if pipeline_name is None:
            pipeline_name = "unknown"

        # Create run
        self.run_id = await self.storage.create_run(
            pipeline_name=pipeline_name,
            metadata={},
        )
        self.start_time = time.time()

        # Save initial state as artifact
        if self.save_initial_state:
            try:
                state_json = json.dumps(state, default=str, indent=2)
                await self.storage.save_artifact(
                    self.run_id,
                    "initial_state.json",
                    state_json.encode("utf-8"),
                )
            except Exception as e:
                # Don't fail pipeline if state serialization fails
                import logging

                logging.warning(f"Failed to save initial state: {e}")

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Save event to storage."""
        _ = (state, context, meta)
        if self.run_id is None:
            return

        try:
            await self.storage.add_event(self.run_id, event)
        except Exception as e:
            # Don't fail pipeline if storage fails
            import logging

            logging.error(f"Failed to save event: {e}")

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Update run with success status."""
        _ = (state, context, meta)
        if self.run_id is None:
            return

        try:
            await self.storage.update_run(
                self.run_id,
                status="success",
                end_time=time.time(),
                duration=duration_s,
            )
        except Exception as e:
            import logging

            logging.error(f"Failed to update run: {e}")

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        """Update run with error status."""
        _ = (state, context, meta)
        if self.run_id is None:
            return

        try:
            await self.storage.update_run(
                self.run_id,
                status="error",
                end_time=time.time(),
                duration=time.time() - (self.start_time or time.time()),
                error_message=str(error),
            )
        except Exception as e:
            import logging

            logging.error(f"Failed to update run with error: {e}")

    def get_run_id(self) -> str | None:
        """Get the current run ID.

        Returns:
            Run ID if pipeline has started, None otherwise
        """
        return self.run_id
