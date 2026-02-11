"""list command for CLI."""

from justpipe.storage.interface import StorageBackend


def format_duration(seconds: float | None) -> str:
    """Format duration for display."""
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def format_timestamp(timestamp: float) -> str:
    """Format timestamp for display."""
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def list_command(
    storage: StorageBackend,
    pipeline: str | None = None,
    status: str | None = None,
    limit: int = 10,
    full_ids: bool = False,
) -> None:
    """list pipeline runs.

    Args:
        storage: Storage backend
        pipeline: Filter by pipeline name
        status: Filter by status
        limit: Maximum number of runs
        full_ids: Show full run IDs (32 chars) instead of short (12 chars)
    """
    # Try to use rich for better formatting
    try:
        from rich.console import Console
        from rich.table import Table

        use_rich = True
    except ImportError:
        use_rich = False

    # Get runs
    runs = await storage.list_runs(
        pipeline_name=pipeline,
        status=status,
        limit=limit,
    )

    if not runs:
        print("No runs found")
        return

    if use_rich:
        # Rich table
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")

        # Run ID column: no_wrap if showing full IDs
        table.add_column("Run ID", style="cyan", no_wrap=full_ids)
        table.add_column("Pipeline", style="green")
        table.add_column("Status")
        table.add_column("Started", style="dim")
        table.add_column("Duration", justify="right")

        for run in runs:
            # Color status
            if run.status == "success":
                status_str = f"[green]{run.status}[/green]"
            elif run.status == "error":
                status_str = f"[red]{run.status}[/red]"
            elif run.status == "running":
                status_str = f"[yellow]{run.status}[/yellow]"
            else:
                status_str = run.status

            # Format ID (full or truncated)
            if full_ids:
                run_id_str = run.id
            else:
                run_id_str = run.id[:12] + "..."

            table.add_row(
                run_id_str,
                run.pipeline_name,
                status_str,
                format_timestamp(run.start_time),
                format_duration(run.duration),
            )

        console.print(table)

    else:
        # Plain text table
        id_width = 34 if full_ids else 14
        print(
            f"{'Run ID':<{id_width}} {'Pipeline':<20} {'Status':<10} {'Started':<20} {'Duration':>10}"
        )
        print("-" * (id_width + 70))

        for run in runs:
            # Format ID (full or truncated)
            if full_ids:
                run_id_str = run.id
            else:
                run_id_str = run.id[:12]

            print(
                f"{run_id_str:<{id_width}} "
                f"{run.pipeline_name[:20]:<20} "
                f"{run.status:<10} "
                f"{format_timestamp(run.start_time):<20} "
                f"{format_duration(run.duration):>10}"
            )

    print()
    print(f"Showing {len(runs)} run(s)")
    if len(runs) >= limit:
        print(f"(Limited to {limit}, use --limit to show more)")

    if not full_ids:
        print()
        print("💡 Tip: Use run ID prefix (min 4 chars) in other commands")
        print(f"   Example: justpipe show {runs[0].id[:8]}")
