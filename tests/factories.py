"""Shared test factories for RunRecord and event data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from justpipe.storage.interface import RunRecord
from justpipe.types import PipelineTerminalStatus


def make_run(
    run_id: str = "run1",
    status: PipelineTerminalStatus = PipelineTerminalStatus.SUCCESS,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    duration: timedelta | None = None,
    error_message: str | None = None,
    error_step: str | None = None,
    run_meta: str | None = None,
) -> RunRecord:
    """Create a RunRecord with sensible defaults for testing."""
    _start = start_time or datetime(2025, 1, 1, 12, 0, 0)
    _end = end_time or datetime(2025, 1, 1, 12, 0, 5)
    _dur = duration or timedelta(seconds=5)
    return RunRecord(
        run_id=run_id,
        start_time=_start,
        end_time=_end,
        duration=_dur,
        status=status,
        error_message=error_message,
        error_step=error_step,
        run_meta=run_meta,
    )


def make_events() -> list[str]:
    """Create a minimal set of serialized pipeline events for testing."""
    return [
        json.dumps(
            {
                "type": "start",
                "stage": "system",
                "timestamp": 1704110400.0,
                "node_kind": "system",
                "attempt": 1,
            }
        ),
        json.dumps(
            {
                "type": "step_start",
                "stage": "step_a",
                "timestamp": 1704110400.1,
                "node_kind": "step",
                "attempt": 1,
            }
        ),
        json.dumps(
            {
                "type": "step_end",
                "stage": "step_a",
                "timestamp": 1704110400.5,
                "node_kind": "step",
                "attempt": 1,
            }
        ),
        json.dumps(
            {
                "type": "finish",
                "stage": "system",
                "timestamp": 1704110405.0,
                "node_kind": "system",
                "attempt": 1,
            }
        ),
    ]
