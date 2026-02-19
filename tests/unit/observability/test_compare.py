"""Unit tests for compare module step time calculation."""

from datetime import datetime

from justpipe.observability.compare import _build_step_times
from justpipe.storage.interface import StoredEvent
from justpipe.types import EventType


def test_errored_step_not_in_step_times() -> None:
    """A step that started but never ended should not appear in step_times."""
    events = [
        StoredEvent(
            seq=1,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            event_type=EventType.STEP_START,
            step_name="fetch",
            data="{}",
        ),
        # No STEP_END for "fetch" — it errored
        StoredEvent(
            seq=2,
            timestamp=datetime(2025, 1, 1, 12, 0, 1),
            event_type=EventType.STEP_START,
            step_name="process",
            data="{}",
        ),
        StoredEvent(
            seq=3,
            timestamp=datetime(2025, 1, 1, 12, 0, 3),
            event_type=EventType.STEP_END,
            step_name="process",
            data="{}",
        ),
    ]

    result = _build_step_times(events)
    assert "fetch" not in result
    assert "process" in result
    assert abs(result["process"] - 2.0) < 0.001
