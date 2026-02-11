"""Unit tests for VisualAST and related data models."""

from justpipe.visualization import (
    VisualEdge,
    VisualNode,
    ParallelGroup,
    NodeKind,
)


def test_node_kind_enum() -> None:
    """Test NodeKind enum values."""
    assert NodeKind.STEP.value == "step"
    assert NodeKind.STREAMING.value == "streaming"
    assert NodeKind.MAP.value == "map"
    assert NodeKind.SWITCH.value == "switch"
    assert NodeKind.SUB.value == "sub"


def test_visual_node_defaults() -> None:
    """Test default values for VisualNode."""
    node = VisualNode(id="n0", name="test", kind=NodeKind.STEP)
    assert node.id == "n0"
    assert node.name == "test"
    assert node.kind == NodeKind.STEP
    assert not node.is_entry
    assert not node.is_terminal
    assert not node.is_isolated
    assert not node.is_map_target
    assert node.metadata == {}
    assert node.sub_graph is None


def test_visual_edge_defaults() -> None:
    """Test default values for VisualEdge."""
    edge = VisualEdge(source="a", target="b")
    assert edge.source == "a"
    assert edge.target == "b"
    assert edge.label is None
    assert not edge.is_map_edge


def test_visual_edge_with_label() -> None:
    """Test edge with label."""
    edge = VisualEdge(source="a", target="b", label="yes")
    assert edge.label == "yes"


def test_visual_edge_map() -> None:
    """Test map edge."""
    edge = VisualEdge(source="a", target="b", is_map_edge=True)
    assert edge.is_map_edge


def test_parallel_group() -> None:
    """Test ParallelGroup."""
    group = ParallelGroup(id="p1", source_id="src", node_ids=["a", "b"])
    assert group.id == "p1"
    assert group.source_id == "src"
    assert group.node_ids == ["a", "b"]
