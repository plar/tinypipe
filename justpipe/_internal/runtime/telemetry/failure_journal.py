from __future__ import annotations

from justpipe._internal.runtime.telemetry.execution_log import _ExecutionLog
from justpipe.types import (
    FailureClassificationConfig,
    FailureClassificationContext,
    FailureKind,
    FailureReason,
    FailureRecord,
    FailureSource,
    FailureSourceClassifier,
)


class _FailureJournal:
    """Owns failure classification policy and recording."""

    _DEFAULT_EXTERNAL_DEP_PREFIXES: tuple[str, ...] = (
        "httpx",
        "requests",
        "aiohttp",
        "openai",
        "anthropic",
        "google",
        "botocore",
        "boto3",
        "redis",
        "sqlalchemy",
        "psycopg",
        "asyncpg",
    )

    def __init__(self, config: FailureClassificationConfig | None = None) -> None:
        cfg = config or FailureClassificationConfig()
        self._source_classifier: FailureSourceClassifier | None = cfg.source_classifier
        self._external_dep_prefixes = (
            self._DEFAULT_EXTERNAL_DEP_PREFIXES + cfg.external_dependency_prefixes
        )

    def record_failure(
        self,
        log: _ExecutionLog,
        *,
        kind: FailureKind,
        source: FailureSource,
        reason: FailureReason,
        error_message: str | None = None,
        step: str | None = None,
        error: Exception | None = None,
    ) -> None:
        resolved_source, classifier_diagnostic = self._resolve_failure_source(
            error=error,
            kind=kind,
            reason=reason,
            step=step,
            default=source,
        )
        log.record_failure(
            kind=kind,
            source=resolved_source,
            reason=reason,
            error_message=error_message,
            step=step,
            error=error,
        )
        if classifier_diagnostic is not None:
            log.record_diagnostic(classifier_diagnostic)

    def _resolve_failure_source(
        self,
        *,
        error: Exception | None,
        kind: FailureKind,
        reason: FailureReason,
        step: str | None,
        default: FailureSource,
    ) -> tuple[FailureSource, FailureRecord | None]:
        resolved_source = self._classify_failure_source_builtin(error, default)
        classifier = self._source_classifier
        if classifier is None:
            return resolved_source, None

        context = FailureClassificationContext(
            error=error,
            kind=kind,
            reason=reason,
            step=step,
            default_source=resolved_source,
        )
        try:
            user_source = classifier(context)
        except Exception as exc:
            diagnostic = FailureRecord(
                kind=FailureKind.INFRA,
                source=FailureSource.FRAMEWORK,
                reason=FailureReason.CLASSIFIER_ERROR,
                error=(
                    "failure_classification.source_classifier raised an exception: "
                    f"{type(exc).__name__}: {exc}"
                ),
                step=step,
            )
            return resolved_source, diagnostic

        if user_source is None:
            return resolved_source, None

        if isinstance(user_source, FailureSource):
            return user_source, None

        diagnostic = FailureRecord(
            kind=FailureKind.INFRA,
            source=FailureSource.FRAMEWORK,
            reason=FailureReason.CLASSIFIER_ERROR,
            error=(
                "failure_classification.source_classifier "
                f"returned invalid value: {user_source!r}"
            ),
            step=step,
        )
        return resolved_source, diagnostic

    def _classify_failure_source_builtin(
        self, error: Exception | None, default: FailureSource
    ) -> FailureSource:
        if error is None:
            return default
        module = type(error).__module__
        if module.startswith(self._external_dep_prefixes):
            return FailureSource.EXTERNAL_DEP
        return default
