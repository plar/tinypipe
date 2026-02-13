from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from justpipe.types import Event, NodeKind


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    # Concrete event object queued for publication.
    event: Event


@dataclass(frozen=True, slots=True)
class InvocationContext:
    # Unique ID for this concrete step invocation.
    invocation_id: str

    # Invocation that directly scheduled this invocation.
    parent_invocation_id: str | None = None

    # Composite owner/grouping invocation (map/sub owner).
    owner_invocation_id: str | None = None

    # Retry attempt number for this invocation.
    attempt: int = 1

    # Nested execution scope path.
    scope: tuple[str, ...] = ()

    # Kind of node being executed.
    node_kind: NodeKind = NodeKind.STEP


@dataclass(frozen=True, slots=True)
class StepCompleted:
    # Concrete step node name that finished.
    name: str

    # Logical owner key used for tracker/barrier accounting.
    owner: str

    # Step return value.
    result: Any

    # Injected payload used for invocation (map item, etc.).
    payload: dict[str, Any] | None = None

    # Whether this completion should decrement logical owner counters.
    track_owner: bool = True

    # Invocation identity/lineage for emitted terminal events.
    invocation: InvocationContext | None = None

    # True when a terminal step event (STEP_ERROR) was already emitted upstream.
    already_terminal: bool = False
