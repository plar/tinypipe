"""Shared STEP_START / STEP_END pairing logic for timeline consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from justpipe.types import EventType, StepStatus


@dataclass(frozen=True, slots=True)
class StepSpan:
    """A completed step span with start/end timestamps and computed duration."""

    step_name: str
    start: Any  # float or datetime depending on caller
    end: Any
    duration: float  # always seconds
    status: StepStatus


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
    # Use a stack (LIFO) per step_name to correctly handle concurrent
    # map workers that share the same step name.
    starts: dict[str, list[Any]] = {}
    spans: list[StepSpan] = []

    for step_name, event_type, timestamp in events:
        if event_type == EventType.STEP_START:
            starts.setdefault(step_name, []).append(timestamp)
        elif event_type in (EventType.STEP_END, EventType.STEP_ERROR) and starts.get(
            step_name
        ):
            start_ts = starts[step_name].pop()
            if not starts[step_name]:
                del starts[step_name]
            duration = _compute_duration(start_ts, timestamp)
            status = (
                StepStatus.SUCCESS
                if event_type == EventType.STEP_END
                else StepStatus.ERROR
            )
            spans.append(StepSpan(step_name, start_ts, timestamp, duration, status))

    return spans


def _compute_duration(start: Any, end: Any) -> float:
    """Compute duration in seconds between two timestamps."""
    diff = end - start
    # datetime.timedelta has .total_seconds(), float subtraction is direct
    if hasattr(diff, "total_seconds"):
        return float(diff.total_seconds())
    return float(diff)
