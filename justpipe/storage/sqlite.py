"""SQLite storage backend for local pipeline observability."""

import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import aiosqlite
except ImportError:
    raise ImportError(
        "aiosqlite is required for SQLite storage. "
        "Install it with: pip install justpipe[observability]"
    )

from justpipe.storage.interface import StorageBackend, StoredEvent, StoredRun
from justpipe.types import Event, EventType


class SQLiteStorage(StorageBackend):
    """SQLite-based storage backend for local development and debugging.

    Stores runs and events in a SQLite database, with artifacts saved as
    separate files. Suitable for single-machine deployments.

    Storage structure:
        ~/.justpipe/
        ├── runs.db (SQLite database)
        └── artifacts/
            ├── <run_id>/
            │   ├── initial_state.json
            │   └── ...
            └── ...

    Example:
        storage = SQLiteStorage("~/.justpipe")

        # Create run
        run_id = await storage.create_run("my_pipeline")

        # Add events
        await storage.add_event(run_id, event)

        # Query runs
        runs = await storage.list_runs(status="success")
    """

    def __init__(self, storage_dir: str = "~/.justpipe"):
        """Initialize SQLite storage.

        Args:
            storage_dir: Directory for database and artifacts
        """
        self.storage_dir = Path(storage_dir).expanduser()
        self.db_path = self.storage_dir / "runs.db"
        self.artifacts_dir = self.storage_dir / "artifacts"

        # Create directories
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database (synchronous, only done once)
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        self._init_db_sync(conn)
        conn.close()

    def _init_db_sync(self, conn: Any) -> None:
        """Initialize database schema (synchronous, called once at startup)."""
        conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL for better concurrency
        conn.execute("PRAGMA foreign_keys=ON")

        # Create runs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                duration REAL,
                status TEXT DEFAULT 'running',
                error_message TEXT,
                metadata TEXT,
                created_at REAL DEFAULT (julianday('now'))
            )
        """
        )

        # Create indexes
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_runs_pipeline
            ON runs(pipeline_name, start_time DESC)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_runs_status
            ON runs(status, start_time DESC)
        """
        )

        # Create events table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                step_name TEXT,
                payload TEXT,
                metadata TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
            )
        """
        )

        # Create event indexes
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_run_id
            ON events(run_id, timestamp)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(run_id, event_type)
        """
        )

        conn.commit()

    @asynccontextmanager
    async def _connect(self) -> Any:
        """Create a connection with foreign key constraints enabled."""
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            await conn.close()

    def _serialize_data(self, data: Any) -> str:
        """Serialize data to JSON string."""
        try:
            return json.dumps(data, default=str)
        except Exception:
            return json.dumps(str(data))

    def _deserialize_data(self, data_str: str | None) -> Any:
        """Deserialize JSON string to data."""
        if data_str is None:
            return None
        try:
            return json.loads(data_str)
        except Exception:
            return data_str

    async def create_run(
        self,
        pipeline_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new pipeline run."""
        run_id = uuid.uuid4().hex
        start_time = time.time()

        async with self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO runs (id, pipeline_name, start_time, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    pipeline_name,
                    start_time,
                    self._serialize_data(metadata or {}),
                ),
            )
            await conn.commit()

        # Create artifacts directory for this run
        run_artifacts_dir = self.artifacts_dir / run_id
        run_artifacts_dir.mkdir(parents=True, exist_ok=True)

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
        updates = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if end_time is not None:
            updates.append("end_time = ?")
            params.append(end_time)

        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if not updates:
            return

        params.append(run_id)
        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"

        async with self._connect() as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def add_event(
        self,
        run_id: str,
        event: Event,
    ) -> None:
        """Add an event to a run."""
        async with self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO events (run_id, timestamp, event_type, step_name, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event.timestamp,
                    event.type.value,
                    event.stage,
                    self._serialize_data(event.payload),
                ),
            )
            await conn.commit()

    async def get_run(self, run_id: str) -> StoredRun | None:
        """Get a run by ID."""
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """
                SELECT id, pipeline_name, start_time, end_time, duration,
                       status, error_message, metadata
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ) as cursor:
                row = await cursor.fetchone()

                if row is None:
                    return None

                return StoredRun(
                    id=row["id"],
                    pipeline_name=row["pipeline_name"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    duration=row["duration"],
                    status=row["status"],
                    error_message=row["error_message"],
                    metadata=self._deserialize_data(row["metadata"]),
                )

    async def list_runs(
        self,
        pipeline_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredRun]:
        """list runs with optional filtering."""
        conditions = []
        params: list[Any] = []

        if pipeline_name is not None:
            conditions.append("pipeline_name = ?")
            params.append(pipeline_name)

        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, pipeline_name, start_time, end_time, duration,
                   status, error_message, metadata
            FROM runs
            {where_clause}
            ORDER BY start_time DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()

                return [
                    StoredRun(
                        id=row["id"],
                        pipeline_name=row["pipeline_name"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration=row["duration"],
                        status=row["status"],
                        error_message=row["error_message"],
                        metadata=self._deserialize_data(row["metadata"]),
                    )
                    for row in rows
                ]

    async def get_events(
        self,
        run_id: str,
        event_types: list[EventType] | None = None,
    ) -> list[StoredEvent]:
        """Get events for a run."""
        query = """
            SELECT id, run_id, timestamp, event_type, step_name, payload, metadata
            FROM events
            WHERE run_id = ?
        """
        params: list[Any] = [run_id]

        if event_types is not None:
            placeholders = ", ".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend([et.value for et in event_types])

        query += " ORDER BY timestamp ASC"

        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()

                return [
                    StoredEvent(
                        id=row["id"],
                        run_id=row["run_id"],
                        timestamp=row["timestamp"],
                        event_type=row["event_type"],
                        step_name=row["step_name"],
                        payload=self._deserialize_data(row["payload"]),
                        metadata=self._deserialize_data(row["metadata"]),
                    )
                    for row in rows
                ]

    async def delete_run(self, run_id: str) -> bool:
        """Delete a run and its events."""
        async with self._connect() as conn:
            cursor = await conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            deleted = bool(cursor.rowcount > 0)
            await conn.commit()

            # Delete artifacts
            if deleted:
                run_artifacts_dir = self.artifacts_dir / run_id
                if run_artifacts_dir.exists():
                    import shutil

                    shutil.rmtree(run_artifacts_dir)

            return deleted

    async def save_artifact(
        self,
        run_id: str,
        name: str,
        data: bytes,
    ) -> str:
        """Save a binary artifact."""
        run_artifacts_dir = self.artifacts_dir / run_id
        run_artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = run_artifacts_dir / name

        # Write file
        with open(artifact_path, "wb") as f:
            f.write(data)

        return str(artifact_path)

    async def load_artifact(
        self,
        run_id: str,
        name: str,
    ) -> bytes | None:
        """Load a binary artifact."""
        artifact_path = self.artifacts_dir / run_id / name

        if not artifact_path.exists():
            return None

        with open(artifact_path, "rb") as f:
            return f.read()
