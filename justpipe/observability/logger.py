"""Structured event logger for pipeline observability."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, TextIO
from collections.abc import Callable

from justpipe.observability import Observer, ObserverMeta
from justpipe.types import Event, EventType


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Structured representation of one emitted log line."""

    timestamp: float
    relative_time: str
    event_type: EventType
    stage: str
    payload: Any
    message: str


LogSink = Callable[[LogRecord], None]


class StreamLogSink:
    """Sink that writes rendered messages to a text stream."""

    def __init__(self, stream: TextIO):
        self._stream = stream

    def __call__(self, record: LogRecord) -> None:
        print(record.message, file=self._stream, flush=True)


class LogLevel:
    """Log level constants."""

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class EventLogger(Observer):
    """Observer that emits structured log records for pipeline events.

    Notes:
    - Logging is sink-driven. If ``sink`` is ``None``, records are produced but
      not emitted anywhere.
    - Use ``EventLogger.stderr_sink()`` for CLI-style output.
    """

    LEVEL_MAP = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
    }

    COLORS = {
        "RESET": "\033[0m",
        "BOLD": "\033[1m",
        "RED": "\033[91m",
        "GREEN": "\033[92m",
        "YELLOW": "\033[93m",
        "BLUE": "\033[94m",
        "MAGENTA": "\033[95m",
        "CYAN": "\033[96m",
        "GRAY": "\033[90m",
    }

    def __init__(
        self,
        level: str = "INFO",
        sink: LogSink | None = None,
        use_colors: bool = False,
    ):
        """Initialize the event logger.

        Args:
            level: Minimum event level to emit.
            sink: Target sink for structured records. When omitted, logging is
                effectively disabled.
            use_colors: Enables ANSI coloring in rendered messages.
        """
        self.level = self.LEVEL_MAP.get(level.upper(), LogLevel.INFO)
        self.sink = sink
        self.use_colors = use_colors
        self.start_time: float | None = None

    @staticmethod
    def stderr_sink() -> StreamLogSink:
        """Build a stderr sink for convenience in app wiring."""
        return StreamLogSink(sys.stderr)

    def _emit(self, record: LogRecord) -> None:
        if self.sink is not None:
            self.sink(record)

    def _format_time(self, timestamp: float) -> str:
        if self.start_time is None:
            self.start_time = timestamp

        elapsed = timestamp - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    def _colorize(self, text: str, color: str) -> str:
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    def _should_log(self, event_type: EventType) -> bool:
        if self.level == LogLevel.DEBUG:
            return True
        if self.level == LogLevel.INFO:
            return event_type in {
                EventType.START,
                EventType.FINISH,
                EventType.STEP_START,
                EventType.STEP_END,
                EventType.STEP_ERROR,
                EventType.BARRIER_WAIT,
                EventType.BARRIER_RELEASE,
                EventType.MAP_START,
                EventType.MAP_COMPLETE,
                EventType.SUSPEND,
            }
        if self.level == LogLevel.WARNING:
            return event_type in {
                EventType.STEP_ERROR,
                EventType.BARRIER_WAIT,
                EventType.SUSPEND,
            }
        return event_type == EventType.STEP_ERROR

    def _format_event(self, event: Event) -> str:
        timestamp = self._colorize(self._format_time(event.timestamp), "GRAY")
        event_type = event.type.value.upper()

        if event.type == EventType.STEP_ERROR:
            event_type = self._colorize(event_type.ljust(16), "RED")
            stage = self._colorize(event.stage, "RED")
        elif event.type in {EventType.BARRIER_WAIT, EventType.SUSPEND}:
            event_type = self._colorize(event_type.ljust(16), "YELLOW")
            stage = self._colorize(event.stage, "YELLOW")
        elif event.type in {EventType.START, EventType.FINISH}:
            event_type = self._colorize(event_type.ljust(16), "BOLD")
            stage = self._colorize(event.stage, "BOLD")
        elif event.type in {EventType.STEP_START, EventType.MAP_START}:
            event_type = self._colorize(event_type.ljust(16), "CYAN")
            stage = event.stage
        elif event.type in {
            EventType.STEP_END,
            EventType.MAP_COMPLETE,
            EventType.BARRIER_RELEASE,
        }:
            event_type = self._colorize(event_type.ljust(16), "GREEN")
            stage = event.stage
        else:
            event_type = event_type.ljust(16)
            stage = event.stage

        data_str = ""
        if event.payload is not None:
            if isinstance(event.payload, dict):
                items = [
                    f"{k}={v}" for k, v in event.payload.items() if k != "trace_id"
                ]
                if items:
                    data_str = f" ({', '.join(items)})"
            elif isinstance(event.payload, str) and len(event.payload) < 100:
                data_str = f" ({event.payload})"

        return f"[{timestamp}] {event_type} {stage}{data_str}"

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        _ = (state, context, meta)

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        _ = (state, context, meta)
        if not self._should_log(event.type):
            return

        record = LogRecord(
            timestamp=event.timestamp,
            relative_time=self._format_time(event.timestamp),
            event_type=event.type,
            stage=event.stage,
            payload=event.payload,
            message=self._format_event(event),
        )
        self._emit(record)

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        _ = (state, context, meta)
        if self.level > LogLevel.INFO:
            return

        import time as _time

        timestamp = (
            self.start_time + duration_s
            if self.start_time is not None
            else _time.time()
        )
        message = self._colorize(f"Pipeline completed in {duration_s:.2f}s", "GREEN")
        self._emit(
            LogRecord(
                timestamp=timestamp,
                relative_time=self._format_time(timestamp),
                event_type=EventType.FINISH,
                stage="system",
                payload={"duration_s": duration_s},
                message=message,
            )
        )

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        _ = (state, context, meta)
        import time as _time

        timestamp = _time.time()
        message = self._colorize(f"Pipeline failed: {error}", "RED")
        self._emit(
            LogRecord(
                timestamp=timestamp,
                relative_time=self._format_time(timestamp),
                event_type=EventType.STEP_ERROR,
                stage="system",
                payload={"error": str(error)},
                message=message,
            )
        )
