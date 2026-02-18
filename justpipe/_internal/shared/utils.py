import os
from pathlib import Path
from typing import Any
from collections.abc import Callable, Iterable

from justpipe.types import CancellationToken, InjectionMetadata, InjectionSource


def format_duration(seconds: float | None) -> str:
    """Format duration for display.

    Shared by CLI formatting and timeline visualization.
    """
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def resolve_storage_path() -> Path:
    """Resolve the base storage directory from env or default.

    Reads JUSTPIPE_STORAGE_PATH env var, falls back to ~/.justpipe.
    """
    raw = os.getenv("JUSTPIPE_STORAGE_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".justpipe"


def _resolve_name(target: str | Callable[..., Any]) -> str:
    """Resolve a name string from a string or callable target."""
    if isinstance(target, str):
        return target

    if hasattr(target, "func") and hasattr(target.func, "__name__"):
        return str(target.func.__name__)

    if hasattr(target, "__name__"):
        return str(target.__name__)

    if callable(target):
        return str(type(target).__name__)

    raise ValueError(f"Cannot resolve name for {target}")


def suggest_similar(
    target: str, candidates: Iterable[str], cutoff: float = 0.6
) -> str | None:
    """Suggest a similar string from candidates using fuzzy matching.

    Args:
        target: The string to find matches for
        candidates: Collection of candidate strings
        cutoff: Similarity threshold (0.0 to 1.0)

    Returns:
        Best matching candidate or None if no good match found
    """
    from difflib import get_close_matches

    matches = get_close_matches(target, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _resolve_injection_kwargs(
    inj_meta: InjectionMetadata,
    state: Any,
    context: Any,
    error: Exception | None = None,
    step_name: str | None = None,
    cancellation_token: CancellationToken | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for param_name, source in inj_meta.items():
        if source == InjectionSource.STATE:
            kwargs[param_name] = state
        elif source == InjectionSource.CONTEXT:
            kwargs[param_name] = context
        elif source == InjectionSource.ERROR:
            kwargs[param_name] = error
        elif source == InjectionSource.STEP_NAME:
            kwargs[param_name] = step_name
        elif source == InjectionSource.CANCEL:
            kwargs[param_name] = cancellation_token
    return kwargs
