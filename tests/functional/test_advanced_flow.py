import pytest
import asyncio
from typing import List, Any, Union, Dict
from justpipe import Pipe, EventType, Suspend


@pytest.mark.asyncio
async def test_dag_barrier_multiple_paths() -> None:
    """
    Verify that a node waits for ALL its static parents to complete.
    Flow: start -> [a, b]; a -> c; b -> d -> c.
    'c' should only run once, after both 'a' and 'd' finish.
    """
    pipe: Pipe[Any, Any] = Pipe()
    executed_counts: Dict[str, int] = {}

    async def track_execution(name: str) -> None:
        executed_counts[name] = executed_counts.get(name, 0) + 1

    @pipe.step("start", to=["a", "b"])
    async def start() -> None:
        await track_execution("start")

    @pipe.step("a", to="c")
    async def a() -> None:
        await track_execution("a")

    @pipe.step("b", to="d")
    async def b() -> None:
        await track_execution("b")

    @pipe.step("d", to="c")
    async def d() -> None:
        await track_execution("d")

    @pipe.step("c")
    async def c() -> None:
        await track_execution("c")

    async for _ in pipe.run({}):
        pass

    assert executed_counts["c"] == 1, (
        f"Step 'c' should only run once, but ran {executed_counts.get('c', 0)} times"
    )


@pytest.mark.asyncio
async def test_map_parallelism() -> None:
    """Test Spawning N parallel tasks via @pipe.map decorator."""
    pipe: Pipe[Any, Any] = Pipe()
    processed: List[Union[int, str]] = []

    @pipe.map("start", using="worker", to="end")
    async def start() -> List[int]:
        return [1, 2, 3]

    @pipe.step("worker")
    async def worker(item: int) -> None:
        await asyncio.sleep(0.01)
        processed.append(item)

    @pipe.step("end")
    async def end() -> None:
        processed.append("end")

    async for _ in pipe.run({}):
        pass

    assert set(processed[:3]) == {1, 2, 3}
    assert processed[3] == "end"


@pytest.mark.asyncio
async def test_run_subpipeline() -> None:
    """Test nested pipeline execution via @pipe.sub decorator."""
    sub_pipe: Pipe[Any, Any] = Pipe()

    @sub_pipe.step("sub_step")
    async def sub_step() -> Any:
        yield "sub_token"

    main_pipe: Pipe[Any, Any] = Pipe()

    @main_pipe.sub("runner", using=sub_pipe)
    async def runner() -> Dict[str, Any]:
        return {}

    events = []
    async for event in main_pipe.run({}):
        events.append(event)

    # Check for namespaced events
    stages = [e.stage for e in events]
    assert "runner:sub_step" in stages
    tokens = [e.data for e in events if e.type == EventType.TOKEN]
    assert "sub_token" in tokens


@pytest.mark.asyncio
async def test_suspend_execution() -> None:
    """Test early termination via Suspend return type."""
    pipe: Pipe[Any, Any] = Pipe()
    executed: List[bool] = []

    @pipe.step("start", to="next_step")
    async def start() -> Suspend:
        return Suspend(reason="wait_for_input")

    @pipe.step("next_step")
    async def next_step() -> None:
        executed.append(True)

    events = []
    async for event in pipe.run({}):
        events.append(event)

    assert not executed
    assert any(e.type == EventType.SUSPEND for e in events)


@pytest.mark.asyncio
async def test_step_timeout() -> None:
    """Test step execution timeout."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("slow", timeout=0.1)
    async def slow() -> None:
        await asyncio.sleep(0.5)

    errors = []
    async for event in pipe.run({}):
        if event.type == EventType.ERROR:
            errors.append(event)

    assert len(errors) > 0
    # TimeoutError check
    assert any(
        isinstance(e.data, str)
        and ("timed out" in e.data.lower() or "timeout" in e.data.lower())
        for e in errors
    )


@pytest.mark.asyncio
async def test_map_empty_list() -> None:
    """Verify @pipe.map with empty list does not schedule tasks."""
    pipe: Pipe[Any, Any] = Pipe()
    executed = False

    @pipe.map("start", using="worker")
    async def start() -> List[int]:
        return []

    @pipe.step("worker")
    async def worker(item: int) -> None:
        nonlocal executed
        executed = True

    async for _ in pipe.run({}, start="start"):
        pass

    assert not executed


@pytest.mark.asyncio
async def test_map_no_unknown_args() -> None:
    """Verify @pipe.map item is ignored if target has no unknown args."""
    pipe: Pipe[Any, Any] = Pipe()
    executed_count = 0

    @pipe.map("start", using="worker")
    async def start() -> List[int]:
        return [1, 2]

    @pipe.step("worker")
    async def worker() -> None:
        nonlocal executed_count
        executed_count += 1

    async for _ in pipe.run({}, start="start"):
        pass

    assert executed_count == 2


@pytest.mark.asyncio
async def test_map_multiple_unknown_args() -> None:
    """Verify @pipe.map injects into the first unknown arg."""
    pipe: Pipe[Any, Any] = Pipe()
    results = []

    @pipe.map("start", using="worker")
    async def start() -> List[int]:
        return [10]

    @pipe.step("worker")
    async def worker(a: int, b: int = 99) -> None:
        # 'a' should get the item because it's first unknown
        results.append((a, b))

    async for _ in pipe.run({}, start="start"):
        pass

    assert results == [(10, 99)]


@pytest.mark.asyncio
async def test_subpipeline_failure() -> None:
    """Verify sub-pipeline failure bubbles up as ERROR."""
    sub_pipe: Pipe[Any, Any] = Pipe()

    @sub_pipe.step("fail")
    async def fail() -> None:
        raise ValueError("Boom")

    main_pipe: Pipe[Any, Any] = Pipe()

    @main_pipe.sub("runner", using=sub_pipe)
    async def runner() -> Dict[str, Any]:
        return {}

    events = []
    async for event in main_pipe.run({}):
        events.append(event)

    errors = [e for e in events if e.type == EventType.ERROR]
    assert len(errors) > 0
    assert "Boom" in errors[0].data