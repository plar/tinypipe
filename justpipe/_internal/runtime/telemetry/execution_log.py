from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from justpipe.types import (
    FailureKind,
    FailureReason,
    FailureRecord,
    FailureSource,
    PipelineTerminalStatus,
)

_FAILURE_PRIORITY: dict[FailureKind, int] = {
    FailureKind.VALIDATION: 0,
    FailureKind.STARTUP: 1,
    FailureKind.STEP: 2,
    FailureKind.SHUTDOWN: 3,
    FailureKind.INFRA: 4,
    FailureKind.NONE: 1_000_000,
}


@dataclass
class _FailureEntry:
    kind: FailureKind
    source: FailureSource
    reason: FailureReason
    error_message: str | None
    step: str | None
    error: Exception | None


class _TerminalSignal(Enum):
    TIMEOUT = auto()
    CANCELLED = auto()
    CLIENT_CLOSED = auto()


_TERMINAL_SIGNAL_STATUS: dict[_TerminalSignal, PipelineTerminalStatus] = {
    _TerminalSignal.TIMEOUT: PipelineTerminalStatus.TIMEOUT,
    _TerminalSignal.CANCELLED: PipelineTerminalStatus.CANCELLED,
    _TerminalSignal.CLIENT_CLOSED: PipelineTerminalStatus.CLIENT_CLOSED,
}


@dataclass
class _ExecutionLog:
    failures: list[_FailureEntry] = field(default_factory=list)
    diagnostics: list[FailureRecord] = field(default_factory=list)
    terminal_signal: _TerminalSignal | None = None
    terminal_reason: FailureReason | None = None
    execution_started: bool = False
    closing: bool = False
    cancelled: bool = False

    def record_failure(
        self,
        *,
        kind: FailureKind,
        source: FailureSource,
        reason: FailureReason,
        error_message: str | None = None,
        step: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.failures.append(
            _FailureEntry(
                kind=kind,
                source=source,
                reason=reason,
                error_message=error_message,
                step=step,
                error=error,
            )
        )

    def record_diagnostic(self, record: FailureRecord) -> None:
        self.diagnostics.append(record)

    def signal_terminal(self, signal: _TerminalSignal, reason: FailureReason) -> None:
        self.terminal_signal = signal
        self.terminal_reason = reason

    def mark_started(self) -> None:
        self.execution_started = True

    def mark_closing(self) -> None:
        self.closing = True

    def mark_cancelled(self) -> None:
        self.cancelled = True


@dataclass(frozen=True)
class _ResolvedOutcome:
    status: PipelineTerminalStatus
    reason: str | None
    failure_kind: FailureKind
    failure_source: FailureSource
    failed_step: str | None
    pipeline_error: Exception | None
    errors: list[FailureRecord]


def _resolve_outcome(log: _ExecutionLog) -> _ResolvedOutcome:
    errors: list[FailureRecord] = [
        FailureRecord(
            kind=f.kind,
            source=f.source,
            reason=f.reason.value,
            error=f.error_message,
            step=f.step,
        )
        for f in log.failures
    ]
    errors.extend(log.diagnostics)

    if log.terminal_signal is not None:
        return _ResolvedOutcome(
            status=_TERMINAL_SIGNAL_STATUS[log.terminal_signal],
            reason=log.terminal_reason.value if log.terminal_reason else None,
            failure_kind=FailureKind.NONE,
            failure_source=FailureSource.NONE,
            failed_step=None,
            pipeline_error=None,
            errors=errors,
        )

    if log.failures:
        primary = min(
            log.failures,
            key=lambda failure: _FAILURE_PRIORITY.get(failure.kind, 1_000_000),
        )
        if primary.error is not None:
            pipeline_error = primary.error
        elif primary.error_message is not None:
            pipeline_error = RuntimeError(primary.error_message)
        else:
            pipeline_error = None

        return _ResolvedOutcome(
            status=PipelineTerminalStatus.FAILED,
            reason=primary.reason.value,
            failure_kind=primary.kind,
            failure_source=primary.source,
            failed_step=primary.step,
            pipeline_error=pipeline_error,
            errors=errors,
        )

    return _ResolvedOutcome(
        status=PipelineTerminalStatus.SUCCESS,
        reason=None,
        failure_kind=FailureKind.NONE,
        failure_source=FailureSource.NONE,
        failed_step=None,
        pipeline_error=None,
        errors=errors,
    )
