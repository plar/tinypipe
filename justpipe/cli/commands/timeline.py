"""Timeline command for CLI."""

from __future__ import annotations

from justpipe.cli.formatting import resolve_or_exit
from justpipe.cli.registry import PipelineRegistry
from justpipe.observability.timeline import TimelineVisualizer


def timeline_command(
    registry: PipelineRegistry, run_id_prefix: str, format: str = "ascii"
) -> None:
    """Show execution timeline for a run."""
    result = resolve_or_exit(registry, run_id_prefix)
    if result is None:
        return

    annotated, backend = result
    run = annotated.run

    stored_events = backend.get_events(run.run_id)

    if not stored_events:
        print("No events found for this run")
        return

    visualizer = TimelineVisualizer()
    visualizer.pipeline_start = run.start_time.timestamp()
    visualizer.pipeline_end = (run.end_time or run.start_time).timestamp()
    visualizer.pipeline_name = annotated.pipeline_name

    for stored_event in stored_events:
        visualizer.process_event(
            stored_event.event_type,
            stored_event.step_name,
            stored_event.timestamp.timestamp(),
        )

    if format == "ascii":
        output = visualizer.render_ascii()
        print(output)

    elif format == "html":
        output = visualizer.render_html()
        filename = f"timeline_{run.run_id[:8]}.html"
        with open(filename, "w") as f:
            f.write(output)
        print(f"HTML timeline saved to: {filename}")
        print("Open in your browser to view.")

    elif format == "mermaid":
        output = visualizer.render_mermaid()
        filename = f"timeline_{run.run_id[:8]}.mmd"
        with open(filename, "w") as f:
            f.write(output)
        print(f"Mermaid diagram saved to: {filename}")
        print()
        print("View online at: https://mermaid.live")
        print()
        print(output)

    else:
        print(f"Unknown format: {format}")
        print("Supported formats: ascii, html, mermaid")
