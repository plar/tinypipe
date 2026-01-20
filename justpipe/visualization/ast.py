"""Semantic AST model for pipeline visualization."""

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class NodeKind(Enum):
    """Kind of pipeline node."""

    STEP = "step"
    STREAMING = "streaming"
    MAP = "map"
    SWITCH = "switch"
    SUB = "sub"


@dataclass
class VisualNode:
    """A single step in the pipeline."""

    id: str
    name: str
    kind: NodeKind
    is_entry: bool = False
    is_terminal: bool = False
    is_isolated: bool = False
    is_map_target: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    sub_graph: Optional["VisualAST"] = None


@dataclass
class VisualEdge:
    """Connection between nodes."""

    source: str
    target: str
    label: Optional[str] = None
    is_map_edge: bool = False


@dataclass
class ParallelGroup:
    """A group of nodes that execute in parallel."""

    id: str
    source_id: str
    node_ids: List[str]


@dataclass
class VisualAST:
    """Semantic representation of pipeline structure."""

    nodes: Dict[str, VisualNode]
    edges: List[VisualEdge]
    parallel_groups: List[ParallelGroup]
    startup_hooks: List[str] = field(default_factory=list)
    shutdown_hooks: List[str] = field(default_factory=list)

    @classmethod
    def from_pipe(
        cls,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        step_metadata: Dict[str, Dict[str, Any]],
        startup_hooks: Optional[List[Callable[..., Any]]] = None,
        shutdown_hooks: Optional[List[Callable[..., Any]]] = None,
    ) -> "VisualAST":
        """Build AST from Pipe internals."""
        # Collect hook names
        startup_names = [h.__name__ for h in (startup_hooks or [])]
        shutdown_names = [h.__name__ for h in (shutdown_hooks or [])]

        # Collect all nodes
        all_nodes: Set[str] = set(steps.keys())
        for targets in topology.values():
            all_nodes.update(targets)

        for meta in step_metadata.values():
            if "map_target" in meta:
                all_nodes.add(meta["map_target"])
            if "switch_routes" in meta and isinstance(meta["switch_routes"], dict):
                all_nodes.update(meta["switch_routes"].values())
            if "switch_default" in meta and meta["switch_default"]:
                all_nodes.add(meta["switch_default"])

        # Remove special "Stop" marker if present
        all_nodes.discard("Stop")

        # Identify streaming nodes
        streaming_nodes = {
            name for name, func in steps.items() if inspect.isasyncgenfunction(func)
        }

        # Identify switch nodes
        switch_nodes = {
            name for name, meta in step_metadata.items() if "switch_routes" in meta
        }

        # Identify sub-pipeline nodes
        sub_nodes = {
            name for name, meta in step_metadata.items() if "sub_pipeline" in meta
        }

        # Identify map nodes
        map_nodes = {
            name for name, meta in step_metadata.items() if "map_target" in meta
        }

        # Identify nodes that are targets of a map operation
        map_targets = {
            meta["map_target"] for meta in step_metadata.values() if "map_target" in meta
        }

        # Calculate all targets (nodes that are destinations)
        all_targets: Set[str] = set()
        for targets in topology.values():
            all_targets.update(targets)
        for meta in step_metadata.values():
            if "map_target" in meta:
                all_targets.add(meta["map_target"])
            if "switch_routes" in meta and isinstance(meta["switch_routes"], dict):
                all_targets.update(
                    t for t in meta["switch_routes"].values() if t != "Stop"
                )
            if "switch_default" in meta and meta["switch_default"]:
                all_targets.add(meta["switch_default"])

        # Entry points: nodes that are in topology or steps but not targets
        entry_points = set(topology.keys()) - all_targets
        if not entry_points and topology:
            entry_points = {next(iter(topology.keys()))}
        elif not topology and steps:
            entry_points = set(steps.keys())

        # Terminal nodes: nodes that have no outgoing edges
        non_terminal = set(topology.keys()) | {
            n
            for n, m in step_metadata.items()
            if "map_target" in m or "switch_routes" in m
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
            if name in switch_nodes:
                kind = NodeKind.SWITCH
            elif name in sub_nodes:
                kind = NodeKind.SUB
            elif name in map_nodes:
                kind = NodeKind.MAP
            elif name in streaming_nodes:
                kind = NodeKind.STREAMING
            else:
                kind = NodeKind.STEP

            sub_graph = None
            if kind == NodeKind.SUB:
                sub_pipe = step_metadata.get(name, {}).get("sub_pipeline_obj")
                if sub_pipe:
                    sub_graph = cls.from_pipe(
                        sub_pipe._steps,
                        sub_pipe._topology,
                        sub_pipe._step_metadata,
                    )

            nodes[name] = VisualNode(
                id=safe_ids[name],
                name=name,
                kind=kind,
                is_entry=name in entry_points,
                is_terminal=name in terminal_nodes,
                is_isolated=name in isolated_nodes,
                is_map_target=name in map_targets,
                metadata=step_metadata.get(name, {}),
                sub_graph=sub_graph,
            )

        # Build edges
        edges: List[VisualEdge] = []

        # Regular topology edges
        for src, targets in topology.items():
            for target in targets:
                edges.append(VisualEdge(source=src, target=target))

        # Map and switch edges from metadata
        for src, meta in step_metadata.items():
            if "map_target" in meta:
                target = meta["map_target"]
                edges.append(VisualEdge(source=src, target=target, is_map_edge=True))

            if "switch_routes" in meta:
                routes = meta["switch_routes"]
                if isinstance(routes, dict):
                    for val, target in routes.items():
                        if target != "Stop":
                            edges.append(
                                VisualEdge(source=src, target=target, label=str(val))
                            )

                default = meta.get("switch_default")
                if default:
                    edges.append(VisualEdge(source=src, target=default, label="default"))

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

        return cls(
            nodes=nodes,
            edges=edges,
            parallel_groups=parallel_groups,
            startup_hooks=startup_names,
            shutdown_hooks=shutdown_names,
        )
