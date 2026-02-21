"""Unit tests for _MermaidRenderer and MermaidTheme."""

from typing import Any
from justpipe.visualization import (
    _MermaidRenderer,
    MermaidTheme,
    VisualNodeKind,
    _PipelineASTBuilder,
    VisualAST,
    VisualEdge,
    VisualNode,
)


def create_ast(
    nodes: dict[str, VisualNode] | None = None,
    edges: list[VisualEdge] | None = None,
    parallel_groups: list[Any] | None = None,
) -> VisualAST:
    return VisualAST(
        nodes=nodes or {},
        edges=edges or [],
        parallel_groups=parallel_groups or [],
        startup_hooks=[],
        shutdown_hooks=[],
    )


def test_mermaid_renderer_empty() -> None:
    ast = _PipelineASTBuilder.build({}, {})
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert "graph TD" in output
    assert "Empty[No steps registered]" in output


def test_mermaid_renderer_simple() -> None:
    """Test rendering simple AST."""
    node = VisualNode(id="n0", name="step", kind=VisualNodeKind.STEP)
    ast = create_ast(nodes={"step": node})
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert 'n0["Step"]' in output
    assert "class n0 step;" in output


def test_mermaid_renderer_streaming_shape() -> None:
    """Test streaming node shape."""
    node = VisualNode(id="n0", name="stream", kind=VisualNodeKind.STREAMING)
    ast = create_ast(nodes={"stream": node})
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert 'n0(["Stream ⚡"])' in output
    assert "class n0 streaming;" in output


def test_mermaid_renderer_map_shape() -> None:
    """Test map node shape."""
    node = VisualNode(id="n0", name="mapper", kind=VisualNodeKind.MAP)
    ast = create_ast(nodes={"mapper": node})
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert 'n0[["Mapper"]]' in output
    assert "class n0 map;" in output


def test_mermaid_renderer_switch_shape() -> None:
    """Test switch node shape."""
    node = VisualNode(id="n0", name="router", kind=VisualNodeKind.SWITCH)
    ast = create_ast(nodes={"router": node})
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert 'n0{"Router"}' in output
    assert "class n0 switch;" in output


def test_mermaid_renderer_map_edge() -> None:
    """Test map edge rendering."""
    n1 = VisualNode(id="n1", name="a", kind=VisualNodeKind.MAP)
    n2 = VisualNode(id="n2", name="b", kind=VisualNodeKind.STEP, is_map_target=True)
    edge = VisualEdge(source="a", target="b", is_map_edge=True)
    ast = create_ast(nodes={"a": n1, "b": n2}, edges=[edge])
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert "n1 -. map .-> n2" in output
    assert 'n2@{ shape: procs, label: "B" }' in output


def test_mermaid_renderer_labeled_edge() -> None:
    """Test labeled edge rendering."""
    n1 = VisualNode(id="n1", name="a", kind=VisualNodeKind.SWITCH)
    n2 = VisualNode(id="n2", name="b", kind=VisualNodeKind.STEP)
    edge = VisualEdge(source="a", target="b", label="yes")
    ast = create_ast(nodes={"a": n1, "b": n2}, edges=[edge])
    renderer = _MermaidRenderer(ast)
    output = renderer.render()
    assert 'n1 -- "yes" --> n2' in output


def test_mermaid_theme_direction() -> None:
    """Test custom direction in theme."""
    theme = MermaidTheme(direction="LR")
    assert theme.render_header() == "graph LR"


def test_mermaid_theme_custom_colors() -> None:
    """Test custom colors in theme."""
    theme = MermaidTheme(step_fill="#ff0000")
    styles = theme.render_styles()
    assert any("fill:#ff0000" in s and "classDef step" in s for s in styles)


def test_renderer_internal_methods() -> None:
    """Test internal helper methods of _MermaidRenderer."""
    # Build an empty AST
    ast = _PipelineASTBuilder.build({}, {})
    renderer = _MermaidRenderer(ast, MermaidTheme())

    # Test _add indentation
    renderer._add("test", indent=2)
    assert renderer.lines[-1] == "  test"

    # Test label formatting
    assert renderer._format_label("simple_name") == "Simple Name"
    # Note: .title() affects the escaped quote
    assert renderer._format_label('quote"test"') == "Quote&Quot;Test&Quot;"


def test_theme_methods() -> None:
    """Test theme configuration and generation."""
    theme = MermaidTheme(direction="LR", step_fill="#ffffff")
    assert theme.direction == "LR"
    assert theme.step_fill == "#ffffff"

    styles = theme.render_styles()
    assert isinstance(styles, list)
    assert len(styles) > 0
    assert any("fill:#ffffff" in s for s in styles)


def test_node_formatting() -> None:
    """Test complex node formatting scenarios."""
    ast = _PipelineASTBuilder.build({}, {})
    renderer = _MermaidRenderer(ast)

    # Test node with isolated status
    node = VisualNode(id="n1", name="test", kind=VisualNodeKind.STEP, is_isolated=True)
    output = renderer._render_node(node, "", is_isolated=True)
    assert ":::isolated" in output

    # Test sub-pipeline node
    node = VisualNode(id="n2", name="sub", kind=VisualNodeKind.SUB)
    output = renderer._render_node(node, "")
    assert '/"Sub" /' in output
