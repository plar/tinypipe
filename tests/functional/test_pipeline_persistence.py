"""Functional tests for persist=True end-to-end pipeline persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from justpipe import Meta, Pipe
from justpipe.storage.sqlite import SQLiteBackend
from justpipe.types import PipelineTerminalStatus


@dataclass
class SimpleState:
    value: int = 0


@dataclass
class MetaContext:
    meta: Meta | None = None


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: Any) -> Path:
    """Redirect persistence to a temp directory."""
    monkeypatch.setenv("JUSTPIPE_STORAGE_PATH", str(tmp_path))
    return tmp_path


def _find_runs_db(storage_dir: Path) -> Path | None:
    """Find the runs.db file under the storage directory."""
    for db in storage_dir.rglob("runs.db"):
        return db
    return None


async def test_persist_creates_db(storage_dir: Path) -> None:
    """Pipeline with persist=True creates runs.db."""
    pipe: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_persist", persist=True)

    @pipe.step()
    async def add_one(state: SimpleState) -> None:
        state.value += 1

    async for _ in pipe.run(SimpleState(value=0)):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None, "runs.db should be created"

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 1
    assert runs[0].status == PipelineTerminalStatus.SUCCESS


async def test_persist_false_no_files(storage_dir: Path) -> None:
    """Pipeline with persist=False creates no files."""
    pipe: Pipe[SimpleState, Any] = Pipe(
        SimpleState, name="test_no_persist", persist=False
    )

    @pipe.step()
    async def add_one(state: SimpleState) -> None:
        state.value += 1

    async for _ in pipe.run(SimpleState(value=0)):
        pass

    assert _find_runs_db(storage_dir) is None


async def test_persist_stores_events(storage_dir: Path) -> None:
    """Persisted runs include all events."""
    pipe: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_events", persist=True)

    @pipe.step(to=["step_b"])
    async def step_a(state: SimpleState) -> None:
        state.value += 1

    @pipe.step()
    async def step_b(state: SimpleState) -> None:
        state.value += 10

    async for _ in pipe.run(SimpleState(value=0)):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 1

    events = backend.get_events(runs[0].run_id)
    assert len(events) >= 4  # start, step_start, step_end, ..., finish

    # Check event types are correctly stored via generated columns
    event_types = [e.event_type.value for e in events]
    assert "start" in event_types
    assert "finish" in event_types
    assert "step_start" in event_types
    assert "step_end" in event_types


async def test_persist_with_meta(storage_dir: Path) -> None:
    """Persisted runs include user meta snapshot."""
    pipe: Pipe[SimpleState, MetaContext] = Pipe(
        context_type=MetaContext, name="test_meta_persist", persist=True
    )

    @pipe.step()
    async def add_one(state: SimpleState, ctx: MetaContext) -> None:
        state.value += 1
        if ctx.meta:
            ctx.meta.run.set("label", "test-run")
            ctx.meta.run.add_tag("integration")
            ctx.meta.step.record_metric("latency", 0.5)

    ctx = MetaContext()
    async for _ in pipe.run(SimpleState(value=0), ctx):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 1
    assert runs[0].run_meta is not None

    meta = json.loads(runs[0].run_meta)
    assert meta["data"]["label"] == "test-run"
    assert "integration" in meta["tags"]


async def test_persist_without_meta(storage_dir: Path) -> None:
    """Pipeline without Meta field on context persists core events."""
    pipe: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_no_meta", persist=True)

    @pipe.step()
    async def add_one(state: SimpleState) -> None:
        state.value += 1

    async for _ in pipe.run(SimpleState(value=0)):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 1
    # No run_meta when context doesn't have Meta field
    assert runs[0].run_meta is None


async def test_same_pipeline_twice_same_db(storage_dir: Path) -> None:
    """Running the same pipeline twice stores both runs in the same DB."""
    pipe: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_same", persist=True)

    @pipe.step()
    async def add_one(state: SimpleState) -> None:
        state.value += 1

    async for _ in pipe.run(SimpleState(value=0)):
        pass
    async for _ in pipe.run(SimpleState(value=0)):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 2


async def test_different_topology_different_hash(storage_dir: Path) -> None:
    """Pipelines with different topologies get different storage directories."""
    # Pipeline A: one step
    pipe_a: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_diff", persist=True)

    @pipe_a.step()
    async def step_a(state: SimpleState) -> None:
        state.value += 1

    # Pipeline B: two steps
    pipe_b: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_diff", persist=True)

    @pipe_b.step(to=["step_d"])
    async def step_c(state: SimpleState) -> None:
        state.value += 1

    @pipe_b.step()
    async def step_d(state: SimpleState) -> None:
        state.value += 10

    async for _ in pipe_a.run(SimpleState(value=0)):
        pass
    async for _ in pipe_b.run(SimpleState(value=0)):
        pass

    # Should have 2 different pipeline directories
    db_files = list(storage_dir.rglob("runs.db"))
    assert len(db_files) == 2


async def test_persist_writes_pipeline_json(storage_dir: Path) -> None:
    """Persistence writes pipeline.json alongside runs.db."""
    pipe: Pipe[SimpleState, Any] = Pipe(
        SimpleState, name="test_pipeline_json", persist=True
    )

    @pipe.step()
    async def add_one(state: SimpleState) -> None:
        state.value += 1

    async for _ in pipe.run(SimpleState(value=0)):
        pass

    pipeline_jsons = list(storage_dir.rglob("pipeline.json"))
    assert len(pipeline_jsons) == 1

    data = json.loads(pipeline_jsons[0].read_text())
    assert data["name"] == "test_pipeline_json"


async def test_persist_error_run(storage_dir: Path) -> None:
    """Pipeline errors are recorded in the persisted run."""
    pipe: Pipe[SimpleState, Any] = Pipe(SimpleState, name="test_error", persist=True)

    @pipe.step()
    async def fail_step(state: SimpleState) -> None:
        raise ValueError("intentional error")

    # justpipe catches step errors and reports them in the FINISH event
    async for _ in pipe.run(SimpleState(value=0)):
        pass

    db_path = _find_runs_db(storage_dir)
    assert db_path is not None

    backend = SQLiteBackend(db_path)
    runs = backend.list_runs()
    assert len(runs) == 1
    assert runs[0].status == PipelineTerminalStatus.FAILED
