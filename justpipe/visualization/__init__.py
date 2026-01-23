"""Pipeline visualization using AST-based rendering."""

from typing import Any, Callable, Dict, List, Optional

from justpipe.visualization.ast import (
    NodeKind,
    ParallelGroup,
    VisualAST,
    VisualEdge,
    VisualNode,
)
from justpipe.visualization.builder import _PipelineASTBuilder
from justpipe.visualization.mermaid import _MermaidRenderer, MermaidTheme
from justpipe.steps import _BaseStep


def generate_mermaid_graph(
    steps: Dict[str, _BaseStep],
    topology: Dict[str, List[str]],
    startup_hooks: Optional[List[Callable[..., Any]]] = None,
    shutdown_hooks: Optional[List[Callable[..., Any]]] = None,
    *,
    theme: Optional[MermaidTheme] = None,
    direction: str = "TD",
) -> str:
# ... (middle lines omitted)
    effective_theme = theme or MermaidTheme(direction=direction)
    ast = _PipelineASTBuilder.build(
        steps,
        topology,
        startup_hooks=startup_hooks,
        shutdown_hooks=shutdown_hooks,
    )
    renderer = _MermaidRenderer(ast, effective_theme)
    return renderer.render()



__all__ = [
    # AST model
    "VisualAST",
    "VisualNode",
    "VisualEdge",
    "ParallelGroup",
    "NodeKind",
    # Builder
    "_PipelineASTBuilder",
    # Mermaid rendering
    "_MermaidRenderer",
    "MermaidTheme",
    # Convenience function
    "generate_mermaid_graph",
]

