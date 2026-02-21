"""Mermaid.js renderer for pipeline visualization."""

from collections import defaultdict
from dataclasses import dataclass

from justpipe.visualization.ast import VisualNodeKind, VisualAST, VisualNode
from justpipe.types import BarrierType


@dataclass
class MermaidTheme:
    """Styling configuration for Mermaid diagrams."""

    direction: str = "TD"

    # Colors for standard steps
    step_fill: str = "#e3f2fd"
    step_stroke: str = "#1976d2"
    step_color: str = "#0d47a1"

    # Colors for streaming steps
    streaming_fill: str = "#fff3e0"
    streaming_stroke: str = "#f57c00"
    streaming_color: str = "#e65100"

    # Colors for map steps
    map_fill: str = "#e8f5e9"
    map_stroke: str = "#388e3c"
    map_color: str = "#1b5e20"

    # Colors for switch steps
    switch_fill: str = "#f3e5f5"
    switch_stroke: str = "#7b1fa2"
    switch_color: str = "#4a148c"

    # Colors for sub-pipelines
    sub_fill: str = "#f1f8e9"
    sub_stroke: str = "#558b2f"
    sub_color: str = "#33691e"

    # Colors for isolated steps
    isolated_fill: str = "#fce4ec"
    isolated_stroke: str = "#c2185b"
    isolated_color: str = "#880e4f"

    # Colors for start/end markers
    start_end_fill: str = "#e8f5e9"
    start_end_stroke: str = "#388e3c"
    start_end_color: str = "#1b5e20"

    def render_header(self) -> str:
        """Render the Mermaid graph header."""
        return f"graph {self.direction}"

    def render_styles(self) -> list[str]:
        """Render Mermaid class definitions."""
        return [
            "%% Styling",
            "classDef default fill:#f8f9fa,stroke:#dee2e6,stroke-width:1px;",
            f"classDef step fill:{self.step_fill},stroke:{self.step_stroke},stroke-width:2px,color:{self.step_color};",
            f"classDef streaming fill:{self.streaming_fill},stroke:{self.streaming_stroke},stroke-width:2px,color:{self.streaming_color};",
            f"classDef map fill:{self.map_fill},stroke:{self.map_stroke},stroke-width:2px,color:{self.map_color};",
            f"classDef switch fill:{self.switch_fill},stroke:{self.switch_stroke},stroke-width:2px,color:{self.switch_color};",
            f"classDef sub fill:{self.sub_fill},stroke:{self.sub_stroke},stroke-width:2px,color:{self.sub_color};",
            f"classDef isolated fill:{self.isolated_fill},stroke:{self.isolated_stroke},stroke-width:2px,stroke-dasharray: 5 5,color:{self.isolated_color};",
            f"classDef startEnd fill:{self.start_end_fill},stroke:{self.start_end_stroke},stroke-width:3px,color:{self.start_end_color};",
        ]


class _MermaidRenderer:
    """Renders VisualAST to Mermaid.js string."""

    def __init__(self, ast: VisualAST, theme: MermaidTheme | None = None):
        self.ast = ast
        self.theme = theme or MermaidTheme()
        self.lines: list[str] = [self.theme.render_header()]

    def render(self) -> str:
        """Generate complete Mermaid diagram."""
        self._render_graph_content(self.ast, prefix="", indent=4)

        # Render styles at the end
        self.lines.append("")
        for style_line in self.theme.render_styles():
            self._add(style_line, indent=4)

        return "\n".join(self.lines)

    def _add(self, line: str, indent: int = 4) -> None:
        """Append a line with proper indentation."""
        self.lines.append(" " * indent + line)

    def _format_label(self, name: str) -> str:
        """Format a node label for display."""
        return name.replace('"', "&quot;").replace("_", " ").title()

    def _render_node(
        self,
        node: VisualNode,
        id_prefix: str,
        is_isolated: bool = False,
    ) -> str:
        """Render node with kind-specific shape."""
        label = self._format_label(node.name)
        if node.barrier_type == BarrierType.ANY:
            label = f"{label} (Any)"

        node_id = f"{id_prefix}{node.id}"

        if node.is_map_target:
            node_def = f'{node_id}@{{ shape: procs, label: "{label}" }}'
        else:
            match node.kind:
                case VisualNodeKind.SWITCH:
                    node_def = f'{node_id}{{"{label}"}}'
                case VisualNodeKind.MAP:
                    node_def = f'{node_id}[["{label}"]]'
                case VisualNodeKind.SUB:
                    node_def = f'{node_id}[/"{label}" /]'
                case VisualNodeKind.STREAMING:
                    label = f"{label} ⚡"
                    node_def = f'{node_id}(["{label}"])'

                case _:
                    node_def = f'{node_id}["{label}"]'

        if is_isolated:
            node_def += ":::isolated"
        return node_def

    def _get_grouped_nodes(self, ast: VisualAST) -> set[str]:
        """Get all nodes that are part of parallel groups."""
        grouped: set[str] = set()
        for group in ast.parallel_groups:
            grouped.update(group.node_ids)
        return grouped

    def _get_isolated_nodes(self, ast: VisualAST) -> set[str]:
        """Get all isolated nodes."""
        return {name for name, node in ast.nodes.items() if node.is_isolated}

    def _render_graph_content(
        self,
        ast: VisualAST,
        prefix: str = "",
        indent: int = 4,
    ) -> None:
        """Render the nodes and edges of an AST."""
        if not ast.nodes:
            self._add(f"{prefix}Empty[No steps registered]", indent)
            return

        start_target_id = f"{prefix}Start"

        self._render_hooks(
            ast.startup_hooks, prefix, indent, "startup", start_target_id, before=True
        )

        # Start node
        self._add(f'{start_target_id}(["▶ Start"])', indent)

        grouped = self._get_grouped_nodes(ast)
        isolated = self._get_isolated_nodes(ast)

        self._render_parallel_groups(ast, prefix, indent)
        self._render_main_nodes(ast, prefix, indent, grouped, isolated)

        # End node
        terminal_non_isolated = [
            n
            for n, node in ast.nodes.items()
            if node.is_terminal and not node.is_isolated
        ]

        end_source_id = None
        if terminal_non_isolated:
            end_source_id = f"{prefix}End"
            self._add(f'{end_source_id}(["■ End"])', indent)

        # Connect terminal nodes to End
        if end_source_id:
            for name in sorted(terminal_non_isolated):
                node = ast.nodes[name]
                self._add(f"{prefix}{node.id} --> {end_source_id}", indent)

        self._render_hooks(
            ast.shutdown_hooks, prefix, indent, "shutdown", end_source_id, before=False
        )

        self.lines.append("")
        self._render_start_connections(ast, prefix, indent, start_target_id)
        self._render_edges(ast, prefix, indent)

        self._render_isolated_nodes(ast, prefix, indent, isolated)

        self._apply_classes(ast, prefix)

        self._render_sub_pipelines(ast, prefix, indent)

    def _render_hooks(
        self,
        hooks: list[str],
        prefix: str,
        indent: int,
        kind: str,
        connect_id: str | None,
        *,
        before: bool,
    ) -> None:
        if not hooks or connect_id is None:
            return
        label = f"{kind.title()} Hooks"
        last_id = None
        self._add(f"subgraph {prefix}{kind}[{label}]", indent)
        self._add("direction TB", indent + 4)
        for i, h_name in enumerate(hooks):
            node_id = f"{prefix}{kind}_{i}"
            self._add(f"{node_id}> {self._format_label(h_name)} ]", indent + 4)
            if last_id:
                self._add(f"{last_id} --> {node_id}", indent + 4)
            last_id = node_id
        self._add("end", indent)
        if before:
            self._add(f"{prefix}{kind} --> {connect_id}", indent)
        else:
            self._add(f"{connect_id} --> {prefix}{kind}", indent)

    def _render_parallel_groups(self, ast: VisualAST, prefix: str, indent: int) -> None:
        for group in ast.parallel_groups:
            self.lines.append("")
            self._add(f"subgraph {prefix}{group.id}[Parallel]", indent)
            self._add("direction LR", indent + 4)
            for node_name in sorted(group.node_ids):
                node = ast.nodes[node_name]
                self._add(self._render_node(node, prefix), indent + 4)
            self._add("end", indent)

    def _render_main_nodes(
        self,
        ast: VisualAST,
        prefix: str,
        indent: int,
        grouped: set[str],
        isolated: set[str],
    ) -> None:
        self.lines.append("")
        for name in sorted(ast.nodes.keys()):
            if name not in grouped and name not in isolated:
                node = ast.nodes[name]
                self._add(self._render_node(node, prefix), indent)

    def _render_start_connections(
        self, ast: VisualAST, prefix: str, indent: int, start_target_id: str
    ) -> None:
        for name, node in sorted(ast.nodes.items()):
            if node.is_entry and not node.is_isolated:
                self._add(f"{start_target_id} --> {prefix}{node.id}", indent)

    def _render_edges(self, ast: VisualAST, prefix: str, indent: int) -> None:
        for edge in sorted(ast.edges, key=lambda e: (e.source, e.target)):
            src_node = ast.nodes[edge.source]
            tgt_node = ast.nodes[edge.target]
            src_id = f"{prefix}{src_node.id}"
            tgt_id = f"{prefix}{tgt_node.id}"

            if edge.is_map_edge:
                self._add(f"{src_id} -. map .-> {tgt_id}", indent)
            elif edge.label:
                self._add(f' {src_id} -- "{edge.label}" --> {tgt_id}', indent)
            else:
                self._add(f"{src_id} --> {tgt_id}", indent)

    def _render_isolated_nodes(
        self, ast: VisualAST, prefix: str, indent: int, isolated: set[str]
    ) -> None:
        if isolated:
            self.lines.append("")
            self._add(f"subgraph {prefix}utilities[Utilities]", indent)
            self._add("direction TB", indent + 4)
            for name in sorted(isolated):
                node = ast.nodes[name]
                self._add(
                    self._render_node(node, prefix, is_isolated=True),
                    indent + 4,
                )
            self._add("end", indent)

    def _render_sub_pipelines(self, ast: VisualAST, prefix: str, indent: int) -> None:
        for name, node in sorted(ast.nodes.items()):
            if node.sub_graph:
                self.lines.append("")
                sub_id = f"cluster_{prefix}{node.id}"
                # Using a subgraph for visual grouping
                self._add(
                    f'subgraph {sub_id} ["{self._format_label(node.name)} (Impl)"]',
                    indent,
                )
                self._add("direction TB", indent + 4)
                self._render_graph_content(
                    node.sub_graph,
                    prefix=f"{prefix}{node.id}_",
                    indent=indent + 4,
                )
                self._add("end", indent)

                # Link parent node to sub-pipeline start
                sub_start_id = f"{prefix}{node.id}_Start"
                node_full_id = f"{prefix}{node.id}"
                self._add(f"{node_full_id} -.- {sub_start_id}", indent)

    def _apply_classes(self, ast: VisualAST, prefix: str) -> None:
        """Generate class assignments for nodes."""
        kind_to_class = {
            VisualNodeKind.STREAMING: "streaming",
            VisualNodeKind.MAP: "map",
            VisualNodeKind.SWITCH: "switch",
            VisualNodeKind.SUB: "sub",
        }
        buckets: dict[str, list[str]] = defaultdict(list)
        for name, node in ast.nodes.items():
            full_id = f"{prefix}{node.id}"
            if node.is_isolated:
                buckets["isolated"].append(full_id)
            else:
                buckets[kind_to_class.get(node.kind, "step")].append(full_id)
        for cls, ids in sorted(buckets.items()):
            self._add(f"class {','.join(sorted(ids))} {cls};")
        if ast.nodes:
            self._add(f"class {prefix}Start,{prefix}End startEnd;")
