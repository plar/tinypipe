"""Storage backends for persisting pipeline runs and events."""

from justpipe.storage.interface import StorageBackend, StoredRun, StoredEvent
from justpipe.storage.memory import InMemoryStorage

# SQLiteStorage requires aiosqlite (optional dependency)
try:
    from justpipe.storage.sqlite import SQLiteStorage

    __all__ = [
        "StorageBackend",
        "StoredRun",
        "StoredEvent",
        "SQLiteStorage",
        "InMemoryStorage",
    ]
except ImportError:
    # aiosqlite not installed
    __all__ = [
        "StorageBackend",
        "StoredRun",
        "StoredEvent",
        "InMemoryStorage",
    ]
