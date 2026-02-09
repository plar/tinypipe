"""Helpers for map-worker bookkeeping cleanup in observers."""

from collections.abc import MutableMapping, MutableSet
from typing import Any


def remove_worker_entries(
    collection: MutableSet[str] | MutableMapping[str, Any],
    target: str,
) -> None:
    """Remove target and indexed map-worker entries from a collection."""
    prefix = f"{target}["
    to_remove = [key for key in collection if key == target or key.startswith(prefix)]

    if isinstance(collection, MutableSet):
        for key in to_remove:
            collection.discard(key)
        return

    for key in to_remove:
        collection.pop(key, None)
