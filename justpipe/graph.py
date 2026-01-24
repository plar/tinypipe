from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set, Union, Tuple

from justpipe.types import Stop, _resolve_name
from justpipe.steps import _BaseStep, _MapStep, _SwitchStep


@dataclass
class TransitionResult:
    steps_to_start: List[str] = field(default_factory=list)
    barriers_to_schedule: List[Tuple[str, float]] = field(default_factory=list)
    barriers_to_cancel: List[str] = field(default_factory=list)


def _validate_routing_target(target: Any) -> None:
    """Validate that a routing target is a valid name or callable."""
    if isinstance(target, str):
        pass
    elif callable(target):
        pass
    elif isinstance(target, list):
        for t in target:
            _validate_routing_target(t)
    elif isinstance(target, dict):
        for t in target.values():
            if t is not Stop:
                _validate_routing_target(t)
    else:
        raise ValueError(
            f"Invalid routing target type: {type(target).__name__}. Expected str, callable, list, or dict."
        )


class _DependencyGraph:
    """Encapsulates the pipeline topology, validation, and dependency tracking."""

    def __init__(
        self,
        steps: Dict[str, _BaseStep],
        topology: Dict[str, List[str]],
    ):
        self._steps = steps
        self._topology = topology
        self._parents_map: Dict[str, Set[str]] = defaultdict(set)
        self._completed_parents: Dict[str, Set[str]] = defaultdict(set)

    def build(self) -> None:
        """Build the reverse dependency graph (parents map)."""
        self._parents_map.clear()
        self._completed_parents.clear()
        for parent, children in self._topology.items():
            for child in children:
                self._parents_map[child].add(parent)

    def get_roots(self, start: Union[str, Callable[..., Any], None] = None) -> Set[str]:
        """Determine entry points for execution."""
        if start:
            return {_resolve_name(start)}
        elif self._steps:
            all_targets = {
                t for step_targets in self._topology.values() for t in step_targets
            }
            for step in self._steps.values():
                all_targets.update(step.get_targets())

            roots = set(self._steps.keys()) - all_targets
            if not roots:
                roots = {next(iter(self._steps))}
            return roots
        return set()

    def get_successors(self, node: str) -> List[str]:
        return self._topology.get(node, [])

    def transition(self, completed_node: str) -> TransitionResult:
        """
        Process the completion of a node and determine next actions.
        """
        result = TransitionResult()

        for succ in self.get_successors(completed_node):
            is_first = len(self._completed_parents[succ]) == 0
            self._completed_parents[succ].add(completed_node)
            parents_needed = self._parents_map[succ]

            is_ready = self._completed_parents[succ] >= parents_needed

            if is_ready:
                # If ready, we can start the step.
                # Also if we were waiting for a barrier, we should cancel it.
                # Note: Only cancel if it was potentially scheduled (parents > 1).
                if len(parents_needed) > 1:
                    result.barriers_to_cancel.append(succ)
                result.steps_to_start.append(succ)
            else:
                # Not ready yet.
                # If this is the first parent arriving and we have multiple parents,
                # we might need to schedule a barrier timeout.
                if is_first and len(parents_needed) > 1:
                    step = self._steps.get(succ)
                    timeout = step.barrier_timeout if step else None
                    if timeout:
                        result.barriers_to_schedule.append((succ, timeout))

        return result

    def is_barrier_satisfied(self, node: str) -> bool:
        return self._completed_parents[node] >= self._parents_map[node]

    def validate(self) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            ValueError: if any unresolvable references or integrity issues are found.
        """
        if not self._steps:
            return

        all_step_names = set(self._steps.keys())
        referenced_names: Set[str] = set()

        # 1. Check topology
        for parent, children in self._topology.items():
            for child in children:
                if child not in all_step_names:
                    raise ValueError(f"Step '{parent}' targets unknown step '{child}'")
                referenced_names.add(child)

        # 2. Check special metadata (map_target, switch_routes)
        for step_name, step in self._steps.items():
            targets = step.get_targets()
            unknowns = [t for t in targets if t not in all_step_names]

            if not unknowns:
                referenced_names.update(targets)
                continue

            # Detailed error reporting for unknowns
            if isinstance(step, _MapStep) and step.map_target in unknowns:
                raise ValueError(
                    f"Step '{step_name}' (map) targets unknown step '{step.map_target}'"
                )

            if isinstance(step, _SwitchStep):
                if step.default in unknowns:
                    raise ValueError(
                        f"Step '{step_name}' (switch) has unknown default route '{step.default}'"
                    )

                if step.routes and isinstance(step.routes, dict):
                    for route_name in step.routes.values():
                        if isinstance(route_name, str) and route_name in unknowns:
                            raise ValueError(
                                f"Step '{step_name}' (switch) routes to unknown step '{route_name}'"
                            )

        # 3. Detect roots (entry points)
        roots = all_step_names - referenced_names
        if not roots and all_step_names:
            raise ValueError(
                "Circular dependency detected or no entry points found in the pipeline."
            )

        # 4. Cycle detection and reachability
        visited: Set[str] = set()
        path: Set[str] = set()

        def check_cycle(node: str) -> None:
            visited.add(node)
            path.add(node)

            targets = self._topology.get(node, []).copy()
            step = self._steps.get(node)
            if step:
                targets.extend(step.get_targets())

            for target in targets:
                if target in path:
                    raise ValueError(
                        f"Circular dependency detected involving '{node}' and '{target}'"
                    )
                if target not in visited:
                    check_cycle(target)

            path.remove(node)

        for root in roots:
            check_cycle(root)

        unvisited = all_step_names - visited
        if unvisited:
            raise ValueError(
                f"Unreachable steps detected (possibly a cycle without an entry point): {unvisited}"
            )
