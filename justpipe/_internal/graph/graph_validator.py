from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable
from typing import Any, NoReturn

from justpipe.types import (
    BarrierType,
    DefinitionError,
    PipelineValidationWarning,
)
from justpipe._internal.definition.steps import _BaseStep, _MapStep, _SwitchStep
from justpipe._internal.graph.dependency_graph import compute_roots
from justpipe._internal.shared.utils import _resolve_name, suggest_similar


class _GraphValidator:
    """Definition-time graph validator (stateless across runs)."""

    def __init__(
        self,
        steps: dict[str, _BaseStep],
        topology: dict[str, list[str]],
    ):
        self._steps = steps
        self._topology = topology

    def _raise_unknown_step(
        self,
        prefix: str,
        unknown: str,
        all_step_names: set[str],
        define_hint: str | None = None,
        fallback_hint: str | None = None,
    ) -> NoReturn:
        sorted_step_names = sorted(all_step_names)
        available_steps = ", ".join(sorted_step_names)
        error_msg = f"{prefix}{unknown}'. Available steps: {available_steps}. "
        suggestion = suggest_similar(unknown, all_step_names)
        if suggestion:
            error_msg += f"Did you mean '{suggestion}'? "
        elif fallback_hint:
            error_msg += fallback_hint
        if define_hint:
            error_msg += define_hint
        raise DefinitionError(error_msg)

    def _raise_or_warn(self, message: str, *, strict: bool) -> None:
        if strict:
            raise DefinitionError(message)
        warnings.warn(message, PipelineValidationWarning, stacklevel=3)

    def _targets_for(self, node: str) -> list[str]:
        targets = self._topology.get(node, []).copy()
        step = self._steps.get(node)
        if step:
            targets.extend(step.get_targets())
        return targets

    def _walk_reachable(
        self,
        roots: set[str],
        edges: dict[str, list[str]],
    ) -> set[str]:
        reachable: set[str] = set()
        stack: list[str] = list(roots)
        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)
            for target in edges.get(node, []):
                if target not in reachable:
                    stack.append(target)
        return reachable

    def _validate_start_scope_all_barriers(
        self,
        *,
        reachable_nodes: set[str],
        start_name: str,
        strict: bool,
    ) -> None:
        parents_map: dict[str, set[str]] = defaultdict(set)
        for parent, children in self._topology.items():
            for child in children:
                parents_map[child].add(parent)

        for node in sorted(reachable_nodes):
            parents = parents_map.get(node, set())
            if len(parents) <= 1:
                continue

            step = self._steps.get(node)
            barrier_type = step.barrier_type if step else BarrierType.ALL
            if barrier_type == BarrierType.ANY:
                continue

            missing_parents = parents - reachable_nodes
            if not missing_parents:
                continue

            all_parents = ", ".join(sorted(parents))
            missing = ", ".join(sorted(missing_parents))
            self._raise_or_warn(
                (
                    f"Step '{node}' requires ALL parents [{all_parents}], but "
                    f"run(start='{start_name}') cannot reach parent(s): {missing}. "
                    "This step will never execute in this run."
                ),
                strict=strict,
            )

    def validate(
        self,
        start: str | Callable[..., Any] | None = None,
        strict: bool = True,
        allow_multi_root: bool = False,
    ) -> None:
        """
        Validate the pipeline graph integrity.
        Raises:
            DefinitionError: if any unresolvable references or integrity issues are found.
        """
        if not self._steps:
            return

        referenced_names: set[str] = set()
        all_step_names = set(self._steps.keys())

        # 1. Check topology
        for parent, children in self._topology.items():
            for child in children:
                if child not in all_step_names:
                    self._raise_unknown_step(
                        prefix=f"Step '{parent}' targets unknown step '",
                        unknown=child,
                        all_step_names=all_step_names,
                        fallback_hint=(
                            f"Did you forget to define step '{child}' with @pipe.step()?"
                        ),
                    )
                referenced_names.add(child)

        # 2. Check special metadata (map_target, switch_routes)
        for step_name, step in self._steps.items():
            # Validation: Detect "Worker Trap" (Step used in map has ignored 'to' transitions)
            if isinstance(step, _MapStep):
                worker_step_name = step.each
                # Check if the worker step exists
                if worker_step_name in self._steps:
                    worker_transitions = self._topology.get(worker_step_name, [])
                    if worker_transitions:
                        raise DefinitionError(
                            f"Step '{worker_step_name}' defines transitions (to={worker_transitions}) but is used as a worker in map '{step_name}'. "
                            f"These transitions will be IGNORED by the runner.\n"
                            f"Options to fix:\n"
                            f"1. Remove 'to=' from '{worker_step_name}' and handle flow after the map.\n"
                            f"2. Use a sub-pipeline (@pipe.sub) if you need a sequence of steps per item."
                        )

            targets = step.get_targets()
            unknowns = [t for t in targets if t not in all_step_names]

            if not unknowns:
                referenced_names.update(targets)
                continue

            # Detailed error reporting for unknowns
            if isinstance(step, _MapStep) and step.each in unknowns:
                self._raise_unknown_step(
                    prefix=f"Step '{step_name}' (map) targets unknown step '",
                    unknown=step.each,
                    all_step_names=all_step_names,
                    define_hint=(
                        f"Define step '{step.each}' with @pipe.step() before using it in map."
                    ),
                )

            if isinstance(step, _SwitchStep):
                if step.default in unknowns:
                    self._raise_unknown_step(
                        prefix=f"Step '{step_name}' (switch) has unknown default route '",
                        unknown=step.default,
                        all_step_names=all_step_names,
                        define_hint=(
                            f"Define step '{step.default}' or fix the default parameter."
                        ),
                    )

                if step.to and isinstance(step.to, dict):
                    for route_name in step.to.values():
                        if isinstance(route_name, str) and route_name in unknowns:
                            self._raise_unknown_step(
                                prefix=f"Step '{step_name}' (switch) routes to unknown step '",
                                unknown=route_name,
                                all_step_names=all_step_names,
                                define_hint=(
                                    f"Define step '{route_name}' or fix the routes dictionary."
                                ),
                            )

        # 3. Detect roots (entry points)
        roots = compute_roots(self._steps, self._topology)
        if not roots and all_step_names and start is None:
            raise DefinitionError(
                "Circular dependency detected or no entry points found in the pipeline. "
                "Every step has a parent, creating a cycle. "
                "Remove one 'to=' edge to create an entry point, or specify start= in run()."
            )

        if start is not None:
            start_name = _resolve_name(start)
            if start_name not in all_step_names:
                self._raise_unknown_step(
                    prefix="run(start=...) references unknown step '",
                    unknown=start_name,
                    all_step_names=all_step_names,
                    fallback_hint=(
                        "Check the provided start step name or pass a registered callable."
                    ),
                )
            traversal_roots = {start_name}
        else:
            start_name = None
            traversal_roots = roots

        if start is None and len(roots) > 1:
            sorted_roots = ", ".join(sorted(roots))
            if strict and not allow_multi_root:
                raise DefinitionError(
                    f"Multiple root steps detected: {sorted_roots}. "
                    "run() without an explicit start schedules all roots concurrently, "
                    "so root execution order is non-deterministic. "
                    "Pass start=... or set allow_multi_root=True to opt in."
                )
            if not strict:
                self._raise_or_warn(
                    (
                        f"Multiple root steps detected: {sorted_roots}. "
                        "run() without an explicit start schedules all roots concurrently, "
                        "so root execution order is non-deterministic."
                    ),
                    strict=False,
                )

        # 4. Cycle detection and reachability
        visited: set[str] = set()
        path_stack: list[str] = []
        path_members: set[str] = set()

        def check_cycle(node: str) -> None:
            visited.add(node)
            path_stack.append(node)
            path_members.add(node)

            for target in self._targets_for(node):
                if target in path_members:
                    cycle_start = path_stack.index(target)
                    cycle_nodes = path_stack[cycle_start:] + [target]
                    cycle_path = " -> ".join(cycle_nodes)
                    raise DefinitionError(
                        f"Circular dependency detected: {cycle_path}. "
                        f"Remove one of these edges to break the cycle."
                    )
                if target not in visited:
                    check_cycle(target)

            path_stack.pop()
            path_members.remove(node)

        for root in traversal_roots:
            check_cycle(root)

        if start is None:
            unvisited = all_step_names - visited
            if unvisited:
                unreachable_list = ", ".join(sorted(unvisited))
                raise DefinitionError(
                    f"Unreachable steps detected: {unreachable_list}. "
                    f"These steps are not connected to any entry point. "
                    f"Add 'to=' parameters to connect them or remove them if unused."
                )

        if start_name is not None:
            reachable_from_start = self._walk_reachable(traversal_roots, self._topology)
            self._validate_start_scope_all_barriers(
                reachable_nodes=reachable_from_start,
                start_name=start_name,
                strict=strict,
            )
