from justpipe._internal.runtime.telemetry.execution_log import (
    _ExecutionLog,
    _TerminalSignal,
    _resolve_outcome,
)
from justpipe.types import (
    FailureKind,
    FailureReason,
    FailureRecord,
    FailureSource,
    PipelineTerminalStatus,
)


def test_resolve_outcome_prefers_terminal_signal() -> None:
    log = _ExecutionLog()
    log.record_failure(
        kind=FailureKind.STEP,
        source=FailureSource.USER_CODE,
        reason=FailureReason.STEP_ERROR,
        error_message="boom",
    )
    log.signal_terminal(_TerminalSignal.TIMEOUT, FailureReason.TIMEOUT)

    resolved = _resolve_outcome(log)

    assert resolved.status is PipelineTerminalStatus.TIMEOUT
    assert resolved.reason == FailureReason.TIMEOUT.value
    assert resolved.failure_kind is FailureKind.NONE
    assert resolved.pipeline_error is None
    assert len(resolved.errors) == 1


def test_resolve_outcome_uses_failure_priority() -> None:
    log = _ExecutionLog()
    log.record_failure(
        kind=FailureKind.STEP,
        source=FailureSource.USER_CODE,
        reason=FailureReason.STEP_ERROR,
        step="worker",
        error_message="step failed",
    )
    log.record_failure(
        kind=FailureKind.STARTUP,
        source=FailureSource.USER_CODE,
        reason=FailureReason.STARTUP_HOOK_ERROR,
        error_message="startup failed",
    )

    resolved = _resolve_outcome(log)

    assert resolved.status is PipelineTerminalStatus.FAILED
    assert resolved.reason == FailureReason.STARTUP_HOOK_ERROR.value
    assert resolved.failure_kind is FailureKind.STARTUP


def test_resolve_outcome_builds_runtime_error_from_message() -> None:
    log = _ExecutionLog()
    log.record_failure(
        kind=FailureKind.SHUTDOWN,
        source=FailureSource.USER_CODE,
        reason=FailureReason.SHUTDOWN_HOOK_ERROR,
        error_message="cleanup failed",
    )

    resolved = _resolve_outcome(log)

    assert isinstance(resolved.pipeline_error, RuntimeError)
    assert str(resolved.pipeline_error) == "cleanup failed"


def test_resolve_outcome_keeps_diagnostics_in_success() -> None:
    log = _ExecutionLog()
    diagnostic = FailureRecord(
        kind=FailureKind.INFRA,
        source=FailureSource.FRAMEWORK,
        reason=FailureReason.CLASSIFIER_ERROR.value,
        error="classifier failed",
    )
    log.record_diagnostic(diagnostic)

    resolved = _resolve_outcome(log)

    assert resolved.status is PipelineTerminalStatus.SUCCESS
    assert resolved.errors == [diagnostic]
