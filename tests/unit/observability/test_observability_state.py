from dataclasses import dataclass
from typing import Any

import pytest

from justpipe.observability import ObserverMeta, StateDiffTracker
from justpipe.types import Event, EventType


PIPE_META = ObserverMeta(pipe_name="state_pipe")


@dataclass
class ObjState:
    value: int
    name: str


@pytest.mark.asyncio
async def test_snapshots_captured_for_start_step_and_end() -> None:
    tracker = StateDiffTracker()
    state: dict[str, Any] = {"count": 1}

    await tracker.on_pipeline_start(state=state, context=None, meta=PIPE_META)
    state["count"] = 2
    await tracker.on_event(
        state=state,
        context=None,
        meta=PIPE_META,
        event=Event(EventType.STEP_END, "step1"),
    )
    await tracker.on_pipeline_end(
        state=state, context=None, meta=PIPE_META, duration_s=1.0
    )

    assert "__start__" in tracker.snapshots
    assert "step1" in tracker.snapshots
    assert "__end__" in tracker.snapshots
    assert tracker.step_order == ["step1"]


def test_diff_reports_added_removed_and_changed_fields() -> None:
    tracker = StateDiffTracker()
    tracker.snapshots["before"] = {"keep": 1, "old": "x", "change": 1}
    tracker.snapshots["after"] = {"keep": 1, "new": "y", "change": 2}

    rendered = tracker.diff("before", "after")

    assert "Added:" in rendered
    assert "Removed:" in rendered
    assert "Changed:" in rendered
    assert "+ new:" in rendered
    assert "- old:" in rendered
    assert "~ change:" in rendered


def test_diff_handles_missing_or_non_mapping_snapshots() -> None:
    tracker = StateDiffTracker()
    tracker.snapshots["left"] = 1
    tracker.snapshots["right"] = 2

    assert tracker.diff("missing", "right") == "No snapshot found for missing"
    rendered = tracker.diff("left", "right")
    assert "Before: 1" in rendered
    assert "After:  2" in rendered


def test_summary_reports_changes_by_step() -> None:
    tracker = StateDiffTracker()
    tracker.snapshots["__start__"] = {"a": 1}
    tracker.snapshots["s1"] = {"a": 2, "b": 3}
    tracker.snapshots["s2"] = {"a": 2, "b": 4}
    tracker.step_order = ["s1", "s2"]

    rendered = tracker.summary()

    assert "State Changes Summary" in rendered
    assert "s1:" in rendered
    assert "s2:" in rendered
    assert "+ b" in rendered or "~ b" in rendered


def test_summary_without_step_order_is_explicit() -> None:
    tracker = StateDiffTracker()
    assert tracker.summary() == "No state snapshots captured"


def test_serialize_value_truncates_long_values() -> None:
    truncating_tracker = StateDiffTracker(max_value_length=8)
    regular_tracker = StateDiffTracker(max_value_length=64)

    assert truncating_tracker._serialize_value("abcdefghijk") == "abcde..."
    assert regular_tracker._serialize_value([1, 2, 3]) == "list(3 items)"
    assert regular_tracker._serialize_value({"a": 1}) == "dict(1 keys)"
    assert regular_tracker._serialize_value({1, 2}) == "set(2 items)"


def test_export_json_handles_non_serializable_values() -> None:
    tracker = StateDiffTracker()
    tracker.snapshots["obj"] = ObjState(value=1, name="x")

    payload = tracker.export_json()

    assert '"obj"' in payload
    assert "ObjState" in payload
