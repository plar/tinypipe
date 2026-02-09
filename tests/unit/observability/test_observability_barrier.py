import pytest

from justpipe.observability import BarrierDebugRecord, BarrierDebugger, ObserverMeta
from justpipe.types import Event, EventType


PIPE_META = ObserverMeta(pipe_name="barrier_pipe")


@pytest.mark.asyncio
async def test_wait_then_release_warns_on_slow_barrier() -> None:
    records: list[BarrierDebugRecord] = []
    debugger = BarrierDebugger(warn_after=0.5, clock=lambda: 2.0, sink=records.append)

    await debugger.on_pipeline_start(state={}, context=None, meta=PIPE_META)
    await debugger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(
            EventType.BARRIER_WAIT,
            "join",
            payload={"expected_count": 2, "completed_count": 1, "waiting_for": ["w2"]},
            timestamp=1.0,
        ),
    )
    await debugger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.BARRIER_RELEASE, "join", timestamp=2.0),
    )

    assert len(records) == 1
    assert records[0].kind == "slow"
    assert records[0].barrier_name == "join"
    assert records[0].wait_time_s == pytest.approx(1.0)
    assert debugger.waiting_barriers == {}
    assert "join" in debugger.warned_barriers


@pytest.mark.asyncio
async def test_hang_warning_emits_structured_details() -> None:
    records: list[BarrierDebugRecord] = []
    debugger = BarrierDebugger(warn_after=0.1, clock=lambda: 12.0, sink=records.append)

    await debugger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(
            EventType.BARRIER_WAIT,
            "join",
            payload={
                "expected_count": 2,
                "completed_count": 1,
                "waiting_for": ["w1", "w2"],
            },
            timestamp=10.0,
        ),
    )
    debugger.worker_activity["w1"] = 11.5

    await debugger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.STEP_START, "probe", timestamp=10.3),
    )

    assert len(records) == 1
    assert records[0].kind == "hang"
    assert records[0].barrier_name == "join"
    assert records[0].expected_count == 2
    assert records[0].completed_count == 1
    assert "w1: inactive" in records[0].message
    assert "w2: never started" in records[0].message


@pytest.mark.asyncio
async def test_pipeline_end_and_error_report_unresolved_and_clear_state() -> None:
    records: list[BarrierDebugRecord] = []
    debugger = BarrierDebugger(warn_after=1.0, clock=lambda: 10.0, sink=records.append)
    debugger.waiting_barriers["join"] = {"waiting_for": ["w1"]}
    debugger.worker_activity["w1"] = 5.0
    debugger.warned_barriers.add("join")

    await debugger.on_pipeline_end(
        state={}, context=None, meta=PIPE_META, duration_s=2.0
    )
    assert any(record.kind == "unresolved" for record in records)
    assert debugger.waiting_barriers == {}
    assert debugger.worker_activity == {}
    assert debugger.warned_barriers == set()

    debugger.waiting_barriers["join2"] = {"waiting_for": ["w2"]}
    await debugger.on_pipeline_error(
        state={},
        context=None,
        meta=PIPE_META,
        error=RuntimeError("boom"),
    )
    assert any(record.kind == "error_state" for record in records)
    assert debugger.waiting_barriers == {}


@pytest.mark.asyncio
async def test_map_complete_removes_indexed_worker_entries() -> None:
    debugger = BarrierDebugger(warn_after=1.0, clock=lambda: 10.0, sink=None)
    debugger.worker_activity = {
        "worker": 1.0,
        "worker[0]": 1.0,
        "worker[1]": 1.0,
        "workerish": 1.0,
    }

    await debugger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(
            EventType.MAP_COMPLETE,
            "fanout",
            payload={"target": "worker"},
        ),
    )

    assert debugger.worker_activity == {"workerish": 1.0}
