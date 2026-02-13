"""Main CLI entry point for justpipe commands."""

import os
from pathlib import Path
from typing import Any

import click

from justpipe.cli.registry import PipelineRegistry
from justpipe.types import PipelineTerminalStatus


def get_storage_dir() -> Path:
    """Get storage directory from environment or default."""
    raw = os.getenv("JUSTPIPE_STORAGE_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".justpipe"


def get_registry() -> PipelineRegistry:
    """Get pipeline registry for the storage directory."""
    storage_dir = get_storage_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)
    return PipelineRegistry(storage_dir)


@click.group()
@click.version_option()
def cli() -> None:
    """justpipe - Observability CLI for justpipe pipelines."""
    pass


@cli.command("list")
@click.option("--pipeline", "-p", help="Filter by pipeline name")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["success", "failed", "timeout", "cancelled", "client_closed"]),
    help="Filter by status",
)
@click.option("--limit", "-n", default=10, help="Maximum number of runs to show")
@click.option("--full", is_flag=True, help="Show full run IDs (32 chars)")
def list_command_cli(pipeline: Any, status: Any, limit: Any, full: Any) -> None:
    """list pipeline runs."""
    from justpipe.cli.commands.list import list_command

    enum_status = PipelineTerminalStatus(status) if status else None
    list_command(get_registry(), pipeline, enum_status, limit, full)


@cli.command("show")
@click.argument("run_id")
def show_command_cli(run_id: Any) -> None:
    """Show details of a specific run."""
    from justpipe.cli.commands.show import show_command

    show_command(get_registry(), run_id)


@cli.command("timeline")
@click.argument("run_id")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["ascii", "html", "mermaid"]),
    default="ascii",
    help="Output format",
)
def timeline_command_cli(run_id: Any, format: Any) -> None:
    """Show execution timeline for a run."""
    from justpipe.cli.commands.timeline import timeline_command

    timeline_command(get_registry(), run_id, format)


@cli.command("compare")
@click.argument("run1_id")
@click.argument("run2_id")
def compare_command_cli(run1_id: Any, run2_id: Any) -> None:
    """Compare two pipeline runs."""
    from justpipe.cli.commands.compare import compare_command

    compare_command(get_registry(), run1_id, run2_id)


@cli.command("export")
@click.argument("run_id")
@click.option("--output", "-o", help="Output file path (default: run_<id>.json)")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json"]),
    default="json",
    help="Export format",
)
def export_command_cli(run_id: Any, output: Any, format: Any) -> None:
    """Export run data to file."""
    from justpipe.cli.commands.export import export_command

    export_command(get_registry(), run_id, output, format)


@cli.command("cleanup")
@click.option("--older-than", type=int, help="Delete runs older than N days")
@click.option(
    "--status",
    type=click.Choice(["success", "failed", "timeout", "cancelled", "client_closed"]),
    help="Only delete runs with this status",
)
@click.option(
    "--keep", default=10, help="Keep at least N most recent runs (default: 10)"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be deleted without deleting"
)
def cleanup_command_cli(older_than: Any, status: Any, keep: Any, dry_run: Any) -> None:
    """Clean up old pipeline runs."""
    from justpipe.cli.commands.cleanup import cleanup_command

    enum_status = PipelineTerminalStatus(status) if status else None
    cleanup_command(get_registry(), older_than, enum_status, keep, dry_run)


@cli.command("stats")
@click.option("--pipeline", "-p", help="Filter by pipeline name")
@click.option("--days", default=7, help="Number of days to include (default: 7)")
def stats_command_cli(pipeline: Any, days: Any) -> None:
    """Show pipeline statistics."""
    from justpipe.cli.commands.stats import stats_command

    stats_command(get_registry(), pipeline, days)


@cli.command("pipelines")
def pipelines_command_cli() -> None:
    """List all known pipelines."""
    from justpipe.cli.commands.pipelines import pipelines_command

    pipelines_command(get_registry())


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
