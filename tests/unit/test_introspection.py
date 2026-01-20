import pytest
from typing import Any
from justpipe import Pipe


def test_steps_empty_pipe() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    steps = list(pipe.steps())
    assert steps == []


def test_steps_basic() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("first", to="second", timeout=5.0, retries=2)
    async def first() -> None:
        pass

    @pipe.step("second")
    async def second() -> None:
        pass

    steps = {s.name: s for s in pipe.steps()}

    assert "first" in steps
    assert "second" in steps

    first_info = steps["first"]
    assert first_info.name == "first"
    assert first_info.timeout == 5.0
    assert first_info.retries == 2
    assert first_info.targets == ["second"]
    assert first_info.kind == "step"
    assert first_info.has_error_handler is False

    second_info = steps["second"]
    assert second_info.name == "second"
    assert second_info.timeout is None
    assert second_info.retries == 0
    assert second_info.targets == []
    assert second_info.kind == "step"


def test_steps_with_error_handler() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    def handle_error(e: Exception) -> None:
        pass

    @pipe.step("test", on_error=handle_error)
    async def test_step() -> None:
        pass

    steps = list(pipe.steps())
    assert len(steps) == 1
    assert steps[0].has_error_handler is True


def test_steps_map_kind() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("worker")
    async def worker(item: Any) -> None:
        pass

    @pipe.map("producer", using=worker)
    async def producer() -> list[int]:
        return [1, 2, 3]

    steps = {s.name: s for s in pipe.steps()}

    assert steps["producer"].kind == "map"
    assert "worker" in steps["producer"].targets


def test_steps_switch_kind() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("path_a")
    async def path_a() -> None:
        pass

    @pipe.step("path_b")
    async def path_b() -> None:
        pass

    @pipe.switch("router", routes={"a": path_a, "b": path_b}, default=path_a)
    async def router() -> str:
        return "a"

    steps = {s.name: s for s in pipe.steps()}

    assert steps["router"].kind == "switch"
    assert "path_a" in steps["router"].targets
    assert "path_b" in steps["router"].targets


def test_steps_with_barrier_timeout() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("first", to="join")
    async def first() -> None:
        pass

    @pipe.step("second", to="join")
    async def second() -> None:
        pass

    @pipe.step("join", barrier_timeout=10.0)
    async def join() -> None:
        pass

    steps = {s.name: s for s in pipe.steps()}
    assert steps["join"].barrier_timeout == 10.0
    assert steps["first"].barrier_timeout is None


def test_topology_empty_pipe() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    assert pipe.topology == {}


def test_topology_basic() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("first", to="second")
    async def first() -> None:
        pass

    @pipe.step("second", to=["third", "fourth"])
    async def second() -> None:
        pass

    @pipe.step("third")
    async def third() -> None:
        pass

    @pipe.step("fourth")
    async def fourth() -> None:
        pass

    topology = pipe.topology

    assert topology["first"] == ["second"]
    assert set(topology["second"]) == {"third", "fourth"}
    assert "third" not in topology
    assert "fourth" not in topology


def test_topology_is_copy() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("first", to="second")
    async def first() -> None:
        pass

    @pipe.step("second")
    async def second() -> None:
        pass

    topology = pipe.topology
    topology["first"] = ["modified"]

    # Original should be unchanged
    assert pipe.topology["first"] == ["second"]


def test_validate_on_run_disabled_by_default() -> None:
    import asyncio

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("first", to="nonexistent")
    async def first() -> None:
        pass

    # Without validate_on_run, the pipe will run without validation
    # and fail later when trying to find the target
    async def run() -> None:
        async for _ in pipe.run({}):
            pass

    # This should not raise immediately (validation doesn't happen)
    # The error would come during execution
    asyncio.run(run())


def test_validate_on_run_enabled() -> None:
    import asyncio

    pipe: Pipe[Any, Any] = Pipe(validate_on_run=True)

    @pipe.step("first", to="nonexistent")
    async def first() -> None:
        pass

    async def run() -> None:
        async for _ in pipe.run({}):
            pass

    # With validate_on_run=True, validation happens before running
    with pytest.raises(ValueError, match="targets unknown step"):
        asyncio.run(run())


def test_validate_on_run_valid_pipe() -> None:
    import asyncio

    pipe: Pipe[Any, Any] = Pipe(validate_on_run=True)

    @pipe.step("first", to="second")
    async def first() -> None:
        pass

    @pipe.step("second")
    async def second() -> None:
        pass

    async def run() -> list[Any]:
        events: list[Any] = []
        async for event in pipe.run({}):
            events.append(event)
        return events

    # Should run successfully
    events = asyncio.run(run())
    assert len(events) > 0
