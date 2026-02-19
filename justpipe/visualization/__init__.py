"""Pipeline visualization using AST-based rendering."""

from typing import Any
from collections.abc import Callable

from justpipe.visualization.ast import (
    NodeKind,
    ParallelGroup,
    VisualAST,
    VisualEdge,
    VisualNode,
)
from justpipe.visualization.builder import _PipelineASTBuilder
from justpipe.visualization.mermaid import _MermaidRenderer, MermaidTheme
from justpipe.visualization.renderer import GraphRenderer
from justpipe._internal.definition.steps import _BaseStep


class MermaidRenderer(GraphRenderer):
    """Default Mermaid.js renderer implementation."""

    def __init__(self, theme: MermaidTheme | None = None, direction: str = "TD"):
        self.theme = theme
        self.direction = direction

    def render(
        self,
        steps: dict[str, _BaseStep],
        topology: dict[str, list[str]],
        startup_hooks: list[Callable[..., Any]] | None = None,
        shutdown_hooks: list[Callable[..., Any]] | None = None,
    ) -> str:
        effective_theme = self.theme or MermaidTheme(direction=self.direction)
        ast = _PipelineASTBuilder.build(
            steps,
            topology,
            startup_hooks=startup_hooks,
            shutdown_hooks=shutdown_hooks,
        )
        renderer = _MermaidRenderer(ast, effective_theme)
        return renderer.render()


def generate_mermaid_graph(
    steps: dict[str, _BaseStep],
    topology: dict[str, list[str]],
    startup_hooks: list[Callable[..., Any]] | None = None,
    shutdown_hooks: list[Callable[..., Any]] | None = None,
    *,
    theme: MermaidTheme | None = None,
    direction: str = "TD",
) -> str:
    """
    Convenience function to generate a Mermaid diagram.
    """
    renderer = MermaidRenderer(theme=theme, direction=direction)
    return renderer.render(steps, topology, startup_hooks, shutdown_hooks)


__all__ = [
    # Protocols
    "GraphRenderer",
    # Implementation
    "MermaidRenderer",
    # AST model
    "VisualAST",
    "VisualNode",
    "VisualEdge",
    "ParallelGroup",
    "NodeKind",
    # Mermaid rendering
    "MermaidTheme",
    # Convenience function
    "generate_mermaid_graph",
]
