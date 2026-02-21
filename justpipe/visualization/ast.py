"""Semantic AST model for pipeline visualization."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


from justpipe.types import BarrierType


class VisualNodeKind(Enum):
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
    kind: VisualNodeKind
    is_entry: bool = False
    is_terminal: bool = False
    is_isolated: bool = False
    is_map_target: bool = False
    barrier_type: BarrierType = BarrierType.ALL
    metadata: dict[str, Any] = field(default_factory=dict)
    sub_graph: "VisualAST | None" = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "is_entry": self.is_entry,
            "is_terminal": self.is_terminal,
            "is_isolated": self.is_isolated,
            "is_map_target": self.is_map_target,
            "barrier_type": self.barrier_type.value,
        }
        if self.sub_graph is not None:
            d["sub_graph"] = self.sub_graph.to_dict()
        return d


@dataclass
class VisualEdge:
    """Connection between nodes."""

    source: str
    target: str
    label: str | None = None
    is_map_edge: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source": self.source,
            "target": self.target,
            "is_map_edge": self.is_map_edge,
        }
        if self.label is not None:
            d["label"] = self.label
        return d


@dataclass
class ParallelGroup:
    """A group of nodes that execute in parallel."""

    id: str
    source_id: str
    node_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "node_ids": list(self.node_ids),
        }


@dataclass
class VisualAST:
    """Semantic representation of pipeline structure."""

    nodes: dict[str, VisualNode]
    edges: list[VisualEdge]
    parallel_groups: list[ParallelGroup]
    startup_hooks: list[str] = field(default_factory=list)
    shutdown_hooks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "parallel_groups": [g.to_dict() for g in self.parallel_groups],
            "startup_hooks": list(self.startup_hooks),
            "shutdown_hooks": list(self.shutdown_hooks),
        }
