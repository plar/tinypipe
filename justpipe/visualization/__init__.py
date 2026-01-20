"""Pipeline visualization using AST-based rendering."""

from typing import Any, Callable, Dict, List, Optional

from justpipe.visualization.ast import (
    NodeKind,
    ParallelGroup,
    VisualAST,
    VisualEdge,
    VisualNode,
)
from justpipe.visualization.mermaid import MermaidRenderer, MermaidTheme


def generate_mermaid_graph(
    steps: Dict[str, Callable[..., Any]],
    topology: Dict[str, List[str]],
    step_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    startup_hooks: Optional[List[Callable[..., Any]]] = None,
    shutdown_hooks: Optional[List[Callable[..., Any]]] = None,
    *,
    theme: Optional[MermaidTheme] = None,
    direction: str = "TD",
) -> str:
    """
    Generate a Mermaid diagram from the pipeline structure.

    Args:
        steps: Map of registered step functions.
        topology: Map of static execution paths.
        step_metadata: Optional metadata for steps (map/switch info).
        startup_hooks: Optional list of startup hook functions.
        shutdown_hooks: Optional list of shutdown hook functions.
        theme: Optional MermaidTheme for custom styling.
        direction: Graph direction (default: TD).

    Returns:
        A Mermaid.js diagram string.
    """
    effective_theme = theme or MermaidTheme(direction=direction)
    ast = VisualAST.from_pipe(
        steps,
        topology,
        step_metadata or {},
        startup_hooks=startup_hooks,
        shutdown_hooks=shutdown_hooks,
    )
    renderer = MermaidRenderer(ast, effective_theme)
    return renderer.render()


__all__ = [
    # AST model
    "VisualAST",
    "VisualNode",
    "VisualEdge",
    "ParallelGroup",
    "NodeKind",
    # Mermaid rendering
    "MermaidRenderer",
    "MermaidTheme",
    # Convenience function
    "generate_mermaid_graph",
]
