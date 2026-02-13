"""Shared formatting helpers for CLI commands."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from justpipe.types import PipelineTerminalStatus

if TYPE_CHECKING:
    from justpipe.cli.registry import AnnotatedRun, PipelineRegistry
    from justpipe.storage.sqlite import SQLiteBackend


def format_duration(seconds: float | None) -> str:
    """Format duration for display."""
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def format_timestamp(dt: datetime) -> str:
    """Format a datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_status(status: PipelineTerminalStatus) -> str:
    """Format status with rich markup color."""
    value = status.value
    color_map = {
        "success": "green",
        "failed": "red",
        "timeout": "yellow",
        "cancelled": "yellow",
        "client_closed": "yellow",
    }
    color = color_map.get(value, "")
    if color:
        return f"[{color}]{value}[/{color}]"
    return value


def short_id(run_id: str, full: bool = False) -> str:
    """Shorten a run ID for display."""
    if full:
        return run_id
    return run_id[:12] + "..."


def resolve_or_exit(
    registry: PipelineRegistry, run_id_prefix: str
) -> tuple[AnnotatedRun, SQLiteBackend] | None:
    """Resolve run by prefix. Prints error and returns None on failure."""
    try:
        result = registry.resolve_run(run_id_prefix)
    except ValueError as e:
        print(f"Error: {e}")
        return None
    if result is None:
        print(f"Run not found: {run_id_prefix}")
        return None
    return result
