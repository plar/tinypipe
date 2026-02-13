"""Unit tests for pipeline hash computation."""

from __future__ import annotations

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

    def test_different_name_different_hash(self) -> None:
        steps = {"a": _make_step("step")}
        topology: dict[str, list[str]] = {}
        h1 = compute_pipeline_hash("pipe1", steps, topology)
        h2 = compute_pipeline_hash("pipe2", steps, topology)
        assert h1 != h2

    def test_different_step_names_different_hash(self) -> None:
        steps1 = {"a": _make_step("step")}
        steps2 = {"b": _make_step("step")}
        topology: dict[str, list[str]] = {}
        h1 = compute_pipeline_hash("pipe", steps1, topology)
        h2 = compute_pipeline_hash("pipe", steps2, topology)
        assert h1 != h2

    def test_different_kind_different_hash(self) -> None:
        steps1 = {"a": _make_step("step")}
        steps2 = {"a": _make_step("map")}
        topology: dict[str, list[str]] = {}
        h1 = compute_pipeline_hash("pipe", steps1, topology)
        h2 = compute_pipeline_hash("pipe", steps2, topology)
        assert h1 != h2

    def test_different_topology_different_hash(self) -> None:
        steps = {"a": _make_step("step"), "b": _make_step("step")}
        t1: dict[str, list[str]] = {"a": ["b"]}
        t2: dict[str, list[str]] = {}
        h1 = compute_pipeline_hash("pipe", steps, t1)
        h2 = compute_pipeline_hash("pipe", steps, t2)
        assert h1 != h2

    def test_leaf_nodes_captured(self) -> None:
        """Leaf nodes without edges should still affect the hash."""
        steps1 = {"a": _make_step("step")}
        steps2 = {"a": _make_step("step"), "b": _make_step("step")}
        topology: dict[str, list[str]] = {}
        h1 = compute_pipeline_hash("pipe", steps1, topology)
        h2 = compute_pipeline_hash("pipe", steps2, topology)
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
