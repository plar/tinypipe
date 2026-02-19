"""Unit tests for runtime metrics recording."""

from justpipe._internal.runtime.telemetry.runtime_metrics import (
    _RuntimeMetricsRecorder,
)
from justpipe.types import Event, EventType, NodeKind


async def test_concurrent_workers_tracked_independently() -> None:
    """Multiple map workers sharing a step name must each get correct timing."""
    recorder = _RuntimeMetricsRecorder()

    # Three map workers for the same step name, started at different times
    for inv_id, start_ts in [
        ("inv:1", 100.0),
        ("inv:2", 100.5),
        ("inv:3", 101.0),
    ]:
        await recorder.on_event(
            Event(
                EventType.STEP_START,
                "worker",
                node_kind=NodeKind.STEP,
                invocation_id=inv_id,
                timestamp=start_ts,
                attempt=1,
                scope=(),
            )
        )

    # All three end at 102.0
    for inv_id in ["inv:1", "inv:2", "inv:3"]:
        await recorder.on_event(
            Event(
                EventType.STEP_END,
                "worker",
                node_kind=NodeKind.STEP,
                invocation_id=inv_id,
                timestamp=102.0,
                attempt=1,
                scope=(),
            )
        )

    snap = recorder.snapshot()
    timing = snap.step_latency["worker"]
    assert timing.count == 3
    assert abs(timing.total_s - 4.5) < 0.001
    assert abs(timing.min_s - 1.0) < 0.001
    assert abs(timing.max_s - 2.0) < 0.001
