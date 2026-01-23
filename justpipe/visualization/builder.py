"""Builder for VisualAST from pipeline structure."""

import inspect
from typing import Any, Callable, Dict, List, Optional, Set

from justpipe.visualization.ast import (
    NodeKind,
    ParallelGroup,
    VisualAST,
    VisualEdge,
    VisualNode,
)
from justpipe.steps import _BaseStep, _MapStep, _SwitchStep, _SubPipelineStep


class _PipelineASTBuilder:
    """Builds VisualAST from pipeline internals."""

    @classmethod
    def build(
        cls,
        steps: Dict[str, _BaseStep],
        topology: Dict[str, List[str]],
        startup_hooks: Optional[List[Callable[..., Any]]] = None,
        shutdown_hooks: Optional[List[Callable[..., Any]]] = None,
    ) -> VisualAST:
        """Build AST from Pipe internals."""
        # Collect hook names
        startup_names = [h.__name__ for h in (startup_hooks or [])]
        shutdown_names = [h.__name__ for h in (shutdown_hooks or [])]

        # Collect all nodes
        all_nodes: Set[str] = set(steps.keys())
        for targets in topology.values():
            all_nodes.update(targets)

        for step_obj in steps.values():
            all_nodes.update(step_obj.get_targets())

        # Remove special "Stop" marker if present
        all_nodes.discard("Stop")

        # Identify streaming nodes
        streaming_nodes = {
            name for name, s in steps.items() 
            if inspect.isasyncgenfunction(s.original_func)
        }

        # Calculate all targets (nodes that are destinations)
        all_targets: Set[str] = set()
        for targets in topology.values():
            all_targets.update(targets)
        for step_obj in steps.values():
            all_targets.update(step_obj.get_targets())

        # Entry points: nodes that are in topology or steps but not targets
        entry_points = set(topology.keys()) - all_targets
        if not entry_points and topology:
            entry_points = {next(iter(topology.keys()))}
        elif not topology and steps:
            entry_points = set(steps.keys())

        # Terminal nodes: nodes that have no outgoing edges
        map_targets = {
            step_obj.map_target
            for step_obj in steps.values()
            if isinstance(step_obj, _MapStep)
        }

        # Terminal nodes: nodes that have no outgoing edges
        non_terminal = set(topology.keys()) | {
            n for n, step_obj in steps.items() if step_obj.get_targets()
        }
        terminal_nodes = all_nodes - non_terminal

        # Isolated nodes: registered but not connected AND not entry points
        isolated_nodes = set(steps.keys()) - (non_terminal | all_targets | entry_points)

        # Generate safe IDs
        safe_ids = {name: f"n{i}" for i, name in enumerate(sorted(all_nodes))}

        # Build VisualNodes
        nodes: Dict[str, VisualNode] = {}
        for name in all_nodes:
            step: Optional[_BaseStep] = steps.get(name)
            
            # Determine kind
            kind_str = step.get_kind() if step else "step"
            
            if kind_str == "switch":
                kind = NodeKind.SWITCH
            elif kind_str == "sub":
                kind = NodeKind.SUB
            elif kind_str == "map":
                kind = NodeKind.MAP
            elif name in streaming_nodes:
                kind = NodeKind.STREAMING
            else:
                kind = NodeKind.STEP

            sub_graph = None
            if isinstance(step, _SubPipelineStep):
                sub_pipe = step.sub_pipeline_obj
                if sub_pipe:
                    sub_graph = cls.build(
                        sub_pipe._steps,
                        sub_pipe._topology,
                    )
            
            node_metadata: Dict[str, Any] = {}

            nodes[name] = VisualNode(
                id=safe_ids[name],
                name=name,
                kind=kind,
                is_entry=name in entry_points,
                is_terminal=name in terminal_nodes,
                is_isolated=name in isolated_nodes,
                is_map_target=name in map_targets,
                metadata=node_metadata,
                sub_graph=sub_graph,
            )

        # Build edges
        edges: List[VisualEdge] = []

        # Regular topology edges
        for src, targets in topology.items():
            for target in targets:
                edges.append(VisualEdge(source=src, target=target))

        # Map and switch edges from metadata
        for src, step_obj in steps.items():
            if isinstance(step_obj, _MapStep):
                target = step_obj.map_target
                edges.append(VisualEdge(source=src, target=target, is_map_edge=True))

            if isinstance(step_obj, _SwitchStep):
                if isinstance(step_obj.routes, dict):
                    for val, target in step_obj.routes.items():
                        if target != "Stop":
                            edges.append(
                                VisualEdge(source=src, target=target, label=str(val))
                            )

                default = step_obj.default
                if default:
                    edges.append(
                        VisualEdge(source=src, target=default, label="default")
                    )

        # Build parallel groups
        parallel_groups: List[ParallelGroup] = []
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
