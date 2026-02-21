"""Builder for VisualAST from pipeline structure."""

import ast
import inspect
import textwrap
from typing import Any
from collections.abc import Callable

from justpipe.visualization.ast import (
    VisualNodeKind,
    ParallelGroup,
    VisualAST,
    VisualEdge,
    VisualNode,
)
from justpipe._internal.definition.steps import (
    _BaseStep,
    _MapStep,
    _SwitchStep,
    _SubPipelineStep,
)
from justpipe.types import BarrierType, NodeKind

_VIS_KIND: dict[NodeKind, VisualNodeKind] = {
    NodeKind.MAP: VisualNodeKind.MAP,
    NodeKind.SWITCH: VisualNodeKind.SWITCH,
    NodeKind.SUB: VisualNodeKind.SUB,
}


class _PipelineASTBuilder:
    """Builds VisualAST from pipeline internals."""

    @classmethod
    def build(
        cls,
        steps: dict[str, _BaseStep],
        topology: dict[str, list[str]],
        startup_hooks: list[Callable[..., Any]] | None = None,
        shutdown_hooks: list[Callable[..., Any]] | None = None,
    ) -> VisualAST:
        """Build AST from Pipe internals."""
        # Collect hook names
        startup_names = [h.__name__ for h in (startup_hooks or [])]
        shutdown_names = [h.__name__ for h in (shutdown_hooks or [])]

        # Calculate all targets (nodes that are destinations)
        all_targets: set[str] = set()
        for targets in topology.values():
            all_targets.update(targets)
        for step_obj in steps.values():
            all_targets.update(step_obj.get_targets())

        # Collect all nodes (step definitions + targets)
        all_nodes = set(steps.keys()) | all_targets
        all_nodes.discard("Stop")

        # Identify streaming nodes
        streaming_nodes = {
            name
            for name, s in steps.items()
            if inspect.isasyncgenfunction(s._original_func)
        }

        # Entry points: nodes that are in topology or steps but not targets
        entry_points = set(topology.keys()) - all_targets
        if not entry_points and topology:
            entry_points = {next(iter(topology.keys()))}
        elif not topology and steps:
            entry_points = set(steps.keys())

        map_targets = {
            step_obj.each
            for step_obj in steps.values()
            if isinstance(step_obj, _MapStep)
        }

        # Terminal nodes: nodes that have no outgoing edges
        # Map targets are managed by the map step's barrier, not standalone terminals
        non_terminal = set(topology.keys()) | {
            n for n, step_obj in steps.items() if step_obj.get_targets()
        }
        terminal_nodes = all_nodes - non_terminal - map_targets

        # Isolated nodes: registered but not connected AND not entry points
        isolated_nodes = set(steps.keys()) - (non_terminal | all_targets | entry_points)

        # Generate safe IDs
        safe_ids = {name: f"n{i}" for i, name in enumerate(sorted(all_nodes))}

        # Build VisualNodes
        nodes: dict[str, VisualNode] = {}
        for name in all_nodes:
            step: _BaseStep | None = steps.get(name)

            # Determine kind
            types_kind = step.get_kind() if step else NodeKind.STEP
            if name in streaming_nodes and types_kind == NodeKind.STEP:
                kind = VisualNodeKind.STREAMING
            else:
                kind = _VIS_KIND.get(types_kind, VisualNodeKind.STEP)

            sub_graph = None
            if isinstance(step, _SubPipelineStep):
                sub_pipe = step.pipeline
                if sub_pipe:
                    sub_graph = cls.build(
                        sub_pipe._steps,
                        sub_pipe._topology,
                    )

            nodes[name] = VisualNode(
                id=safe_ids[name],
                name=name,
                kind=kind,
                is_entry=name in entry_points,
                is_terminal=name in terminal_nodes,
                is_isolated=name in isolated_nodes,
                is_map_target=name in map_targets,
                barrier_type=step.barrier_type if step else BarrierType.ALL,
                sub_graph=sub_graph,
            )

        # Build edges
        edges: list[VisualEdge] = []

        # Regular topology edges
        for src, targets in topology.items():
            for target in targets:
                edges.append(VisualEdge(source=src, target=target))

        # Map and switch edges from metadata
        for src, step_obj in steps.items():
            if isinstance(step_obj, _MapStep):
                target = step_obj.each
                edges.append(VisualEdge(source=src, target=target, is_map_edge=True))

            if isinstance(step_obj, _SwitchStep):
                if isinstance(step_obj.to, dict):
                    for val, route_target in step_obj.to.items():
                        if isinstance(route_target, str):
                            edges.append(
                                VisualEdge(
                                    source=src, target=route_target, label=str(val)
                                )
                            )

                default = step_obj.default
                if default:
                    edges.append(
                        VisualEdge(source=src, target=default, label="default")
                    )

        # Analyze function bodies for dynamic returns
        for name, step_obj in steps.items():
            if hasattr(step_obj, "_original_func"):
                dynamic_targets = cls._find_dynamic_returns(
                    step_obj._original_func, all_nodes
                )
                for target in dynamic_targets:
                    # Avoid duplicates if already explicitly connected (though label differs)
                    existing = any(
                        e.source == name and e.target == target for e in edges
                    )
                    if not existing:
                        edges.append(
                            VisualEdge(source=name, target=target, label="dynamic")
                        )

        # Build parallel groups
        parallel_groups: list[ParallelGroup] = []
        for src, targets in topology.items():
            if len(targets) > 1:
                parallel_groups.append(
                    ParallelGroup(
                        id=f"parallel_{safe_ids[src]}",
                        source_id=src,
                        node_ids=list(targets),
                    )
                )

        return VisualAST(
            nodes=nodes,
            edges=edges,
            parallel_groups=parallel_groups,
            startup_hooks=startup_names,
            shutdown_hooks=shutdown_names,
        )

    @staticmethod
    def _find_dynamic_returns(
        func: Callable[..., Any], known_steps: set[str]
    ) -> set[str]:
        """Parse function source to find return "step_name" statements."""
        try:
            source = inspect.getsource(func)
            # Dedent is crucial for inner functions
            source = textwrap.dedent(source)
            tree = ast.parse(source)
        except (OSError, TypeError, SyntaxError):
            # Source not available or not parseable
            return set()

        dynamic_targets: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Return):
                # Check for return "literal_string"
                if isinstance(node.value, ast.Constant):
                    constant_val = node.value.value
                    if isinstance(constant_val, str) and constant_val in known_steps:
                        dynamic_targets.add(str(constant_val))

        return dynamic_targets
