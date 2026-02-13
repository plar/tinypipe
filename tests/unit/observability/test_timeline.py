"""Unit tests for TimelineVisualizer._build_step_info()."""

from justpipe.observability.timeline import TimelineVisualizer
from justpipe.types import EventType


class TestBuildStepInfo:
    def test_groups_start_end_pairs(self) -> None:
        viz = TimelineVisualizer()
        viz.pipeline_start = 100.0
        viz.pipeline_end = 110.0

        viz.process_event(EventType.STEP_START, "step_a", 100.5)
        viz.process_event(EventType.STEP_END, "step_a", 102.0)
        viz.process_event(EventType.STEP_START, "step_b", 103.0)
        viz.process_event(EventType.STEP_END, "step_b", 106.0)

        infos = viz._build_step_info()
        assert len(infos) == 2
        assert infos[0].name == "step_a"
        assert infos[1].name == "step_b"
        # Raw timestamps preserved
        assert infos[0].start == 100.5
        assert infos[0].end == 102.0
        assert infos[1].start == 103.0

    def test_excludes_incomplete_steps(self) -> None:
        viz = TimelineVisualizer()
        viz.pipeline_start = 100.0
        viz.pipeline_end = 110.0

        viz.process_event(EventType.STEP_START, "step_a", 100.5)
        # No STEP_END for step_a
        viz.process_event(EventType.STEP_START, "step_b", 103.0)
        viz.process_event(EventType.STEP_END, "step_b", 106.0)

        infos = viz._build_step_info()
        assert len(infos) == 1
        assert infos[0].name == "step_b"

    def test_sorted_by_start_time(self) -> None:
        viz = TimelineVisualizer()
        viz.pipeline_start = 100.0
        viz.pipeline_end = 110.0

        viz.process_event(EventType.STEP_START, "late", 105.0)
        viz.process_event(EventType.STEP_END, "late", 106.0)
        viz.process_event(EventType.STEP_START, "early", 101.0)
        viz.process_event(EventType.STEP_END, "early", 102.0)

        infos = viz._build_step_info()
        assert [i.name for i in infos] == ["early", "late"]

    def test_empty_events(self) -> None:
        viz = TimelineVisualizer()
        assert viz._build_step_info() == []
