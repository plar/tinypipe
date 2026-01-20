"""Unit tests for VisualAST and related models."""

from typing import Any
from justpipe.visualization import (
    VisualAST,
    VisualNode,
    VisualEdge,
    ParallelGroup,
    NodeKind,
    MermaidRenderer,
    MermaidTheme,
)


def test_node_kind_enum() -> None:
    """Test NodeKind enum values."""
    assert NodeKind.STEP.value == "step"
    assert NodeKind.STREAMING.value == "streaming"
    assert NodeKind.MAP.value == "map"
    assert NodeKind.SWITCH.value == "switch"


def test_visual_node_defaults() -> None:
    """Test VisualNode default values."""
    node = VisualNode(id="n0", name="test", kind=NodeKind.STEP)
    assert node.id == "n0"
    assert node.name == "test"
    assert node.kind == NodeKind.STEP
    assert node.is_entry is False
    assert node.is_terminal is False
    assert node.is_isolated is False
    assert node.metadata == {}


def test_visual_edge_defaults() -> None:
    """Test VisualEdge default values."""
    edge = VisualEdge(source="a", target="b")
    assert edge.source == "a"
    assert edge.target == "b"
    assert edge.label is None
    assert edge.is_map_edge is False


def test_visual_edge_with_label() -> None:
    """Test VisualEdge with label."""
    edge = VisualEdge(source="a", target="b", label="yes")
    assert edge.label == "yes"
    assert edge.is_map_edge is False


def test_visual_edge_map() -> None:
    """Test VisualEdge for map connections."""
    edge = VisualEdge(source="a", target="b", is_map_edge=True)
    assert edge.is_map_edge is True


def test_parallel_group() -> None:
    """Test ParallelGroup dataclass."""
    group = ParallelGroup(id="parallel_n0", source_id="a", node_ids=["b", "c"])
    assert group.id == "parallel_n0"
    assert group.source_id == "a"
    assert group.node_ids == ["b", "c"]


def test_ast_from_empty_pipe() -> None:
    """Test building AST from empty pipe."""
    ast = VisualAST.from_pipe({}, {}, {})
    assert ast.nodes == {}
    assert ast.edges == []
    assert ast.parallel_groups == []


def test_ast_from_single_step() -> None:
    """Test building AST from single step."""

    async def step_a(s: Any) -> None:
        pass

    steps = {"a": step_a}
    topology: dict[str, list[str]] = {}
    metadata: dict[str, dict[str, Any]] = {}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert len(ast.nodes) == 1
    assert "a" in ast.nodes
    node = ast.nodes["a"]
    assert node.name == "a"
    assert node.kind == NodeKind.STEP
    assert node.is_entry is True
    assert node.is_terminal is True
    assert node.is_isolated is False


def test_ast_from_linear_pipe() -> None:
    """Test building AST from linear pipeline."""

    async def step_a(s: Any) -> None:
        pass

    async def step_b(s: Any) -> None:
        pass

    steps = {"a": step_a, "b": step_b}
    topology = {"a": ["b"]}
    metadata: dict[str, dict[str, Any]] = {}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert len(ast.nodes) == 2
    assert ast.nodes["a"].is_entry is True
    assert ast.nodes["a"].is_terminal is False
    assert ast.nodes["b"].is_entry is False
    assert ast.nodes["b"].is_terminal is True

    assert len(ast.edges) == 1
    assert ast.edges[0].source == "a"
    assert ast.edges[0].target == "b"


def test_ast_streaming_node() -> None:
    """Test that streaming steps are identified correctly."""

    async def regular(s: Any) -> None:
        pass

    async def streaming(s: Any) -> Any:
        yield 1

    steps = {"regular": regular, "streaming": streaming}
    topology = {"regular": ["streaming"]}
    metadata: dict[str, dict[str, Any]] = {}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert ast.nodes["regular"].kind == NodeKind.STEP
    assert ast.nodes["streaming"].kind == NodeKind.STREAMING


def test_ast_parallel_group() -> None:
    """Test that parallel branches create groups."""

    async def step_a(s: Any) -> None:
        pass

    async def step_b(s: Any) -> None:
        pass

    async def step_c(s: Any) -> None:
        pass

    steps = {"a": step_a, "b": step_b, "c": step_c}
    topology = {"a": ["b", "c"]}
    metadata: dict[str, dict[str, Any]] = {}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert len(ast.parallel_groups) == 1
    group = ast.parallel_groups[0]
    assert set(group.node_ids) == {"b", "c"}
    assert group.source_id == "a"


def test_ast_map_metadata() -> None:
    """Test that map steps are identified from metadata."""

    async def mapper(s: Any) -> None:
        pass

    async def worker(item: Any) -> None:
        pass

    steps = {"mapper": mapper, "worker": worker}
    topology: dict[str, list[str]] = {}
    metadata = {"mapper": {"map_target": "worker"}}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert ast.nodes["mapper"].kind == NodeKind.MAP
    # Check map edge
    map_edges = [e for e in ast.edges if e.is_map_edge]
    assert len(map_edges) == 1
    assert map_edges[0].source == "mapper"
    assert map_edges[0].target == "worker"


def test_ast_switch_metadata() -> None:
    """Test that switch steps are identified from metadata."""

    async def router(s: Any) -> None:
        pass

    async def handler_a(s: Any) -> None:
        pass

    async def handler_b(s: Any) -> None:
        pass

    steps = {"router": router, "handler_a": handler_a, "handler_b": handler_b}
    topology: dict[str, list[str]] = {}
    metadata = {
        "router": {
            "switch_routes": {"yes": "handler_a", "no": "handler_b"},
            "switch_default": None,
        }
    }

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert ast.nodes["router"].kind == NodeKind.SWITCH
    # Check labeled edges
    labeled_edges = [e for e in ast.edges if e.label]
    assert len(labeled_edges) == 2
    labels = {e.label for e in labeled_edges}
    assert labels == {"yes", "no"}


def test_ast_switch_with_default() -> None:
    """Test switch with default route."""

    async def router(s: Any) -> None:
        pass

    async def handler(s: Any) -> None:
        pass

    async def fallback(s: Any) -> None:
        pass

    steps = {"router": router, "handler": handler, "fallback": fallback}
    topology: dict[str, list[str]] = {}
    metadata = {
        "router": {
            "switch_routes": {"yes": "handler"},
            "switch_default": "fallback",
        }
    }

    ast = VisualAST.from_pipe(steps, topology, metadata)

    labeled_edges = [e for e in ast.edges if e.label]
    labels = {e.label for e in labeled_edges}
    assert "default" in labels


def test_ast_isolated_node() -> None:
    """Test isolated nodes are identified."""

    async def main(s: Any) -> None:
        pass

    async def orphan(s: Any) -> None:
        pass

    async def leaf(s: Any) -> None:
        pass

    steps = {"main": main, "orphan": orphan, "leaf": leaf}
    topology = {"main": ["leaf"]}
    metadata: dict[str, dict[str, Any]] = {}

    ast = VisualAST.from_pipe(steps, topology, metadata)

    assert ast.nodes["orphan"].is_isolated is True
    assert ast.nodes["main"].is_isolated is False
    assert ast.nodes["leaf"].is_isolated is False


def test_mermaid_renderer_empty() -> None:
    """Test MermaidRenderer with empty AST."""
    ast = VisualAST(nodes={}, edges=[], parallel_groups=[])
    renderer = MermaidRenderer(ast)
    result = renderer.render()
    assert "No steps registered" in result


def test_mermaid_renderer_simple() -> None:
    """Test MermaidRenderer with simple AST."""
    nodes = {
        "a": VisualNode(id="n0", name="a", kind=NodeKind.STEP, is_entry=True),
        "b": VisualNode(id="n1", name="b", kind=NodeKind.STEP, is_terminal=True),
    }
    edges = [VisualEdge(source="a", target="b")]
    ast = VisualAST(nodes=nodes, edges=edges, parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert "graph TD" in result
    assert '["A"]' in result
    assert '["B"]' in result
    assert "n0 --> n1" in result


def test_mermaid_renderer_streaming_shape() -> None:
    """Test that streaming nodes get stadium shape."""
    nodes = {
        "stream": VisualNode(
            id="n0", name="stream", kind=NodeKind.STREAMING, is_entry=True, is_terminal=True
        )
    }
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert '(["Stream ⚡"])' in result


def test_mermaid_renderer_map_shape() -> None:
    """Test that map nodes get subroutine shape."""
    nodes = {
        "mapper": VisualNode(
            id="n0", name="mapper", kind=NodeKind.MAP, is_entry=True, is_terminal=True
        )
    }
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert '[["Mapper"]]' in result


def test_mermaid_renderer_switch_shape() -> None:
    """Test that switch nodes get diamond shape."""
    nodes = {
        "router": VisualNode(
            id="n0", name="router", kind=NodeKind.SWITCH, is_entry=True, is_terminal=True
        )
    }
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert '{"Router"}' in result


def test_mermaid_theme_direction() -> None:
    """Test custom direction in theme."""
    theme = MermaidTheme(direction="LR")
    nodes = {"a": VisualNode(id="n0", name="a", kind=NodeKind.STEP, is_entry=True)}
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast, theme)
    result = renderer.render()

    assert "graph LR" in result


def test_mermaid_theme_custom_colors() -> None:
    """Test custom colors in theme."""
    theme = MermaidTheme(step_fill="#ff0000")
    nodes = {"a": VisualNode(id="n0", name="a", kind=NodeKind.STEP, is_entry=True)}
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast, theme)
    result = renderer.render()

    assert "#ff0000" in result


def test_mermaid_renderer_map_edge() -> None:
    """Test that map edges render as dotted lines."""
    nodes = {
        "mapper": VisualNode(id="n0", name="mapper", kind=NodeKind.MAP, is_entry=True),
        "worker": VisualNode(id="n1", name="worker", kind=NodeKind.STEP, is_terminal=True),
    }
    edges = [VisualEdge(source="mapper", target="worker", is_map_edge=True)]
    ast = VisualAST(nodes=nodes, edges=edges, parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert "-. map .->" in result


def test_mermaid_renderer_labeled_edge() -> None:
    """Test that labeled edges include labels."""
    nodes = {
        "router": VisualNode(id="n0", name="router", kind=NodeKind.SWITCH, is_entry=True),
        "handler": VisualNode(id="n1", name="handler", kind=NodeKind.STEP, is_terminal=True),
    }
    edges = [VisualEdge(source="router", target="handler", label="yes")]
    ast = VisualAST(nodes=nodes, edges=edges, parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert '-- "yes" -->' in result


def test_mermaid_renderer_parallel_subgraph() -> None:
    """Test parallel groups create subgraphs."""
    nodes = {
        "a": VisualNode(id="n0", name="a", kind=NodeKind.STEP, is_entry=True),
        "b": VisualNode(id="n1", name="b", kind=NodeKind.STEP),
        "c": VisualNode(id="n2", name="c", kind=NodeKind.STEP, is_terminal=True),
    }
    edges = [
        VisualEdge(source="a", target="b"),
        VisualEdge(source="a", target="c"),
    ]
    groups = [ParallelGroup(id="parallel_n0", source_id="a", node_ids=["b", "c"])]
    ast = VisualAST(nodes=nodes, edges=edges, parallel_groups=groups)

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert "subgraph parallel_n0" in result
    assert "direction LR" in result


def test_mermaid_renderer_utilities_subgraph() -> None:
    """Test isolated nodes create utilities subgraph."""
    nodes = {
        "main": VisualNode(id="n0", name="main", kind=NodeKind.STEP, is_entry=True, is_terminal=True),
        "orphan": VisualNode(id="n1", name="orphan", kind=NodeKind.STEP, is_isolated=True),
    }
    ast = VisualAST(nodes=nodes, edges=[], parallel_groups=[])

    renderer = MermaidRenderer(ast)
    result = renderer.render()

    assert "subgraph utilities" in result
    assert ":::isolated" in result
