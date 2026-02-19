"""Unit tests for CLI export helpers."""

from datetime import datetime

from justpipe.cli.commands.export import _export_events
from justpipe.storage.interface import StoredEvent
from justpipe.types import EventType


def test_export_events_survives_malformed_json() -> None:
    """Test that _export_events handles malformed JSON gracefully."""
    events = [
        StoredEvent(
            seq=1,
            timestamp=datetime(2024, 1, 15, 12, 0, 0),
            event_type=EventType.STEP_START,
            step_name="step_a",
            data='{"type": "step_start", "stage": "step_a"}',
        ),
        StoredEvent(
            seq=2,
            timestamp=datetime(2024, 1, 15, 12, 0, 1),
            event_type=EventType.STEP_END,
            step_name="step_a",
            data="not valid json {{{",
        ),
    ]
    exported = _export_events(events)
    assert len(exported) == 2
    assert exported[0]["data"] is not None
    assert exported[1]["data"] is None
