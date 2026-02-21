"""Unit tests for VisualAST and related data models."""

from justpipe.visualization import (
    VisualEdge,
    VisualNode,
    ParallelGroup,
    VisualNodeKind,
)


def test_node_kind_enum() -> None:
    """Test VisualNodeKind enum values."""
    assert VisualNodeKind.STEP.value == "step"
    assert VisualNodeKind.STREAMING.value == "streaming"
    assert VisualNodeKind.MAP.value == "map"
    assert VisualNodeKind.SWITCH.value == "switch"
    assert VisualNodeKind.SUB.value == "sub"


def test_visual_node_defaults() -> None:
    """Test default values for VisualNode."""
    node = VisualNode(id="n0", name="test", kind=VisualNodeKind.STEP)
    assert node.id == "n0"
    assert node.name == "test"
    assert node.kind == VisualNodeKind.STEP
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
