from typing import Any, Protocol, runtime_checkable
from collections.abc import Callable
from justpipe._internal.definition.steps import _BaseStep


@runtime_checkable
class GraphRenderer(Protocol):
    """Protocol for pipeline graph renderers."""

    def render(
        self,
        steps: dict[str, _BaseStep],
        topology: dict[str, list[str]],
        startup_hooks: list[Callable[..., Any]] | None = None,
        shutdown_hooks: list[Callable[..., Any]] | None = None,
    ) -> str:
        """Render the pipeline structure to a string representation."""
        ...
