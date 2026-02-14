"""SQLite storage backend using stdlib sqlite3 (zero dependencies)."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

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
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save_run(self, run: RunRecord, events: list[str]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO runs
                   (run_id, start_time, end_time, duration_s, status,
                    error_message, error_step, run_meta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.run_id,
                    run.start_time.timestamp(),
                    run.end_time.timestamp() if run.end_time else None,
                    run.duration.total_seconds() if run.duration else None,
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
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_run(self, run_id: str) -> RunRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_run(row)
        finally:
            conn.close()

    def list_runs(
        self,
        status: PipelineTerminalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRecord]:
        conn = self._connect()
        try:
            if status is not None:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE status = ? ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (status.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [self._row_to_run(r) for r in rows]
        finally:
            conn.close()

    def get_events(
        self,
        run_id: str,
        event_type: EventType | None = None,
    ) -> list[StoredEvent]:
        conn = self._connect()
        try:
            if event_type is not None:
                rows = conn.execute(
                    "SELECT seq, timestamp, event_type, step_name, data "
                    "FROM events WHERE run_id = ? AND event_type = ? ORDER BY seq ASC",
                    (run_id, event_type.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT seq, timestamp, event_type, step_name, data "
                    "FROM events WHERE run_id = ? ORDER BY seq ASC",
                    (run_id,),
                ).fetchall()
            return [self._row_to_event(r) for r in rows]
        finally:
            conn.close()

    _RUN_ID_SAFE = re.compile(r"^[a-zA-Z0-9\-_]+$")

    def find_runs_by_prefix(
        self, run_id_prefix: str, limit: int = 10
    ) -> list[RunRecord]:
        if not run_id_prefix or not self._RUN_ID_SAFE.match(run_id_prefix):
            return []
        conn = self._connect()
        try:
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
        finally:
            conn.close()

    def delete_run(self, run_id: str) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            start_time=datetime.fromtimestamp(row["start_time"]),
            end_time=(
                datetime.fromtimestamp(row["end_time"])
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
            else PipelineTerminalStatus.SUCCESS,
            error_message=row["error_message"],
            error_step=row["error_step"],
            run_meta=row["run_meta"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> StoredEvent:
        return StoredEvent(
            seq=row["seq"],
            timestamp=datetime.fromtimestamp(row["timestamp"]),
            event_type=EventType(row["event_type"]),
            step_name=row["step_name"] or "",
            data=row["data"],
        )
