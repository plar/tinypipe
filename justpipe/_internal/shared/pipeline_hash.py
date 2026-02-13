"""Deterministic pipeline identity hash."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep


def compute_pipeline_hash(
    name: str,
    steps: Mapping[str, _BaseStep],
    topology: Mapping[str, list[str]],
) -> str:
    """Deterministic hash from pipeline name + step names/kinds + sorted edge list.

    Includes step names AND kinds (not just edges):
    - Leaf nodes without edges are captured (via step_info)
    - Converting a step to a map changes the hash (kind changes)
    - Renaming a step changes the hash (step_info changes)
    """
    step_info = sorted(
        [step_name, step.get_kind()] for step_name, step in steps.items()
    )
    edges = sorted([src, dst] for src, dsts in topology.items() for dst in dsts)
    content = json.dumps(
        {"name": name, "steps": step_info, "edges": edges}, sort_keys=True
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]
