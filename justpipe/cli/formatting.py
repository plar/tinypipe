"""Shared formatting helpers for CLI commands."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from justpipe._internal.shared.utils import format_duration
from justpipe.types import PipelineTerminalStatus

if TYPE_CHECKING:
    from justpipe.cli.registry import AnnotatedRun, PipelineRegistry
    from justpipe.storage.sqlite import SQLiteBackend


__all__ = ["format_duration"]  # re-exported from _internal.shared.utils


def parse_run_meta(run_meta: str | None) -> Any:
    """Parse run_meta JSON string from a RunRecord.

    Returns parsed dict on success, raw string on decode failure, or None.
    """
    if not run_meta:
        return None
    try:
        return json.loads(run_meta)
    except (json.JSONDecodeError, AttributeError):
        return run_meta


def format_timestamp(dt: datetime) -> str:
    """Format a datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


_STATUS_COLORS = {
    "success": "green",
    "failed": "red",
    "timeout": "yellow",
    "cancelled": "yellow",
    "client_closed": "yellow",
}


def format_status(status: PipelineTerminalStatus) -> str:
    """Format status with rich markup color."""
    value = status.value
    color = _STATUS_COLORS.get(value)
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
