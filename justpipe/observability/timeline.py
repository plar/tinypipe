"""Timeline visualization for pipeline execution analysis."""

import html
import time
from dataclasses import dataclass
from typing import Any

from justpipe._internal.shared.utils import format_duration
from justpipe.observability import Observer, ObserverMeta
from justpipe.observability._step_pairing import pair_step_events
from justpipe.observability._worker_cleanup import remove_worker_entries
from justpipe.types import Event, EventType


@dataclass
class _TimelineSlot:
    """Information about a step for timeline visualization."""

    name: str
    start: float
    end: float
    duration: float
    width: float = 0.0  # Used for HTML rendering


class TimelineEvent:
    """Represents a timeline event for visualization."""

    def __init__(
        self,
        timestamp: float,
        event_type: EventType,
        stage: str,
        duration: float | None = None,
    ):
        self.timestamp = timestamp
        self.event_type = event_type
        self.stage = stage
        self.duration = duration


class TimelineVisualizer(Observer):
    """Observer that generates execution timeline visualizations.

    Creates ASCII, HTML, and Mermaid timeline diagrams showing:
    - Step execution order
    - Parallel worker execution
    - Duration of each step
    - Bottlenecks

    Example:
        from justpipe.observability import TimelineVisualizer

        timeline = TimelineVisualizer()
        pipe.add_observer(timeline)

        async for event in pipe.run(state):
            pass

        # Print ASCII timeline
        print(timeline.render_ascii())

        # Export to HTML
        html = timeline.render_html()

        # Export to Mermaid
        mermaid = timeline.render_mermaid()
    """

    def __init__(self, width: int = 80):
        """Initialize TimelineVisualizer.

        Args:
            width: Width of ASCII timeline in characters
        """
        self.width = width
        self.events: list[TimelineEvent] = []
        self.step_start_times: dict[str, float] = {}
        self.step_end_times: dict[str, float] = {}
        self.pipeline_start: float | None = None
        self.pipeline_end: float | None = None
        self.pipeline_name: str = "Pipeline"

    async def on_pipeline_start(
        self, state: Any, context: Any, meta: ObserverMeta
    ) -> None:
        """Record pipeline start."""
        _ = (state, context)
        # Reset state for per-run timelines when observer is reused.
        self.events.clear()
        self.step_start_times.clear()
        self.step_end_times.clear()
        self.pipeline_end = None
        self.pipeline_start = time.time()

        self.pipeline_name = meta.pipe_name

    def process_event(
        self, event_type: EventType, stage: str, timestamp: float
    ) -> None:
        """Sync method to process a single event into the timeline.

        Used by CLI replay and delegated to by ``on_event``.
        """
        if event_type == EventType.STEP_START:
            self.step_start_times[stage] = timestamp
            self.events.append(TimelineEvent(timestamp, event_type, stage))

        elif event_type == EventType.STEP_END:
            if stage in self.step_start_times:
                start = self.step_start_times[stage]
                duration = timestamp - start
                self.step_end_times[stage] = timestamp
                del self.step_start_times[stage]

                self.events.append(
                    TimelineEvent(timestamp, event_type, stage, duration)
                )

        elif event_type in {
            EventType.STEP_ERROR,
            EventType.BARRIER_WAIT,
            EventType.BARRIER_RELEASE,
        }:
            self.events.append(TimelineEvent(timestamp, event_type, stage))

    async def on_event(
        self, state: Any, context: Any, meta: ObserverMeta, event: Event
    ) -> None:
        """Capture events for timeline."""
        _ = (state, context, meta)
        self.process_event(event.type, event.stage, event.timestamp)
        if event.type == EventType.MAP_COMPLETE and isinstance(event.payload, dict):
            target = event.payload.get("target")
            if isinstance(target, str):
                remove_worker_entries(self.step_start_times, target)

    async def on_pipeline_end(
        self, state: Any, context: Any, meta: ObserverMeta, duration_s: float
    ) -> None:
        """Record pipeline end."""
        _ = (state, context, meta, duration_s)
        self.pipeline_end = time.time()
        self.step_start_times.clear()

    async def on_pipeline_error(
        self, state: Any, context: Any, meta: ObserverMeta, error: Exception
    ) -> None:
        """Record pipeline failure."""
        _ = (state, context, meta, error)
        self.pipeline_end = time.time()
        self.step_start_times.clear()

    def _get_duration(self) -> float:
        """Get total pipeline duration."""
        if self.pipeline_start and self.pipeline_end:
            return self.pipeline_end - self.pipeline_start
        return 0.0

    def _normalize_time(self, timestamp: float) -> float:
        """Normalize timestamp to 0-1 range."""
        if not self.pipeline_start:
            return 0.0

        total = self._get_duration()
        if total == 0:
            return 0.0

        return (timestamp - self.pipeline_start) / total

    def _build_step_info(self) -> list[_TimelineSlot]:
        """Group events into step start/end pairs. Shared by all renderers."""
        raw = [
            (e.stage, e.event_type, e.timestamp)
            for e in self.events
            if e.event_type
            in {EventType.STEP_START, EventType.STEP_END, EventType.STEP_ERROR}
        ]
        spans = pair_step_events(raw)
        step_info = [
            _TimelineSlot(
                name=s.step_name, start=s.start, end=s.end, duration=s.duration
            )
            for s in spans
        ]
        step_info.sort(key=lambda x: x.start)
        return step_info

    def render_ascii(self, max_steps: int = 20) -> str:
        """Generate ASCII timeline.

        Args:
            max_steps: Maximum number of steps to show

        Returns:
            ASCII timeline string
        """
        if not self.events:
            return "No events to display"

        lines = []
        total_duration = self._get_duration()

        # Header
        lines.append("")
        lines.append(
            f"{self.pipeline_name} - Execution Timeline ({format_duration(total_duration)})"
        )
        lines.append("")

        # Build step info and normalize timestamps for ASCII rendering
        raw_steps = self._build_step_info()
        step_info = [
            _TimelineSlot(
                name=s.name,
                start=self._normalize_time(s.start),
                end=self._normalize_time(s.end),
                duration=s.duration,
            )
            for s in raw_steps
        ]

        # Limit steps
        if len(step_info) > max_steps:
            step_info = step_info[:max_steps]
            truncated = len(raw_steps) - max_steps
        else:
            truncated = 0

        # Find bottleneck
        bottleneck = None
        if step_info:
            bottleneck = max(step_info, key=lambda x: x.duration).name

        # Render each step
        bar_width = self.width - 45  # Leave room for labels

        for info in step_info:
            name = info.name
            start = info.start
            end = info.end
            duration_width = (end - start) * bar_width
            start_pos = int(start * bar_width)

            # Truncate name if too long
            if len(name) > 25:
                name = name[:22] + "..."

            # Build bar
            bar = " " * start_pos
            bar += "█" * max(1, int(duration_width))

            # Mark bottleneck
            marker = " ← Bottleneck" if info.name == bottleneck else ""

            # Format line
            duration_str = format_duration(info.duration)
            line = f"{name:<28} {bar:<{bar_width}} {duration_str:>8}{marker}"
            lines.append(line)

        if truncated > 0:
            lines.append(f"... and {truncated} more steps")

        lines.append("")

        # Time axis
        axis = "0" + " " * (bar_width - 10) + format_duration(total_duration)
        lines.append(" " * 28 + axis)
        lines.append("")

        return "\n".join(lines)

    def render_html(self) -> str:
        """Generate HTML timeline with interactive features.

        Returns:
            HTML string
        """
        if not self.events:
            return "<p>No events to display</p>"

        total_duration = self._get_duration()

        # Build step info and convert to percentages for HTML rendering
        raw_steps = self._build_step_info()
        step_info = [
            _TimelineSlot(
                name=s.name,
                start=self._normalize_time(s.start) * 100,
                end=0.0,  # Not used in HTML rendering
                width=(self._normalize_time(s.end) - self._normalize_time(s.start))
                * 100,
                duration=s.duration,
            )
            for s in raw_steps
        ]

        # Find bottleneck
        bottleneck = None
        if step_info:
            bottleneck = max(step_info, key=lambda x: x.duration).name

        # Build step rows HTML
        step_rows = []
        for info in step_info:
            is_bottleneck = info.name == bottleneck
            bottleneck_class = " bottleneck" if is_bottleneck else ""
            safe_name = html.escape(info.name)
            duration_str = format_duration(info.duration)

            step_rows.append(f"""
            <div class="step">
                <div class="step-name">{safe_name}</div>
                <div class="step-bar">
                    <div class="step-bar-fill{bottleneck_class}" style="left: {info.start:.2f}%; width: {info.width:.2f}%;"></div>
                </div>
                <div class="step-duration">{duration_str}</div>
            </div>""")

        steps_html = "".join(step_rows)
        duration_str = format_duration(total_duration)

        # Use template string for clean HTML structure
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{html.escape(self.pipeline_name)} - Timeline</title>
    <style>
        body {{ font-family: monospace; padding: 20px; background: #f5f5f5; }}
        .timeline {{ background: white; padding: 20px; border-radius: 8px; }}
        .header {{ font-size: 18px; font-weight: bold; margin-bottom: 20px; }}
        .step {{ margin: 10px 0; display: flex; align-items: center; }}
        .step-name {{ width: 200px; font-size: 14px; }}
        .step-bar {{ flex: 1; height: 24px; background: #e0e0e0; position: relative; }}
        .step-bar-fill {{ height: 100%; background: #4caf50; position: absolute; }}
        .step-bar-fill.bottleneck {{ background: #ff9800; }}
        .step-duration {{ width: 80px; text-align: right; font-size: 14px; margin-left: 10px; }}
        .axis {{ margin-top: 20px; display: flex; justify-content: space-between; color: #666; }}
    </style>
</head>
<body>
    <div class="timeline">
        <div class="header">{html.escape(self.pipeline_name)} - Execution Timeline ({duration_str})</div>
        {steps_html}
        <div class="axis">
            <span>0s</span>
            <span>{duration_str}</span>
        </div>
    </div>
</body>
</html>"""

    def render_mermaid(self) -> str:
        """Generate Mermaid Gantt chart.

        Returns:
            Mermaid diagram string
        """
        if not self.events:
            return "gantt\n    title No events to display"

        lines = []
        lines.append("gantt")
        lines.append(f"    title {self.pipeline_name} Execution Timeline")
        lines.append("    dateFormat X")
        lines.append("    axisFormat %S")
        lines.append("")

        # Build step info and convert to millisecond offsets for Mermaid
        raw_steps = self._build_step_info()
        step_info = []
        for s in raw_steps:
            if self.pipeline_start:
                start_ms = int((s.start - self.pipeline_start) * 1000)
                end_ms = int((s.end - self.pipeline_start) * 1000)
                step_info.append(
                    _TimelineSlot(
                        name=s.name, start=start_ms, end=end_ms, duration=s.duration
                    )
                )

        # Render in Gantt format
        lines.append("    section Execution")
        for info in step_info:
            name = info.name.replace(":", "_")  # Mermaid doesn't like colons
            lines.append(f"    {name}: {info.start}, {info.end}")

        return "\n".join(lines)
