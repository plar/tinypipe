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
from justpipe.types import StepConfig


class PipelineASTBuilder:
    """Builds VisualAST from pipeline internals."""

    @classmethod
    def build(
        cls,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        step_configs: Dict[str, StepConfig],
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

        for config in step_configs.values():
            all_nodes.update(config.get_targets())

        # Remove special "Stop" marker if present
        all_nodes.discard("Stop")

        # Identify streaming nodes
        streaming_nodes = {
            name for name, func in steps.items() if inspect.isasyncgenfunction(func)
        }

        # Calculate all targets (nodes that are destinations)
        all_targets: Set[str] = set()
        for targets in topology.values():
            all_targets.update(targets)
        for config in step_configs.values():
            all_targets.update(config.get_targets())

        # Entry points: nodes that are in topology or steps but not targets
        entry_points = set(topology.keys()) - all_targets
        if not entry_points and topology:
            entry_points = {next(iter(topology.keys()))}
        elif not topology and steps:
            entry_points = set(steps.keys())

        # Terminal nodes: nodes that have no outgoing edges
        map_targets = {
            config.map_target
            for config in step_configs.values()
            if config.map_target
        }

        # Terminal nodes: nodes that have no outgoing edges
        non_terminal = set(topology.keys()) | {
            n for n, c in step_configs.items() if c.get_targets()
        }
        terminal_nodes = all_nodes - non_terminal

        # Isolated nodes: registered but not connected AND not entry points
        isolated_nodes = set(steps.keys()) - (non_terminal | all_targets | entry_points)

        # Generate safe IDs
        safe_ids = {name: f"n{i}" for i, name in enumerate(sorted(all_nodes))}

        # Build VisualNodes
        nodes: Dict[str, VisualNode] = {}
        for name in all_nodes:
            # Determine kind
            kind_str = step_configs[name].get_kind() if name in step_configs else "step"
            
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
            if kind == NodeKind.SUB:
                cfg = step_configs.get(name)
                sub_pipe = cfg.sub_pipeline_obj if cfg else None
                if sub_pipe:
                    # Recursive call to builder
                    sub_graph = cls.build(
                        sub_pipe._steps,
                        sub_pipe._topology,
                        sub_pipe._step_configs,
                    )
            
            # Reconstruct metadata for backward compatibility of visualization model
            node_metadata: Dict[str, Any] = {}
            if name in step_configs:
                # We can populate it if needed by visualization renderer
                pass

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
        for src, config in step_configs.items():
            if config.map_target:
                target = config.map_target
                edges.append(VisualEdge(source=src, target=target, is_map_edge=True))

            if config.switch_routes:
                routes = config.switch_routes
                if isinstance(routes, dict):
                    for val, target in routes.items():
                        if target != "Stop":
                            edges.append(
                                VisualEdge(source=src, target=target, label=str(val))
                            )

                default = config.switch_default
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
