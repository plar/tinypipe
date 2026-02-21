"""Unit tests for pipeline hash computation."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from justpipe._internal.shared.pipeline_hash import compute_pipeline_hash
from justpipe.types import NodeKind


def _make_step(kind: NodeKind) -> MagicMock:
    step = MagicMock()
    step.get_kind.return_value = kind
    return step


class TestComputePipelineHash:
    def test_deterministic(self) -> None:
        steps = {"a": _make_step(NodeKind.STEP), "b": _make_step(NodeKind.STEP)}
        topology: dict[str, list[str]] = {"a": ["b"]}
        h1 = compute_pipeline_hash("pipe", steps, topology)
        h2 = compute_pipeline_hash("pipe", steps, topology)
        assert h1 == h2

    @pytest.mark.parametrize(
        "name1, steps1, topo1, name2, steps2, topo2",
        [
            pytest.param(
                "pipe1",
                {"a": NodeKind.STEP},
                {},
                "pipe2",
                {"a": NodeKind.STEP},
                {},
                id="different_name",
            ),
            pytest.param(
                "pipe",
                {"a": NodeKind.STEP},
                {},
                "pipe",
                {"b": NodeKind.STEP},
                {},
                id="different_step_names",
            ),
            pytest.param(
                "pipe",
                {"a": NodeKind.STEP},
                {},
                "pipe",
                {"a": NodeKind.MAP},
                {},
                id="different_kind",
            ),
            pytest.param(
                "pipe",
                {"a": NodeKind.STEP, "b": NodeKind.STEP},
                {"a": ["b"]},
                "pipe",
                {"a": NodeKind.STEP, "b": NodeKind.STEP},
                {},
                id="different_topology",
            ),
            pytest.param(
                "pipe",
                {"a": NodeKind.STEP},
                {},
                "pipe",
                {"a": NodeKind.STEP, "b": NodeKind.STEP},
                {},
                id="leaf_nodes_captured",
            ),
        ],
    )
    def test_different_inputs_produce_different_hash(
        self,
        name1: str,
        steps1: dict[str, NodeKind],
        topo1: dict[str, list[str]],
        name2: str,
        steps2: dict[str, NodeKind],
        topo2: dict[str, list[str]],
    ) -> None:
        s1 = {k: _make_step(v) for k, v in steps1.items()}
        s2 = {k: _make_step(v) for k, v in steps2.items()}
        h1 = compute_pipeline_hash(name1, s1, topo1)
        h2 = compute_pipeline_hash(name2, s2, topo2)
        assert h1 != h2

    def test_hash_length(self) -> None:
        steps = {"a": _make_step(NodeKind.STEP)}
        h = compute_pipeline_hash("pipe", steps, {})
        assert len(h) == 16

    def test_order_independent(self) -> None:
        """Hash should not depend on dict insertion order."""
        s1 = {"a": _make_step(NodeKind.STEP), "b": _make_step(NodeKind.MAP)}
        s2 = {"b": _make_step(NodeKind.MAP), "a": _make_step(NodeKind.STEP)}
        topology: dict[str, list[str]] = {"a": ["b"]}
        h1 = compute_pipeline_hash("pipe", s1, topology)
        h2 = compute_pipeline_hash("pipe", s2, topology)
        assert h1 == h2
