"""SQLite storage backend using stdlib sqlite3 (zero dependencies)."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from justpipe.storage.interface import RunRecord, StoredEvent
from justpipe.types import EventType, PipelineTerminalStatus

_SCHEMA = """\
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    start_time REAL NOT NULL,
    end_time REAL,
    duration_s REAL,
    status TEXT,
    error_message TEXT,
    error_step TEXT,
    run_meta TEXT,
    created_at REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    data TEXT NOT NULL,
    event_type TEXT GENERATED ALWAYS AS (json_extract(data, '$.type')) STORED,
    step_name TEXT GENERATED ALWAYS AS (json_extract(data, '$.stage')) STORED,
    node_kind TEXT GENERATED ALWAYS AS (json_extract(data, '$.node_kind')) STORED,
    attempt INTEGER GENERATED ALWAYS AS (json_extract(data, '$.attempt')) STORED
);

CREATE INDEX IF NOT EXISTS idx_runs_time ON runs(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(run_id, event_type);
CREATE INDEX IF NOT EXISTS idx_events_step ON events(run_id, step_name, event_type);
"""


class SQLiteBackend:
    """SQLite-based storage backend using stdlib sqlite3.

    Each instance is scoped to one pipeline directory.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.executescript(_SCHEMA)
            self._migrate(conn)
        finally:
            conn.close()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Add/rename columns that may be missing from older databases."""
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        # Rename user_meta → run_meta (from earlier schema version)
        if "user_meta" in existing and "run_meta" not in existing:
            conn.execute("ALTER TABLE runs RENAME COLUMN user_meta TO run_meta")
            existing.discard("user_meta")
            existing.add("run_meta")
        # Add columns that may be entirely missing
        for col, typ in [("run_meta", "TEXT"), ("error_step", "TEXT")]:
            if col not in existing:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {typ}")
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_run(self, run: RunRecord, events: list[str]) -> None:
        with self._transaction() as conn:
            # If a placeholder row exists from append_events (status='running'),
            # UPDATE it in place.  INSERT OR REPLACE would trigger ON DELETE
            # CASCADE and destroy already-flushed events.
            placeholder = conn.execute(
                "SELECT 1 FROM runs WHERE run_id = ? AND status = 'running'",
                (run.run_id,),
            ).fetchone()

            start_ts = run.start_time.timestamp()
            end_ts = run.end_time.timestamp() if run.end_time else None
            duration_s = run.duration.total_seconds() if run.duration else None

            if placeholder:
                conn.execute(
                    """UPDATE runs
                       SET start_time = ?, end_time = ?, duration_s = ?,
                           status = ?, error_message = ?, error_step = ?,
                           run_meta = ?
                       WHERE run_id = ?""",
                    (
                        start_ts,
                        end_ts,
                        duration_s,
                        run.status.value,
                        run.error_message,
                        run.error_step,
                        run.run_meta,
                        run.run_id,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO runs
                       (run_id, start_time, end_time, duration_s, status,
                        error_message, error_step, run_meta)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run.run_id,
                        start_ts,
                        end_ts,
                        duration_s,
                        run.status.value,
                        run.error_message,
                        run.error_step,
                        run.run_meta,
                    ),
                )
            for seq, data in enumerate(events, start=1):
                parsed = json.loads(data)
                conn.execute(
                    """INSERT INTO events (run_id, seq, timestamp, data)
                       VALUES (?, ?, ?, ?)""",
                    (run.run_id, seq, parsed.get("timestamp", 0), data),
                )

    def append_events(self, run_id: str, events: list[str]) -> None:
        with self._transaction() as conn:
            # Ensure a placeholder run row exists for FK constraints.
            # The final save_run call will update it with real metadata.
            conn.execute(
                """INSERT OR IGNORE INTO runs
                   (run_id, start_time, status)
                   VALUES (?, ?, ?)""",
                (run_id, 0, "running"),
            )
            for data in events:
                parsed = json.loads(data)
                seq = parsed.get("seq", 0)
                conn.execute(
                    """INSERT OR IGNORE INTO events (run_id, seq, timestamp, data)
                       VALUES (?, ?, ?, ?)""",
                    (run_id, seq, parsed.get("timestamp", 0), data),
                )

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return self._row_to_run(row) if row else None

    def list_runs(
        self,
        status: PipelineTerminalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        with self._conn() as conn:
            query = "SELECT * FROM runs"
            params: list[Any] = []
            if status is not None:
                query += " WHERE status = ?"
                params.append(status.value)
            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return [self._row_to_run(r) for r in conn.execute(query, params).fetchall()]

    def get_events(
        self,
        run_id: str,
        event_type: EventType | None = None,
    ) -> list[StoredEvent]:
        with self._conn() as conn:
            query = (
                "SELECT seq, timestamp, event_type, step_name, data "
                "FROM events WHERE run_id = ?"
            )
            params: list[Any] = [run_id]
            if event_type is not None:
                query += " AND event_type = ?"
                params.append(event_type.value)
            query += " ORDER BY seq ASC"
            return [
                self._row_to_event(r) for r in conn.execute(query, params).fetchall()
            ]

    _RUN_ID_SAFE = re.compile(r"^[a-zA-Z0-9\-_]+$")

    def find_runs_by_prefix(
        self, run_id_prefix: str, limit: int = 10
    ) -> list[RunRecord]:
        if not run_id_prefix or not self._RUN_ID_SAFE.match(run_id_prefix):
            return []
        with self._conn() as conn:
            escaped = (
                run_id_prefix.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            rows = conn.execute(
                "SELECT * FROM runs WHERE run_id LIKE ? ESCAPE '\\' ORDER BY start_time DESC LIMIT ?",
                (escaped + "%", limit),
            ).fetchall()
            return [self._row_to_run(r) for r in rows]

    def delete_run(self, run_id: str) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            start_time=datetime.fromtimestamp(row["start_time"], tz=timezone.utc),
            end_time=(
                datetime.fromtimestamp(row["end_time"], tz=timezone.utc)
                if row["end_time"] is not None
                else None
            ),
            duration=(
                timedelta(seconds=row["duration_s"])
                if row["duration_s"] is not None
                else None
            ),
            status=PipelineTerminalStatus(row["status"])
            if row["status"]
            else PipelineTerminalStatus.FAILED,
            error_message=row["error_message"],
            error_step=row["error_step"],
            run_meta=row["run_meta"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> StoredEvent:
        return StoredEvent(
            seq=row["seq"],
            timestamp=datetime.fromtimestamp(row["timestamp"], tz=timezone.utc),
            event_type=EventType(row["event_type"]),
            step_name=row["step_name"] or "",
            data=row["data"],
        )
