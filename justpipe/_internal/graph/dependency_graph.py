from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from collections.abc import Callable

from justpipe.types import BarrierType, NodeKind
from justpipe._internal.shared.utils import _resolve_name

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep


def compute_roots(
    steps: dict[str, _BaseStep],
    topology: dict[str, list[str]],
) -> set[str]:
    """Compute entry points: steps that are not targets of any other step."""
    all_targets: set[str] = set()
    for children in topology.values():
        all_targets.update(children)
    for step in steps.values():
        all_targets.update(step.get_targets())
    return set(steps.keys()) - all_targets


@dataclass
class TransitionResult:
    steps_to_start: list[str] = field(default_factory=list)
    barriers_to_schedule: list[tuple[str, float]] = field(default_factory=list)
    barriers_to_cancel: list[str] = field(default_factory=list)


class _DependencyGraph:
    """Runtime dependency tracker for barrier/transition state."""

    def __init__(
        self,
        steps: dict[str, _BaseStep],
        topology: dict[str, list[str]],
        parents_map: dict[str, set[str]] | None = None,
    ):
        self._steps = steps
        self._topology = topology
        self._parents_map: dict[str, set[str]] = (
            defaultdict(set) if parents_map is None else defaultdict(set, parents_map)
        )
        self._completed_parents: dict[str, set[str]] = defaultdict(set)
        self._satisfied_nodes: set[str] = set()

    def build(self) -> None:
        """Build the reverse dependency graph (parents map)."""
        if not self._parents_map:
            for parent, children in self._topology.items():
                for child in children:
                    self._parents_map[child].add(parent)
        self._completed_parents.clear()
        self._satisfied_nodes.clear()

        # Pre-compute switch sibling groups per child node.
        # Switch targets are mutually exclusive — only one runs per execution.
        # When a child has multiple parents from the same switch, we track
        # which parents form an exclusive group so the ALL barrier can adjust.
        self._switch_sibling_groups: dict[str, list[set[str]]] = {}
        for name, step in self._steps.items():
            if step.get_kind() != NodeKind.SWITCH:
                continue
            targets = set(step.get_targets())
            for child, parents in self._parents_map.items():
                group = targets & parents
                if len(group) > 1:
                    self._switch_sibling_groups.setdefault(child, []).append(group)

    def get_roots(self, start: str | Callable[..., Any] | None = None) -> set[str]:
        """Determine entry points for execution."""
        if start:
            return {_resolve_name(start)}
        return compute_roots(self._steps, self._topology)

    def get_successors(self, node: str) -> list[str]:
        return self._topology.get(node, [])

    def parents_map_snapshot(self) -> dict[str, set[str]]:
        return {node: set(parents) for node, parents in self._parents_map.items()}

    def transition(self, completed_node: str) -> TransitionResult:
        """
        Process the completion of a node and determine next actions.
        """
        result = TransitionResult()

        for succ in self.get_successors(completed_node):
            step = self._steps.get(succ)
            barrier_type = step.barrier_type if step else BarrierType.ALL
            parents_needed = self._parents_map[succ]

            # 1. Check if we need to schedule a barrier (only for the first parent of a multi-parent node)
            is_first = len(self._completed_parents[succ]) == 0
            if is_first and len(parents_needed) > 1 and barrier_type != BarrierType.ANY:
                timeout = step.barrier_timeout if step else None
                if timeout:
                    result.barriers_to_schedule.append((succ, timeout))

            # 2. Delegate to specialized barrier handler
            should_start = False
            if barrier_type == BarrierType.ANY:
                should_start = self._handle_any_barrier(succ, completed_node)
            else:
                should_start = self._handle_all_barrier(succ, completed_node)

            # 3. If the barrier is satisfied, start the step and cancel any pending barrier timeout
            if should_start:
                if len(parents_needed) > 1:
                    result.barriers_to_cancel.append(succ)
                result.steps_to_start.append(succ)

        return result

    def _handle_any_barrier(self, node: str, parent: str) -> bool:
        """
        Logic for ANY barrier: ready as soon as the first parent completes.

        It tracks subsequent parents to ensure they don't trigger multiple executions
        of the same step in the same 'wave'.
        """
        if node in self._satisfied_nodes:
            self._update_node_progress(node, parent)
            if self._is_all_parents_completed(node):
                self._reset_node_progress(node)
                self._satisfied_nodes.remove(node)
            return False

        self._update_node_progress(node, parent)
        self._satisfied_nodes.add(node)

        # If this was also the last parent, reset immediately for next wave
        if self._is_all_parents_completed(node):
            self._reset_node_progress(node)
            self._satisfied_nodes.remove(node)

        return True

    def _handle_all_barrier(self, node: str, parent: str) -> bool:
        """Logic for ALL barrier: ready only when all parents complete."""
        self._update_node_progress(node, parent)
        if self._is_all_parents_completed(node):
            self._reset_node_progress(node)
            return True
        return False

    def _update_node_progress(self, node: str, parent: str) -> None:
        """Mark a parent as completed for the given node."""
        self._completed_parents[node].add(parent)

    def _reset_node_progress(self, node: str) -> None:
        """Reset completion tracking for a node."""
        self._completed_parents[node].clear()

    def _is_all_parents_completed(self, node: str) -> bool:
        """Check if every expected parent has reported completion."""
        completed = self._completed_parents[node]
        required = set(self._parents_map[node])

        # Switch siblings are mutually exclusive — if any completed, others won't run
        for group in self._switch_sibling_groups.get(node, []):
            if completed & group:  # At least one sibling completed
                required -= group - completed  # Remove unreachable siblings

        return completed >= required

    def is_barrier_satisfied(self, node: str) -> bool:
        """Check if a node's barrier is met (all parents finished)."""
        return self._is_all_parents_completed(node)
