from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto

from justpipe.types import FailureReason, PipelineEndData, PipelineTerminalStatus


class _RunPhase(Enum):
    INIT = auto()
    STARTUP = auto()
    EXECUTING = auto()
    SHUTDOWN = auto()
    TERMINAL = auto()


@dataclass
class _RunSession:
    """Holds per-run lifecycle state."""

    start_time: float = 0.0
    terminal: PipelineEndData | None = None

    def __post_init__(self) -> None:
        self.start_time = time.monotonic()

    def close(
        self,
        status: PipelineTerminalStatus,
        error: str | None = None,
        reason: FailureReason | None = None,
    ) -> PipelineEndData:
        if self.terminal is not None:
            raise RuntimeError("Run already terminal")
        duration = max(time.monotonic() - self.start_time, 0.0)
        self.terminal = PipelineEndData(
            status=status, duration_s=duration, error=error, reason=reason
        )
        return self.terminal


class _RunStateMachine:
    """Deterministic phase transitions for a pipeline run."""

    def __init__(self) -> None:
        self.phase = _RunPhase.INIT

    def start_startup(self) -> None:
        self._transition(to=_RunPhase.STARTUP, allowed={_RunPhase.INIT})

    def start_execution(self) -> None:
        self._transition(to=_RunPhase.EXECUTING, allowed={_RunPhase.STARTUP})

    def start_shutdown(self) -> None:
        self._transition(
            to=_RunPhase.SHUTDOWN, allowed={_RunPhase.EXECUTING, _RunPhase.STARTUP}
        )

    def finish_terminal(self) -> None:
        self._transition(
            to=_RunPhase.TERMINAL,
            allowed={_RunPhase.SHUTDOWN, _RunPhase.EXECUTING, _RunPhase.STARTUP},
        )

    def _transition(self, to: _RunPhase, allowed: set[_RunPhase]) -> None:
        if self.phase not in allowed:
            raise RuntimeError(
                f"Invalid transition from {self.phase.name} to {to.name}"
            )
        if self.phase == _RunPhase.TERMINAL:
            raise RuntimeError("Run already terminal")
        self.phase = to
