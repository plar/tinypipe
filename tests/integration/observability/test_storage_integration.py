import pytest
from typing import Any

from justpipe import Pipe
from justpipe.observability import (
    ObserverMeta,
    ReplayObserver,
    StorageObserver,
    compare_runs,
    format_comparison,
)
from justpipe.storage import InMemoryStorage


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
async def sample_pipeline() -> Pipe[Any, Any]:
    pipe: Pipe[Any, Any] = Pipe(name="test_pipeline", allow_multi_root=True)

    @pipe.step()
    async def step1(state: Any) -> None:
        state["count"] = state.get("count", 0) + 1

    @pipe.step()
    async def step2(state: Any) -> None:
        state["count"] = state.get("count", 0) * 2

    return pipe


@pytest.mark.parametrize(
    ("raises_step_error", "expected_status", "expected_step_error_events"),
    [
        (False, "success", 0),
        (True, "error", 1),
    ],
    ids=["success", "step_error_recorded"],
)
async def test_storage_observer_persists_run_and_events(
    storage: InMemoryStorage,
    raises_step_error: bool,
    expected_status: str,
    expected_step_error_events: int,
) -> None:
    observer = StorageObserver(storage)
    pipe: Pipe[Any, Any] = Pipe(name="storage_observer_pipeline")
    pipe.add_observer(observer)

    @pipe.step("test")
    async def test_step() -> None:
        if raises_step_error:
            raise ValueError("Test error")

    async for _ in pipe.run({}):
        pass

    run_id = observer.get_run_id()
    assert run_id is not None

    run = await storage.get_run(run_id)
    assert run is not None
    assert run.pipeline_name == "storage_observer_pipeline"
    assert run.status == expected_status

    events = await storage.get_events(run_id)
    event_types = {event.event_type for event in events}
    assert "start" in event_types
    assert "finish" in event_types

    step_error_events = [event for event in events if event.event_type == "step_error"]
    assert len(step_error_events) == expected_step_error_events


async def test_storage_observer_saves_initial_state(
    storage: InMemoryStorage, sample_pipeline: Pipe[Any, Any]
) -> None:
    observer = StorageObserver(storage)
    sample_pipeline.add_observer(observer)

    state = {"count": 5}
    async for _ in sample_pipeline.run(state):
        pass

    runs = await storage.list_runs()
    assert len(runs) == 1
    run_id = runs[0].id

    import json

    initial_state_bytes = await storage.load_artifact(run_id, "initial_state.json")
    assert initial_state_bytes is not None
    initial_state = json.loads(initial_state_bytes.decode("utf-8"))
    assert initial_state["count"] == 5


async def test_replay_observer_loads_state(
    storage: InMemoryStorage, sample_pipeline: Pipe[Any, Any]
) -> None:
    storage_observer = StorageObserver(storage)
    sample_pipeline.add_observer(storage_observer)

    initial_state = {"count": 5}
    async for _ in sample_pipeline.run(initial_state):
        pass

    runs = await storage.list_runs()
    assert len(runs) == 1
    source_run_id = runs[0].id

    replay_observer = ReplayObserver(storage, source_run_id)
    await replay_observer.on_pipeline_start({}, {}, ObserverMeta(pipe_name="test"))

    assert replay_observer.get_initial_state() == {"count": 5}


async def test_compare_runs_same_pipeline(
    storage: InMemoryStorage, sample_pipeline: Pipe[Any, Any]
) -> None:
    storage_observer = StorageObserver(storage)
    sample_pipeline.add_observer(storage_observer)

    async for _ in sample_pipeline.run({"count": 5}):
        pass
    async for _ in sample_pipeline.run({"count": 10}):
        pass

    runs = await storage.list_runs()
    run1_id = runs[1].id
    run2_id = runs[0].id

    comparison = await compare_runs(storage, run1_id, run2_id)
    assert comparison.status_same is True
    assert comparison.pipeline_same is True
    assert comparison.run1.pipeline_name == "test_pipeline"


async def test_compare_runs_step_differences(
    storage: InMemoryStorage, sample_pipeline: Pipe[Any, Any]
) -> None:
    storage_observer = StorageObserver(storage)
    sample_pipeline.add_observer(storage_observer)

    async for _ in sample_pipeline.run({"count": 5}):
        pass
    async for _ in sample_pipeline.run({"count": 10}):
        pass

    runs = await storage.list_runs()
    run1_id = runs[1].id
    run2_id = runs[0].id

    comparison = await compare_runs(storage, run1_id, run2_id)
    assert comparison.new_steps == []
    assert comparison.removed_steps == []


async def test_compare_runs_duration_diff(storage: InMemoryStorage) -> None:
    import time

    start_time = time.time()

    run1_id = await storage.create_run("test_pipeline", {"initial": "state1"})
    await storage.update_run(run1_id, status="success", end_time=start_time + 1.0)

    run2_id = await storage.create_run("test_pipeline", {"initial": "state2"})
    await storage.update_run(run2_id, status="success", end_time=start_time + 2.0)

    comparison = await compare_runs(storage, run1_id, run2_id)
    assert 0.9 < comparison.duration_diff < 1.1


async def test_compare_runs_different_status(storage: InMemoryStorage) -> None:
    run1_id = await storage.create_run("test_pipeline", {})
    await storage.update_run(run1_id, status="success")

    run2_id = await storage.create_run("test_pipeline", {})
    await storage.update_run(run2_id, status="error")

    comparison = await compare_runs(storage, run1_id, run2_id)

    assert comparison.status_same is False
    assert comparison.run1.status == "success"
    assert comparison.run2.status == "error"


async def test_format_comparison_output(storage: InMemoryStorage) -> None:
    run1_id = await storage.create_run("pipeline_v1", {})
    await storage.update_run(run1_id, status="success")

    run2_id = await storage.create_run("pipeline_v2", {})
    await storage.update_run(run2_id, status="error")

    comparison = await compare_runs(storage, run1_id, run2_id)
    output = format_comparison(comparison)

    assert "Run Comparison" in output
    assert run1_id[:8] in output
    assert run2_id[:8] in output
    assert "pipeline_v1" in output
    assert "pipeline_v2" in output


async def test_compare_runs_error_on_missing(storage: InMemoryStorage) -> None:
    with pytest.raises(ValueError, match="Run not found"):
        await compare_runs(storage, "missing1", "missing2")
