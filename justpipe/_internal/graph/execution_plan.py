from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from justpipe._internal.definition.steps import _BaseStep
from justpipe.types import InjectionMetadataMap
from justpipe._internal.graph.dependency_graph import _DependencyGraph


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Immutable execution plan built from the registry."""

    steps: dict[str, _BaseStep]
    topology: dict[str, list[str]]
    injection_metadata: InjectionMetadataMap
    roots: set[str]
    parents_map: dict[str, set[str]]


def compile_execution_plan(
    steps: Mapping[str, _BaseStep],
    topology: Mapping[str, list[str]],
    injection_metadata: InjectionMetadataMap,
) -> tuple[ExecutionPlan, _DependencyGraph]:
    """Compile an immutable execution plan and runtime graph in one pass."""
    steps_snapshot = dict(steps)
    topology_snapshot = dict(topology)
    injection_snapshot = dict(injection_metadata)

    graph = _DependencyGraph(steps_snapshot, topology_snapshot)
    graph.build()

    plan = ExecutionPlan(
        steps=steps_snapshot,
        topology=topology_snapshot,
        injection_metadata=injection_snapshot,
        roots=graph.get_roots(),
        parents_map=graph.parents_map_snapshot(),
    )
    return plan, graph
