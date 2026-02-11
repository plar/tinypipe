"""Timeline command for CLI."""

from justpipe.storage.interface import StorageBackend
from justpipe.types import EventType
from justpipe.observability import ObserverMeta
from justpipe.observability.timeline import TimelineVisualizer


async def timeline_command(
    storage: StorageBackend, run_id_prefix: str, format: str = "ascii"
) -> None:
    """Show execution timeline for a run.

    Args:
        storage: Storage backend
        run_id_prefix: Run identifier or prefix (min 4 chars)
        format: Output format (ascii, html, mermaid)
    """
    # Resolve prefix to full ID
    try:
        run = await storage.get_run_by_prefix(run_id_prefix)
    except ValueError as e:
        print(f"Error: {e}")
        return

    if run is None:
        print(f"Run not found: {run_id_prefix}")
        return

    # Get events
    stored_events = await storage.get_events(run.id)

    if not stored_events:
        print("No events found for this run")
        return

    # Create timeline visualizer
    visualizer = TimelineVisualizer()

    # Populate visualizer with stored events
    # We need to simulate the observer lifecycle
    visualizer.pipeline_start = run.start_time
    visualizer.pipeline_end = run.end_time or run.start_time
    visualizer.pipeline_name = run.pipeline_name
    meta = ObserverMeta(pipe_name=run.pipeline_name, started_at=run.start_time)

    # Convert stored events to Event objects and process
    from justpipe.types import Event

    for stored_event in stored_events:
        # Create Event object
        try:
            event_type = EventType(stored_event.event_type)
        except ValueError:
            continue

        event = Event(
            type=event_type,
            stage=stored_event.step_name,
            payload=stored_event.payload,
            timestamp=stored_event.timestamp,
        )

        # Process through visualizer
        await visualizer.on_event(None, None, meta, event)

    # Generate output based on format
    if format == "ascii":
        output = visualizer.render_ascii()
        print(output)

    elif format == "html":
        output = visualizer.render_html()

        # Save to file (use first 8 chars of actual ID)
        filename = f"timeline_{run.id[:8]}.html"
        with open(filename, "w") as f:
            f.write(output)

        print(f"HTML timeline saved to: {filename}")
        print("Open in your browser to view.")

    elif format == "mermaid":
        output = visualizer.render_mermaid()

        # Save to file (use first 8 chars of actual ID)
        filename = f"timeline_{run.id[:8]}.mmd"
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
