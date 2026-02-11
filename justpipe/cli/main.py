"""Main CLI entry point for justpipe commands."""

import asyncio
import os
import click
from pathlib import Path
from typing import Any


def get_storage_dir() -> Path:
    """Get storage directory from environment or default."""
    default_dir = Path.home() / ".justpipe"
    storage_dir = os.getenv("JUSTPIPE_STORAGE_DIR", str(default_dir))
    return Path(storage_dir)


def get_storage() -> Any:
    """Get storage backend instance."""
    from justpipe.storage import SQLiteStorage

    storage_dir = get_storage_dir()
    return SQLiteStorage(str(storage_dir))


# CLI commands
async def list_runs(
    pipeline: str | None = None,
    status: str | None = None,
    limit: int = 10,
    full_ids: bool = False,
) -> None:
    """list pipeline runs."""
    from justpipe.cli.commands.list import list_command

    storage = get_storage()
    await list_command(storage, pipeline, status, limit, full_ids)


async def show_run(run_id: str) -> None:
    """Show details of a specific run."""
    from justpipe.cli.commands.show import show_command

    storage = get_storage()
    await show_command(storage, run_id)


async def timeline_run(run_id: str, format: str = "ascii") -> None:
    """Show timeline visualization of a run."""
    from justpipe.cli.commands.timeline import timeline_command

    storage = get_storage()
    await timeline_command(storage, run_id, format)


async def compare_runs_cli(run1_id: str, run2_id: str) -> None:
    """Compare two pipeline runs."""
    from justpipe.cli.commands.compare import compare_command

    storage = get_storage()
    await compare_command(storage, run1_id, run2_id)


async def export_run(
    run_id: str, output_file: str | None = None, format: str = "json"
) -> None:
    """Export run data to file."""
    from justpipe.cli.commands.export import export_command

    storage = get_storage()
    await export_command(storage, run_id, output_file, format)


async def cleanup_runs(
    older_than_days: int | None = None,
    status: str | None = None,
    keep: int = 10,
    dry_run: bool = False,
) -> None:
    """Clean up old pipeline runs."""
    from justpipe.cli.commands.cleanup import cleanup_command

    storage = get_storage()
    await cleanup_command(storage, older_than_days, status, keep, dry_run)


async def show_stats(pipeline: str | None = None, days: int = 7) -> None:
    """Show pipeline statistics."""
    from justpipe.cli.commands.stats import stats_command

    storage = get_storage()
    await stats_command(storage, pipeline, days)


@click.group()
@click.version_option()
def cli() -> None:
    """justpipe - Observability CLI for justpipe pipelines."""
    pass


@cli.command("list")
@click.option(
    "--pipeline",
    "-p",
    help="Filter by pipeline name",
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(["running", "success", "error", "suspended"]),
    help="Filter by status",
)
@click.option(
    "--limit",
    "-n",
    default=10,
    help="Maximum number of runs to show",
)
@click.option(
    "--full",
    is_flag=True,
    help="Show full run IDs (32 chars)",
)
def list_command_cli(pipeline: Any, status: Any, limit: Any, full: Any) -> None:
    """list pipeline runs."""
    asyncio.run(list_runs(pipeline, status, limit, full))


@cli.command("show")
@click.argument("run_id")
def show_command_cli(run_id: Any) -> None:
    """Show details of a specific run."""
    asyncio.run(show_run(run_id))


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
    asyncio.run(timeline_run(run_id, format))


@cli.command("compare")
@click.argument("run1_id")
@click.argument("run2_id")
def compare_command_cli(run1_id: Any, run2_id: Any) -> None:
    """Compare two pipeline runs."""
    asyncio.run(compare_runs_cli(run1_id, run2_id))


@cli.command("export")
@click.argument("run_id")
@click.option(
    "--output",
    "-o",
    help="Output file path (default: run_<id>.json)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json"]),
    default="json",
    help="Export format",
)
def export_command_cli(run_id: Any, output: Any, format: Any) -> None:
    """Export run data to file."""
    asyncio.run(export_run(run_id, output, format))


@cli.command("cleanup")
@click.option(
    "--older-than",
    type=int,
    help="Delete runs older than N days",
)
@click.option(
    "--status",
    type=click.Choice(["running", "success", "error", "suspended"]),
    help="Only delete runs with this status",
)
@click.option(
    "--keep",
    default=10,
    help="Keep at least N most recent runs (default: 10)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without deleting",
)
def cleanup_command_cli(older_than: Any, status: Any, keep: Any, dry_run: Any) -> None:
    """Clean up old pipeline runs."""
    asyncio.run(cleanup_runs(older_than, status, keep, dry_run))


@cli.command("stats")
@click.option(
    "--pipeline",
    "-p",
    help="Filter by pipeline name",
)
@click.option(
    "--days",
    default=7,
    help="Number of days to include (default: 7)",
)
def stats_command_cli(pipeline: Any, days: Any) -> None:
    """Show pipeline statistics."""
    asyncio.run(show_stats(pipeline, days))


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
