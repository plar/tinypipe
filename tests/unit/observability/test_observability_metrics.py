import pytest

from justpipe.observability import MetricsCollector, ObserverMeta
from justpipe.types import Event, EventType


PIPE_META = ObserverMeta(pipe_name="metrics_pipe")


def static_clock() -> float:
    return 100.0


@pytest.mark.asyncio
async def test_pipeline_start_resets_all_counters() -> None:
    collector = MetricsCollector(clock=static_clock)
    collector.total_duration = 5.0
    collector.token_count = 2
    collector.active_workers.add("worker")
    collector.event_counts["start"] = 1

    await collector.on_pipeline_start(state={}, context=None, meta=PIPE_META)

    assert collector.total_duration == 0.0
    assert collector.token_count == 0
    assert collector.active_workers == set()
    assert collector.event_counts == {}


@pytest.mark.asyncio
async def test_on_event_tracks_core_metrics_and_cleanup() -> None:
    collector = MetricsCollector(clock=static_clock)
    await collector.on_pipeline_start(state={}, context=None, meta=PIPE_META)

    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.STEP_START, "task", timestamp=1.0),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.TOKEN, "task", payload="tok", timestamp=1.1),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.BARRIER_WAIT, "join", timestamp=1.2),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.MAP_WORKER, "worker[0]", timestamp=1.3),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(
            EventType.MAP_COMPLETE,
            "fanout",
            payload={"target": "worker"},
            timestamp=1.4,
        ),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.BARRIER_RELEASE, "join", timestamp=1.8),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.STEP_END, "task", timestamp=2.0),
    )
    await collector.on_event(
        state={},
        context=None,
        meta=PIPE_META,
        event=Event(EventType.STEP_ERROR, "task", payload="boom", timestamp=2.1),
    )

    assert collector.token_count == 1
    assert collector.error_count == 1
    assert collector.error_counts_by_step["task"] == 1
    assert collector.get_step_stats("task")["total"] == pytest.approx(1.0)
    assert collector.barrier_wait_times["join"] == pytest.approx(0.6)
    assert collector.active_workers == set()


def test_step_stats_and_bottleneck_helpers() -> None:
    collector = MetricsCollector(clock=static_clock)
    collector.step_durations["a"] = [1.0, 2.0]
    collector.step_durations["b"] = [3.5]
    collector.total_duration = 10.0

    a_stats = collector.get_step_stats("a")
    missing_stats = collector.get_step_stats("missing")

    assert a_stats["count"] == 2
    assert a_stats["avg"] == pytest.approx(1.5)
    assert missing_stats["count"] == 0
    assert collector.get_bottleneck() == "b"
    assert collector.get_bottleneck_percentage() == pytest.approx(35.0)


def test_summary_and_to_dict_include_key_sections() -> None:
    collector = MetricsCollector(clock=static_clock)
    collector.total_duration = 2.5
    collector.step_durations["parse"] = [1.0]
    collector.event_counts["step_start"] = 1
    collector.error_counts_by_step["parse"] = 1
    collector.error_count = 1
    collector.token_count = 2
    collector.max_parallel_workers = 3
    collector.barrier_wait_times["join"] = 0.2

    summary = collector.summary(detailed=True)
    payload = collector.to_dict()

    assert "Pipeline Completed in 2.50s" in summary
    assert "Event Breakdown:" in summary
    assert "Errors by Step:" in summary
    assert payload["steps_executed"] == 1
    assert payload["bottleneck"] == "parse"
    assert payload["barrier_wait_times"]["join"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_pipeline_error_sets_duration_and_clears_runtime_state() -> None:
    collector = MetricsCollector(clock=lambda: 12.0)
    await collector.on_pipeline_start(state={}, context=None, meta=PIPE_META)
    collector.start_time = 10.0
    collector.step_start_times["task"] = 11.0
    collector.active_workers.add("task")
    collector.barrier_start_times["join"] = 11.5
    await collector.on_pipeline_error(
        state={},
        context=None,
        meta=PIPE_META,
        error=RuntimeError("boom"),
    )

    assert collector.total_duration == pytest.approx(2.0)
    assert collector.step_start_times == {}
    assert collector.active_workers == set()
    assert collector.barrier_start_times == {}
