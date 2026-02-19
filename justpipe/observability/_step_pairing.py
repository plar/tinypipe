"""Shared STEP_START / STEP_END pairing logic for timeline consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from justpipe.types import EventType


@dataclass(frozen=True, slots=True)
class StepSpan:
    """A completed step span with start/end timestamps and computed duration."""

    step_name: str
    start: Any  # float or datetime depending on caller
    end: Any
    duration: float  # always seconds
    status: str  # "success" or "error"


def pair_step_events(
    events: list[tuple[str, EventType, Any]],
) -> list[StepSpan]:
    """Pair STEP_START with STEP_END/STEP_ERROR events into StepSpans.

    Args:
        events: List of (step_name, event_type, timestamp) tuples.
            Timestamps can be floats (epoch seconds) or datetimes.

    Returns:
        List of StepSpan objects in event order.
    """
    starts: dict[str, Any] = {}
    spans: list[StepSpan] = []

    for step_name, event_type, timestamp in events:
        if event_type == EventType.STEP_START:
            starts[step_name] = timestamp
        elif event_type == EventType.STEP_END and step_name in starts:
            start_ts = starts.pop(step_name)
            duration = _compute_duration(start_ts, timestamp)
            spans.append(
                StepSpan(step_name, start_ts, timestamp, duration, "success")
            )
        elif event_type == EventType.STEP_ERROR and step_name in starts:
            start_ts = starts.pop(step_name)
            duration = _compute_duration(start_ts, timestamp)
            spans.append(
                StepSpan(step_name, start_ts, timestamp, duration, "error")
            )

    return spans


def _compute_duration(start: Any, end: Any) -> float:
    """Compute duration in seconds between two timestamps."""
    diff = end - start
    # datetime.timedelta has .total_seconds(), float subtraction is direct
    if hasattr(diff, "total_seconds"):
        return float(diff.total_seconds())
    return float(diff)
