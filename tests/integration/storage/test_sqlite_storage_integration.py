import tempfile

import pytest

from justpipe.types import Event, EventType


@pytest.mark.asyncio
async def test_sqlite_update_run_noop_when_no_fields_provided() -> None:
    pytest.importorskip("aiosqlite")
    from justpipe.storage.sqlite import SQLiteStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteStorage(tmpdir)
        run_id = await storage.create_run("pipeline", {"meta": "v"})

        before = await storage.get_run(run_id)
        assert before is not None
        assert before.status == "running"

        await storage.update_run(run_id)

        after = await storage.get_run(run_id)
        assert after is not None
        assert after.status == "running"


@pytest.mark.asyncio
async def test_sqlite_list_runs_filters_offset_and_event_type_filter() -> None:
    pytest.importorskip("aiosqlite")
    from justpipe.storage.sqlite import SQLiteStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteStorage(tmpdir)

        run1 = await storage.create_run("pipeline", {"idx": 1})
        run2 = await storage.create_run("pipeline", {"idx": 2})
        run3 = await storage.create_run("other", {"idx": 3})

        await storage.update_run(run1, status="success", end_time=1.0, duration=1.0)
        await storage.update_run(
            run2,
            status="error",
            end_time=2.0,
            duration=2.0,
            error_message="boom",
        )
        await storage.update_run(run3, status="success", end_time=3.0, duration=3.0)

        filtered = await storage.list_runs(pipeline_name="pipeline", status="success")
        assert len(filtered) == 1
        assert filtered[0].id == run1

        paged = await storage.list_runs(limit=1, offset=1)
        assert len(paged) == 1

        await storage.add_event(run1, Event(EventType.START, "system", {"k": 1}))
        await storage.add_event(run1, Event(EventType.STEP_END, "step", {"k": 2}))

        only_start = await storage.get_events(run1, event_types=[EventType.START])
        assert len(only_start) == 1
        assert only_start[0].event_type == "start"


@pytest.mark.asyncio
async def test_sqlite_delete_missing_run_and_missing_artifact() -> None:
    pytest.importorskip("aiosqlite")
    from justpipe.storage.sqlite import SQLiteStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteStorage(tmpdir)

        assert await storage.delete_run("missing") is False
        assert await storage.load_artifact("missing", "not-found.bin") is None


@pytest.mark.asyncio
async def test_sqlite_serialization_and_deserialization_fallbacks() -> None:
    pytest.importorskip("aiosqlite")
    from justpipe.storage.sqlite import SQLiteStorage

    class BadStr:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteStorage(tmpdir)

        run_id = await storage.create_run("pipeline", {"bad": BadStr()})

        # Force invalid JSON in run metadata and event payload to trigger deserialize fallback
        async with storage._connect() as conn:
            await conn.execute(
                "UPDATE runs SET metadata = ? WHERE id = ?", ("{", run_id)
            )
            await conn.execute(
                "INSERT INTO events (run_id, timestamp, event_type, step_name, payload) VALUES (?, ?, ?, ?, ?)",
                (run_id, 1.0, "start", "system", "{"),
            )
            await conn.commit()

        run = await storage.get_run(run_id)
        assert run is not None
        assert str(run.metadata) == "{"

        events = await storage.get_events(run_id)
        assert events
        assert events[0].payload == "{"
