"""Unit tests for _PipelineASTBuilder."""

from typing import Any

from justpipe.visualization import (
    NodeKind,
    _PipelineASTBuilder,
)
from justpipe._internal.definition.steps import (
    _BaseStep,
    _StandardStep,
    _MapStep,
    _SwitchStep,
)


def test_ast_from_empty_pipe() -> None:
    """Test building AST from empty pipe."""
    ast = _PipelineASTBuilder.build({}, {})
    assert not ast.nodes
    assert not ast.edges
    assert not ast.parallel_groups


def test_ast_from_single_step() -> None:
    """Test building AST from single step."""

    async def step_a(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "a": _StandardStep(name="a", func=step_a),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert len(ast.nodes) == 1
    node = ast.nodes["a"]
    assert node.name == "a"
    assert node.kind == NodeKind.STEP
    assert node.is_entry
    assert node.is_terminal
    assert not node.is_isolated


def test_ast_from_linear_pipe() -> None:
    """Test building AST from linear pipeline."""

    async def step_a(s: Any) -> None:
        pass

    async def step_b(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "a": _StandardStep(name="a", func=step_a, to=["b"]),
        "b": _StandardStep(name="b", func=step_b),
    }
    topology = {"a": ["b"]}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert len(ast.nodes) == 2
    assert len(ast.edges) == 1

    node_a = ast.nodes["a"]
    node_b = ast.nodes["b"]

    assert node_a.is_entry
    assert not node_a.is_terminal
    assert not node_b.is_entry
    assert node_b.is_terminal

    edge = ast.edges[0]
    assert edge.source == "a"
    assert edge.target == "b"


def test_ast_streaming_node() -> None:
    """Test that streaming steps are identified correctly."""

    async def regular(s: Any) -> None:
        pass

    async def streaming(s: Any) -> Any:
        yield 1

    steps: dict[str, _BaseStep] = {
        "regular": _StandardStep(name="regular", func=regular, to=["streaming"]),
        "streaming": _StandardStep(name="streaming", func=streaming),
    }
    topology = {"regular": ["streaming"]}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert ast.nodes["streaming"].kind == NodeKind.STREAMING
    assert ast.nodes["regular"].kind == NodeKind.STEP


def test_ast_parallel_group() -> None:
    """Test that parallel branches create groups."""

    async def step_a(s: Any) -> None:
        pass

    async def step_b(s: Any) -> None:
        pass

    async def step_c(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "a": _StandardStep(name="a", func=step_a, to=["b", "c"]),
        "b": _StandardStep(name="b", func=step_b),
        "c": _StandardStep(name="c", func=step_c),
    }
    topology = {"a": ["b", "c"]}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert len(ast.parallel_groups) == 1
    group = ast.parallel_groups[0]
    assert group.source_id == "a"
    assert set(group.node_ids) == {"b", "c"}


def test_ast_map_metadata() -> None:
    """Test that map steps are identified from metadata."""

    async def mapper(s: Any) -> None:
        pass

    async def worker(item: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "mapper": _MapStep(name="mapper", func=mapper, each="worker"),
        "worker": _StandardStep(name="worker", func=worker),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert ast.nodes["mapper"].kind == NodeKind.MAP
    assert ast.nodes["worker"].is_map_target
    assert len(ast.edges) == 1
    assert ast.edges[0].is_map_edge


def test_ast_switch_metadata() -> None:
    """Test that switch steps are identified from metadata."""

    async def router(s: Any) -> None:
        pass

    async def handler_a(s: Any) -> None:
        pass

    async def handler_b(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "router": _SwitchStep(
            name="router",
            func=router,
            to={"yes": "handler_a", "no": "handler_b"},
        ),
        "handler_a": _StandardStep(name="handler_a", func=handler_a),
        "handler_b": _StandardStep(name="handler_b", func=handler_b),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert ast.nodes["router"].kind == NodeKind.SWITCH
    assert len(ast.edges) == 2
    labels = {e.label for e in ast.edges}
    assert labels == {"yes", "no"}


def test_ast_switch_with_default() -> None:
    """Test switch with default route."""

    async def router(s: Any) -> None:
        pass

    async def handler(s: Any) -> None:
        pass

    async def fallback(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "router": _SwitchStep(
            name="router", func=router, to={"yes": "handler"}, default="fallback"
        ),
        "handler": _StandardStep(name="handler", func=handler),
        "fallback": _StandardStep(name="fallback", func=fallback),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert len(ast.edges) == 2
    labels = {e.label for e in ast.edges}
    assert labels == {"yes", "default"}


def test_ast_isolated_node() -> None:
    """Test isolated nodes are identified."""

    async def main(s: Any) -> None:
        pass

    async def orphan(s: Any) -> None:
        pass

    async def leaf(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "main": _StandardStep(name="main", func=main, to=["leaf"]),
        "orphan": _StandardStep(name="orphan", func=orphan),
        "leaf": _StandardStep(name="leaf", func=leaf),
    }
    topology = {"main": ["leaf"]}

    ast = _PipelineASTBuilder.build(steps, topology)
    assert ast.nodes["orphan"].is_isolated
    assert not ast.nodes["main"].is_isolated
    assert not ast.nodes["leaf"].is_isolated


def test_ast_dynamic_returns() -> None:
    """Test that dynamic return statements are detected via AST analysis."""

    async def step_a(s: Any) -> str:
        if s > 0:
            return "step_b"
        return "step_c"

    async def step_b(s: Any) -> None:
        pass

    async def step_c(s: Any) -> None:
        pass

    steps: dict[str, _BaseStep] = {
        "step_a": _StandardStep(name="step_a", func=step_a),
        "step_b": _StandardStep(name="step_b", func=step_b),
        "step_c": _StandardStep(name="step_c", func=step_c),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)

    # Should detect two dynamic edges
    dynamic_edges = [e for e in ast.edges if e.label == "dynamic"]
    assert len(dynamic_edges) == 2
    targets = {e.target for e in dynamic_edges}
    assert targets == {"step_b", "step_c"}
    assert all(e.source == "step_a" for e in dynamic_edges)


def test_ast_dynamic_returns_from_nested_helper_function() -> None:
    """Nested helper returns should still be parsed after dedent."""

    async def route_with_helper(state: int) -> str:
        def choose(target: int) -> str:
            if target > 0:
                return "step_b"
            return "step_c"

        return choose(state)

    async def step_b(state: Any) -> None:
        _ = state

    async def step_c(state: Any) -> None:
        _ = state

    steps: dict[str, _BaseStep] = {
        "route_with_helper": _StandardStep(
            name="route_with_helper", func=route_with_helper
        ),
        "step_b": _StandardStep(name="step_b", func=step_b),
        "step_c": _StandardStep(name="step_c", func=step_c),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    dynamic_edges = {
        (edge.source, edge.target) for edge in ast.edges if edge.label == "dynamic"
    }

    assert dynamic_edges == {
        ("route_with_helper", "step_b"),
        ("route_with_helper", "step_c"),
    }


def test_ast_ignores_streaming_yielded_step_names_as_dynamic_routes() -> None:
    """Yielded string tokens are not route returns and must not add dynamic edges."""

    async def streaming_router(state: Any) -> Any:
        _ = state
        yield "step_b"

    async def step_b(state: Any) -> None:
        _ = state

    steps: dict[str, _BaseStep] = {
        "streaming_router": _StandardStep(
            name="streaming_router", func=streaming_router
        ),
        "step_b": _StandardStep(name="step_b", func=step_b),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    dynamic_edges = [
        edge
        for edge in ast.edges
        if edge.source == "streaming_router" and edge.label == "dynamic"
    ]

    assert dynamic_edges == []


def test_ast_ignores_unknown_nested_returns_when_outer_return_is_known() -> None:
    """Only known step-name returns should become dynamic edges."""

    async def router(state: int) -> str:
        def helper() -> str:
            return "not_a_step"

        _ = helper()
        if state > 0:
            return "step_b"
        return "step_c"

    async def step_b(state: Any) -> None:
        _ = state

    async def step_c(state: Any) -> None:
        _ = state

    steps: dict[str, _BaseStep] = {
        "router": _StandardStep(name="router", func=router),
        "step_b": _StandardStep(name="step_b", func=step_b),
        "step_c": _StandardStep(name="step_c", func=step_c),
    }
    topology: dict[str, list[str]] = {}

    ast = _PipelineASTBuilder.build(steps, topology)
    dynamic_targets = {
        edge.target
        for edge in ast.edges
        if edge.source == "router" and edge.label == "dynamic"
    }

    assert dynamic_targets == {"step_b", "step_c"}
