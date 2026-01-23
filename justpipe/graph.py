from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Union

from justpipe.types import Stop, _resolve_name, StepConfig


def _validate_routing_target(target: Any) -> None:
    """Validate that a routing target is a valid name or callable."""
    if isinstance(target, str):
        pass
    elif isinstance(target, list):
        for t in target:
            _validate_routing_target(t)
    elif isinstance(target, dict):
        for t in target.values():
            if id(t) != id(Stop):
                _validate_routing_target(t)


class _DependencyGraph:
    """Encapsulates the pipeline topology, validation, and dependency tracking."""

    def __init__(
        self,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        step_configs: Dict[str, StepConfig],
    ):
        self._steps = steps
        self._topology = topology
        self._step_configs = step_configs
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
            for config in self._step_configs.values():
                all_targets.update(config.get_targets())

            roots = set(self._steps.keys()) - all_targets
            if not roots:
                roots = {next(iter(self._steps))}
            return roots
        return set()

    def get_successors(self, node: str) -> List[str]:
        return self._topology.get(node, [])

    def mark_completed(
        self, owner: str, succ: str
    ) -> tuple[bool, bool, Optional[float]]:
        """
        Mark a dependency as satisfied.
        Returns: (is_ready, cancel_timeout, schedule_timeout)
        """
        is_first = len(self._completed_parents[succ]) == 0
        self._completed_parents[succ].add(owner)
        parents_needed = self._parents_map[succ]

        is_ready = self._completed_parents[succ] >= parents_needed
        cancel_timeout = is_ready
        
        schedule_timeout = None
        if not is_ready and is_first and len(parents_needed) > 1:
            config = self._step_configs.get(succ)
            schedule_timeout = config.barrier_timeout if config else None

        return is_ready, cancel_timeout, schedule_timeout

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
        for step_name, config in self._step_configs.items():
            targets = config.get_targets()
            unknowns = [t for t in targets if t not in all_step_names]

            if not unknowns:
                referenced_names.update(targets)
                continue

            # Detailed error reporting for unknowns
            if config.map_target in unknowns:
                raise ValueError(
                    f"Step '{step_name}' (map) targets unknown step '{config.map_target}'"
                )

            if config.switch_default in unknowns:
                raise ValueError(
                    f"Step '{step_name}' (switch) has unknown default route '{config.switch_default}'"
                )

            if config.switch_routes and isinstance(config.switch_routes, dict):
                for route_name in config.switch_routes.values():
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
            config = self._step_configs.get(node)
            if config:
                targets.extend(config.get_targets())

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
