import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class MermaidTheme:
    """Styling configuration for Mermaid diagrams."""

    direction: str = "TD"

    # Colors
    step_fill: str = "#e3f2fd"
    step_stroke: str = "#1976d2"
    step_color: str = "#0d47a1"

    streaming_fill: str = "#fff3e0"
    streaming_stroke: str = "#f57c00"
    streaming_color: str = "#e65100"

    isolated_fill: str = "#fce4ec"
    isolated_stroke: str = "#c2185b"
    isolated_color: str = "#880e4f"

    start_end_fill: str = "#e8f5e9"
    start_end_stroke: str = "#388e3c"
    start_end_color: str = "#1b5e20"

    def render_header(self) -> str:
        """Render the Mermaid graph header."""
        return f"graph {self.direction}"

    def render_styles(self) -> List[str]:
        """Render Mermaid class definitions."""
        return [
            "%% Styling",
            "classDef default fill:#f8f9fa,stroke:#dee2e6,stroke-width:1px;",
            f"classDef step fill:{self.step_fill},stroke:{self.step_stroke},stroke-width:2px,color:{self.step_color};",
            f"classDef streaming fill:{self.streaming_fill},stroke:{self.streaming_stroke},stroke-width:2px,color:{self.streaming_color};",
            f"classDef isolated fill:{self.isolated_fill},stroke:{self.isolated_stroke},stroke-width:2px,stroke-dasharray: 5 5,color:{self.isolated_color};",
            f"classDef startEnd fill:{self.start_end_fill},stroke:{self.start_end_stroke},stroke-width:3px,color:{self.start_end_color};",
        ]


class _MermaidRenderer:
    """Internal engine for generating Mermaid strings."""

    def __init__(
        self,
        steps: Dict[str, Callable[..., Any]],
        topology: Dict[str, List[str]],
        theme: MermaidTheme,
    ):
        self.steps = steps
        self.topology = topology
        self.theme = theme
        self.lines: List[str] = [theme.render_header()]

        # Analysis phase
        self.all_nodes: Set[str] = set(steps.keys())
        for targets in topology.values():
            self.all_nodes.update(targets)

        self.streaming_nodes = {
            name for name, func in steps.items() if inspect.isasyncgenfunction(func)
        }

        all_targets = {t for targets in topology.values() for t in targets}
        self.entry_points = set(topology.keys()) - all_targets
        self.terminal_nodes = self.all_nodes - set(topology.keys())
        self.isolated_nodes = set(steps.keys()) - (set(topology.keys()) | all_targets)

        # Fallback logic for complex DAGs or single-node pipes
        if not self.entry_points and topology:
            self.entry_points = {next(iter(topology.keys()))}
        elif not topology and steps:
            self.entry_points = set(steps.keys())

        # Node ID generation
        self.safe_ids = {name: f"n{i}" for i, name in enumerate(sorted(self.all_nodes))}

    def _add(self, line: str, indent: int = 4) -> None:
        """Append a line with proper indentation."""
        self.lines.append(" " * indent + line)

    def _format_node(self, name: str, is_isolated: bool = False) -> str:
        """Format a node definition based on its type."""
        safe_id = self.safe_ids[name]
        label = name.replace('"', "&quot;").replace("_", " ").title()

        if name in self.streaming_nodes:
            label = f"{label} ⚡"
            node_def = f'{safe_id}(["{label}"])'
        else:
            node_def = f'{safe_id}["{label}"]'

        if is_isolated:
            node_def += ":::isolated"
        return node_def

    def render(self) -> str:
        """Execute the full rendering pipeline."""
        if not self.all_nodes:
            return "graph TD\n    Empty[No steps registered]"

        self._add('Start(["▶ Start"])')

        # 1. Group parallel branches into subgraphs
        grouped: Set[str] = set()
        for src, targets in self.topology.items():
            if len(targets) > 1:
                self.lines.append("")
                self._add(f"subgraph parallel_{self.safe_ids[src]}[Parallel]")
                self._add("direction LR", indent=8)
                for t in sorted(targets):
                    self._add(self._format_node(t), indent=8)
                    grouped.add(t)
                self._add("end")

        # 2. Render main flow nodes
        self.lines.append("")
        for node in sorted(self.all_nodes - grouped - self.isolated_nodes):
            self._add(self._format_node(node))

        if self.terminal_nodes - self.isolated_nodes:
            self._add('End(["■ End"])')

        # 3. Connect entry points and edges
        self.lines.append("")
        for entry in sorted(self.entry_points - self.isolated_nodes):
            self._add(f"Start --> {self.safe_ids[entry]}")

        for src, targets in sorted(self.topology.items()):
            for t in sorted(targets):
                self._add(f"{self.safe_ids[src]} --> {self.safe_ids[t]}")

        # 4. Connect terminal nodes to End
        for term in sorted(self.terminal_nodes - self.isolated_nodes):
            self._add(f"{self.safe_ids[term]} --> End")

        # 5. Render isolated/utility nodes in a separate block
        if self.isolated_nodes:
            self.lines.append("")
            self._add("subgraph utilities[Utilities]")
            self._add("direction TB", indent=8)
            for iso in sorted(self.isolated_nodes):
                self._add(self._format_node(iso, is_isolated=True), indent=8)
            self._add("end")

        # 6. Apply Styles and Classes
        self.lines.append("")
        for style_line in self.theme.render_styles():
            self._add(style_line)

        # Categorize node IDs for bulk class assignment
        reg_ids = [
            self.safe_ids[n]
            for n in self.all_nodes - self.streaming_nodes - self.isolated_nodes
        ]
        stream_ids = [
            self.safe_ids[n] for n in self.streaming_nodes - self.isolated_nodes
        ]
        iso_ids = [self.safe_ids[n] for n in self.isolated_nodes]

        if reg_ids:
            self._add(f"class {','.join(sorted(reg_ids))} step;")
        if stream_ids:
            self._add(f"class {','.join(sorted(stream_ids))} streaming;")
        if iso_ids:
            self._add(f"class {','.join(sorted(iso_ids))} isolated;")
        self._add("class Start,End startEnd;")

        return "\n".join(self.lines)


def generate_mermaid_graph(
    steps: Dict[str, Callable[..., Any]],
    topology: Dict[str, List[str]],
    *,
    theme: Optional[MermaidTheme] = None,
    direction: str = "TD",
) -> str:
    """
    Generate a Mermaid diagram from the pipeline structure.

    Args:
        steps: Map of registered step functions.
        topology: Map of static execution paths.
        theme: Optional MermaidTheme for custom styling.
        direction: Graph direction (default: TD).
    """
    effective_theme = theme or MermaidTheme(direction=direction)
    renderer = _MermaidRenderer(steps, topology, effective_theme)
    return renderer.render()
