from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Generic, TypeVar
import uuid

from justpipe._internal.runtime.telemetry.execution_log import _ExecutionLog
from justpipe._internal.runtime.engine.run_state import _RunSession, _RunStateMachine

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


@dataclass
class _RunContext(Generic[StateT, ContextT]):
    """Centralizes all mutable per-run state."""

    state: StateT | None = None
    context: ContextT | None = None
    closing: bool = False
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session: _RunSession = field(default_factory=_RunSession)
    runtime_sm: _RunStateMachine = field(default_factory=_RunStateMachine)
    log: _ExecutionLog = field(default_factory=_ExecutionLog)
    _event_seq: int = 0
    _invocation_seq: int = 0
    _attempts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def next_event_seq(self) -> int:
        self._event_seq += 1
        return self._event_seq

    def next_invocation_id(self) -> str:
        self._invocation_seq += 1
        return f"{self.run_id}:{self._invocation_seq}"

    def next_attempt(self, stage: str) -> int:
        self._attempts[stage] += 1
        return self._attempts[stage]
