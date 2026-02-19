"""Unit tests for pipeline hash computation."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from justpipe._internal.shared.pipeline_hash import compute_pipeline_hash


def _make_step(kind: str) -> MagicMock:
    step = MagicMock()
    step.get_kind.return_value = kind
    return step


class TestComputePipelineHash:
    def test_deterministic(self) -> None:
        steps = {"a": _make_step("step"), "b": _make_step("step")}
        topology: dict[str, list[str]] = {"a": ["b"]}
        h1 = compute_pipeline_hash("pipe", steps, topology)
        h2 = compute_pipeline_hash("pipe", steps, topology)
        assert h1 == h2

    @pytest.mark.parametrize(
        "name1, steps1, topo1, name2, steps2, topo2",
        [
            pytest.param(
                "pipe1", {"a": "step"}, {},
                "pipe2", {"a": "step"}, {},
                id="different_name",
            ),
            pytest.param(
                "pipe", {"a": "step"}, {},
                "pipe", {"b": "step"}, {},
                id="different_step_names",
            ),
            pytest.param(
                "pipe", {"a": "step"}, {},
                "pipe", {"a": "map"}, {},
                id="different_kind",
            ),
            pytest.param(
                "pipe", {"a": "step", "b": "step"}, {"a": ["b"]},
                "pipe", {"a": "step", "b": "step"}, {},
                id="different_topology",
            ),
            pytest.param(
                "pipe", {"a": "step"}, {},
                "pipe", {"a": "step", "b": "step"}, {},
                id="leaf_nodes_captured",
            ),
        ],
    )
    def test_different_inputs_produce_different_hash(
        self,
        name1: str,
        steps1: dict[str, str],
        topo1: dict[str, list[str]],
        name2: str,
        steps2: dict[str, str],
        topo2: dict[str, list[str]],
    ) -> None:
        s1 = {k: _make_step(v) for k, v in steps1.items()}
        s2 = {k: _make_step(v) for k, v in steps2.items()}
        h1 = compute_pipeline_hash(name1, s1, topo1)
        h2 = compute_pipeline_hash(name2, s2, topo2)
        assert h1 != h2

    def test_hash_length(self) -> None:
        steps = {"a": _make_step("step")}
        h = compute_pipeline_hash("pipe", steps, {})
        assert len(h) == 16

    def test_order_independent(self) -> None:
        """Hash should not depend on dict insertion order."""
        s1 = {"a": _make_step("step"), "b": _make_step("map")}
        s2 = {"b": _make_step("map"), "a": _make_step("step")}
        topology: dict[str, list[str]] = {"a": ["b"]}
        h1 = compute_pipeline_hash("pipe", s1, topology)
        h2 = compute_pipeline_hash("pipe", s2, topology)
        assert h1 == h2
