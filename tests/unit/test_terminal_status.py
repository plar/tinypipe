from justpipe.types import (
    FailureKind,
    FailureSource,
    PipelineTerminalStatus,
    PipelineEndData,
)


def test_pipeline_end_data_roundtrip() -> None:
    data = PipelineEndData(
        status=PipelineTerminalStatus.SUCCESS,
        duration_s=1.23,
        error=None,
        reason=None,
    )
    assert data.status == PipelineTerminalStatus.SUCCESS
    assert data.duration_s == 1.23
    assert data.error is None
    assert data.reason is None
    assert data.failure_kind is FailureKind.NONE
    assert data.failure_source is FailureSource.NONE
