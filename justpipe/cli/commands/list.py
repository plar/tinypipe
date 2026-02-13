"""list command for CLI."""

from __future__ import annotations

from justpipe.cli.formatting import (
    format_duration,
    format_status,
    format_timestamp,
    short_id,
)
from justpipe.cli.registry import PipelineRegistry
from justpipe.types import PipelineTerminalStatus


def list_command(
    registry: PipelineRegistry,
    pipeline: str | None = None,
    status: PipelineTerminalStatus | None = None,
    limit: int = 10,
    full_ids: bool = False,
) -> None:
    """list pipeline runs."""
    try:
        from rich.console import Console
        from rich.table import Table

        use_rich = True
    except ImportError:
        use_rich = False

    runs = registry.list_all_runs(pipeline_name=pipeline, status=status, limit=limit)

    if not runs:
        print("No runs found")
        return

    if use_rich:
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Run ID", style="cyan", no_wrap=full_ids)
        table.add_column("Pipeline", style="green")
        table.add_column("Status")
        table.add_column("Started", style="dim")
        table.add_column("Duration", justify="right")

        for annotated in runs:
            run = annotated.run
            table.add_row(
                short_id(run.run_id, full=full_ids),
                annotated.pipeline_name,
                format_status(run.status),
                format_timestamp(run.start_time),
                format_duration(run.duration.total_seconds() if run.duration else None),
            )

        console.print(table)

    else:
        id_width = 34 if full_ids else 15
        print(
            f"{'Run ID':<{id_width}} {'Pipeline':<20} {'Status':<14} {'Started':<20} {'Duration':>10}"
        )
        print("-" * (id_width + 74))

        for annotated in runs:
            run = annotated.run
            print(
                f"{short_id(run.run_id, full=full_ids):<{id_width}} "
                f"{annotated.pipeline_name[:20]:<20} "
                f"{run.status.value:<14} "
                f"{format_timestamp(run.start_time):<20} "
                f"{format_duration(run.duration.total_seconds() if run.duration else None):>10}"
            )

    print()
    print(f"Showing {len(runs)} run(s)")
    if len(runs) >= limit:
        print(f"(Limited to {limit}, use --limit to show more)")

    if not full_ids and runs:
        print()
        print("Tip: Use run ID prefix (min 4 chars) in other commands")
        print(f"   Example: justpipe show {runs[0].run.run_id[:8]}")
