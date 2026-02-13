"""Pipelines command for CLI."""

from __future__ import annotations

from justpipe.cli.formatting import format_timestamp
from justpipe.cli.registry import PipelineRegistry
from justpipe.types import PipelineTerminalStatus


def pipelines_command(registry: PipelineRegistry) -> None:
    """List all known pipelines."""
    pipelines = registry.list_pipelines()

    if not pipelines:
        print("No pipelines found")
        return

    try:
        from rich.console import Console
        from rich.table import Table

        use_rich = True
    except ImportError:
        use_rich = False

    # Gather stats per pipeline
    rows: list[tuple[str, str, int, str, str]] = []
    for pipe in pipelines:
        from justpipe.storage.sqlite import SQLiteBackend

        backend = SQLiteBackend(pipe.path)
        runs = backend.list_runs(limit=10000)
        total = len(runs)
        last_run_str = "-"
        success_rate_str = "-"

        if runs:
            last_run_str = format_timestamp(runs[0].start_time)
            success_count = sum(
                1 for r in runs if r.status == PipelineTerminalStatus.SUCCESS
            )
            if total > 0:
                success_rate_str = f"{success_count / total * 100:.1f}%"

        rows.append((pipe.name, pipe.hash[:16], total, last_run_str, success_rate_str))

    if use_rich:
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Pipeline", style="green")
        table.add_column("Hash", style="cyan")
        table.add_column("Runs", justify="right")
        table.add_column("Last Run", style="dim")
        table.add_column("Success Rate", justify="right")

        for name, hash_str, total, last_run, rate in rows:
            table.add_row(name, hash_str, str(total), last_run, rate)

        console.print(table)
    else:
        print(
            f"{'Pipeline':<30} {'Hash':<18} {'Runs':>5}  {'Last Run':<20} {'Success Rate':>12}"
        )
        print("-" * 90)
        for name, hash_str, total, last_run, rate in rows:
            print(f"{name:<30} {hash_str:<18} {total:>5}  {last_run:<20} {rate:>12}")

    print()
    print(f"{len(pipelines)} pipeline(s) found")
