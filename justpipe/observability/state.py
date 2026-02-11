"""State tracking and diff visualization for pipeline debugging."""

import copy
import json
from typing import Any

from justpipe.observability import Observer, ObserverMeta
from justpipe.types import Event, EventType


class StateDiffTracker(Observer):
    """Observer that tracks state changes and generates diffs between steps.

    Captures state snapshots after each step completes and provides
    utilities for comparing state at different points in execution.

    Example:
        from justpipe.observability import StateDiffTracker

        tracker = StateDiffTracker()
        pipe.add_observer(tracker)

        async for event in pipe.run(state):
            pass

        # Compare state after two steps
        diff = tracker.diff("step1", "step2")
        print(diff)

        # Show all changes
        print(tracker.summary())
    """

    def __init__(self, max_value_length: int = 200):
        """Initialize StateDiffTracker.

        Args:
            max_value_length: Maximum length for displayed values
        """
        self.max_value_length = max_value_length
        self.snapshots: dict[str, Any] = {}
        self.initial_state: Any | None = None
        self.step_order: list[str] = []

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Capture initial state."""
        _ = (context, meta)
        try:
            self.initial_state = copy.deepcopy(state)
            self.snapshots["__start__"] = self.initial_state
        except Exception:
            # Some objects can't be deep copied
            self.initial_state = None

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Capture state after each step."""
        _ = (context, meta)
        if event.type == EventType.STEP_END:
            try:
                snapshot = copy.deepcopy(state)
                self.snapshots[event.stage] = snapshot

                if event.stage not in self.step_order:
                    self.step_order.append(event.stage)
            except Exception:
                # Can't deep copy this state
                pass

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Capture final state."""
        _ = (context, meta, duration_s)
        try:
            self.snapshots["__end__"] = copy.deepcopy(state)
        except Exception:
            pass

    def get_snapshot(self, step: str) -> Any | None:
        """Get state snapshot after a specific step.

        Args:
            step: Step name, "__start__" for initial, or "__end__" for final

        Returns:
            State snapshot or None if not found
        """
        return self.snapshots.get(step)

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for display."""
        try:
            if isinstance(value, (str, int, float, bool, type(None))):
                s = str(value)
            elif isinstance(value, (list, tuple)):
                s = f"{type(value).__name__}({len(value)} items)"
            elif isinstance(value, dict):
                s = f"dict({len(value)} keys)"
            elif isinstance(value, set):
                s = f"set({len(value)} items)"
            else:
                s = f"{type(value).__name__}"

            if len(s) > self.max_value_length:
                s = s[: self.max_value_length - 3] + "..."

            return s
        except Exception:
            return "<unserializable>"

    def _get_dict_diff(
        self, before: dict[Any, Any], after: dict[Any, Any]
    ) -> dict[str, dict[str, Any]]:
        """Compare two dictionaries.

        Returns:
            dict with keys: added, removed, changed
        """
        before_keys = set(before.keys())
        after_keys = set(after.keys())

        added = {k: after[k] for k in after_keys - before_keys}
        removed = {k: before[k] for k in before_keys - after_keys}
        changed = {}

        for k in before_keys & after_keys:
            if before[k] != after[k]:
                changed[k] = {"before": before[k], "after": after[k]}

        return {"added": added, "removed": removed, "changed": changed}

    def _get_obj_diff(self, before: Any, after: Any) -> dict[str, dict[str, Any]]:
        """Compare two objects by their __dict__.

        Returns:
            dict with keys: added, removed, changed
        """
        before_dict = getattr(before, "__dict__", {})
        after_dict = getattr(after, "__dict__", {})

        return self._get_dict_diff(before_dict, after_dict)

    def diff(self, step1: str, step2: str) -> str:
        """Generate a human-readable diff between two steps.

        Args:
            step1: First step name (or "__start__")
            step2: Second step name (or "__end__")

        Returns:
            Formatted diff string
        """
        snapshot1 = self.get_snapshot(step1)
        snapshot2 = self.get_snapshot(step2)

        if snapshot1 is None:
            return f"No snapshot found for {step1}"
        if snapshot2 is None:
            return f"No snapshot found for {step2}"

        lines = []
        lines.append(f"\nState Changes: {step1} → {step2}")
        lines.append("=" * 60)

        # Try dict comparison first
        if isinstance(snapshot1, dict) and isinstance(snapshot2, dict):
            diff = self._get_dict_diff(snapshot1, snapshot2)
        # Then try object comparison
        elif hasattr(snapshot1, "__dict__") and hasattr(snapshot2, "__dict__"):
            diff = self._get_obj_diff(snapshot1, snapshot2)
        # Otherwise just show both
        else:
            lines.append(f"\nBefore: {self._serialize_value(snapshot1)}")
            lines.append(f"After:  {self._serialize_value(snapshot2)}")
            return "\n".join(lines)

        # Show added fields
        if diff["added"]:
            lines.append("\nAdded:")
            for key, value in sorted(diff["added"].items()):
                lines.append(f"  + {key}: {self._serialize_value(value)}")

        # Show removed fields
        if diff["removed"]:
            lines.append("\nRemoved:")
            for key, value in sorted(diff["removed"].items()):
                lines.append(f"  - {key}: {self._serialize_value(value)}")

        # Show changed fields
        if diff["changed"]:
            lines.append("\nChanged:")
            for key, change in sorted(diff["changed"].items()):
                before_str = self._serialize_value(change["before"])
                after_str = self._serialize_value(change["after"])
                lines.append(f"  ~ {key}:")
                lines.append(f"      {before_str}")
                lines.append(f"    → {after_str}")

        # Summary
        total_changes = len(diff["added"]) + len(diff["removed"]) + len(diff["changed"])
        if total_changes == 0:
            lines.append("\nNo changes detected")

        lines.append("")
        return "\n".join(lines)

    def summary(self) -> str:
        """Generate a summary of all state changes.

        Returns:
            Formatted summary string
        """
        if not self.step_order:
            return "No state snapshots captured"

        lines = []
        lines.append("\nState Changes Summary")
        lines.append("=" * 60)

        # Show changes for each step
        prev_step = "__start__"
        for step in self.step_order:
            snapshot_before = self.get_snapshot(prev_step)
            snapshot_after = self.get_snapshot(step)

            if snapshot_before is None or snapshot_after is None:
                continue

            # Count changes
            if isinstance(snapshot_before, dict) and isinstance(snapshot_after, dict):
                diff = self._get_dict_diff(snapshot_before, snapshot_after)
            elif hasattr(snapshot_before, "__dict__") and hasattr(
                snapshot_after, "__dict__"
            ):
                diff = self._get_obj_diff(snapshot_before, snapshot_after)
            else:
                continue

            total_changes = (
                len(diff["added"]) + len(diff["removed"]) + len(diff["changed"])
            )

            if total_changes > 0:
                changes_str = []
                if diff["added"]:
                    changes_str.append(f"+{len(diff['added'])}")
                if diff["removed"]:
                    changes_str.append(f"-{len(diff['removed'])}")
                if diff["changed"]:
                    changes_str.append(f"~{len(diff['changed'])}")

                lines.append(f"\n{step}:")
                lines.append(f"  Changes: {', '.join(changes_str)}")

                # Show key changes
                if diff["added"]:
                    for key in sorted(diff["added"].keys())[:3]:  # Show first 3
                        lines.append(f"    + {key}")
                if diff["changed"]:
                    for key in sorted(diff["changed"].keys())[:3]:
                        lines.append(f"    ~ {key}")

            prev_step = step

        lines.append("")
        return "\n".join(lines)

    def get_all_snapshots(self) -> dict[str, Any]:
        """Get all captured state snapshots.

        Returns:
            dict mapping step names to state snapshots
        """
        return dict(self.snapshots)

    def export_json(self) -> str:
        """Export all snapshots as JSON.

        Returns:
            JSON string with all snapshots
        """
        serializable = {}
        for step, snapshot in self.snapshots.items():
            try:
                serializable[step] = json.loads(json.dumps(snapshot, default=str))
            except Exception:
                serializable[step] = str(snapshot)

        return json.dumps(serializable, indent=2, default=str)
