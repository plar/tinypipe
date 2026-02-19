import time
from io import StringIO

import pytest

from justpipe.observability import EventLogger, LogRecord, ObserverMeta, StreamLogSink
from justpipe.types import Event, EventType


PIPE_META = ObserverMeta(pipe_name="logger_pipe")


@pytest.mark.parametrize(
    ("level", "event_type", "expected"),
    [
        ("DEBUG", EventType.TOKEN, True),
        ("INFO", EventType.STEP_START, True),
        ("INFO", EventType.TOKEN, False),
        ("WARNING", EventType.STEP_ERROR, True),
        ("WARNING", EventType.STEP_END, False),
        ("ERROR", EventType.STEP_ERROR, True),
        ("ERROR", EventType.START, False),
    ],
)
def test_should_log_respects_level(
    level: str, event_type: EventType, expected: bool
) -> None:
    logger = EventLogger(level=level, sink=None, use_colors=False)
    assert logger._should_log(event_type) is expected


def test_format_event_handles_dict_payload_and_ignores_trace_id() -> None:
    logger = EventLogger(level="DEBUG", sink=None, use_colors=False)
    event = Event(
        EventType.STEP_END,
        "worker",
        payload={"count": 2, "trace_id": "abc", "ok": True},
        timestamp=10.0,
    )

    rendered = logger._format_event(event)

    assert "STEP_END" in rendered
    assert "worker" in rendered
    assert "count=2" in rendered
    assert "ok=True" in rendered
    assert "trace_id" not in rendered


async def test_on_event_emits_structured_record_to_sink() -> None:
    records: list[LogRecord] = []
    logger = EventLogger(level="INFO", sink=records.append, use_colors=False)
    event = Event(EventType.START, "system", timestamp=100.0)

    await logger.on_event(state={}, context=None, meta=PIPE_META, event=event)

    assert len(records) == 1
    assert records[0].event_type is EventType.START
    assert records[0].stage == "system"
    assert "START" in records[0].message


async def test_on_pipeline_end_and_error_emit_messages() -> None:
    records: list[LogRecord] = []
    logger = EventLogger(level="INFO", sink=records.append, use_colors=False)

    await logger.on_pipeline_end(
        state={}, context=None, meta=PIPE_META, duration_s=1.25
    )
    await logger.on_pipeline_error(
        state={},
        context=None,
        meta=PIPE_META,
        error=RuntimeError("boom"),
    )

    assert any("Pipeline completed in 1.25s" in record.message for record in records)
    assert any("Pipeline failed: boom" in record.message for record in records)


def test_colorize_passthrough_when_colors_disabled() -> None:
    logger = EventLogger(level="INFO", sink=None, use_colors=False)
    assert logger._colorize("hello", "GREEN") == "hello"


async def test_stream_sink_writes_rendered_message() -> None:
    stream = StringIO()
    logger = EventLogger(
        level="INFO",
        sink=StreamLogSink(stream),
        use_colors=False,
    )

    await logger.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.START, "system", timestamp=1.0),
    )

    assert "START" in stream.getvalue()


async def test_error_timestamp_is_current_not_start() -> None:
    """on_pipeline_error should log at current time, not pipeline start."""
    records: list[LogRecord] = []
    logger = EventLogger(level="INFO", sink=records.append)
    meta = ObserverMeta(pipe_name="test", run_id="r1")

    # Simulate a pipeline that started 5 seconds ago
    logger.start_time = time.time() - 5.0

    await logger.on_pipeline_error(None, None, meta, RuntimeError("boom"))

    assert len(records) == 1
    record = records[0]
    # The error timestamp should be close to now, not to start_time
    assert abs(record.timestamp - time.time()) < 2.0
    # The relative time should show ~5s elapsed, not 0s
    assert "05" in record.relative_time  # contains "05" for ~5 seconds


async def test_end_timestamp_not_corrupted_when_start_none() -> None:
    """on_pipeline_end with start_time=None must not corrupt start_time."""
    records: list[LogRecord] = []
    logger = EventLogger(level="INFO", sink=records.append)
    meta = ObserverMeta(pipe_name="test", run_id="r1")

    assert logger.start_time is None

    await logger.on_pipeline_end(None, None, meta, duration_s=0.5)

    assert len(records) == 1
    # start_time should be an epoch timestamp if set, not a relative value
    if logger.start_time is not None:
        assert logger.start_time > 1_000_000_000  # epoch sanity check
