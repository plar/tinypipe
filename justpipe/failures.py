"""Failure classification types for pipeline error handling.

Re-exported from ``justpipe.types`` for convenience. Import from here
when you need failure-related types without pulling them from the
top-level ``justpipe`` namespace.

Example::

    from justpipe.failures import FailureKind, FailureRecord
"""

from justpipe.types import (
    FailureClassificationConfig,
    FailureClassificationContext,
    FailureKind,
    FailureReason,
    FailureRecord,
    FailureSource,
    FailureSourceClassifier,
)

__all__ = [
    "FailureClassificationConfig",
    "FailureClassificationContext",
    "FailureKind",
    "FailureReason",
    "FailureRecord",
    "FailureSource",
    "FailureSourceClassifier",
]
