from typing import Any, cast


from justpipe._internal.graph.dependency_graph import TransitionResult
from justpipe._internal.runtime.orchestration.barrier_manager import _BarrierManager


class FakeGraph:
    def __init__(self, transition_result: TransitionResult):
        self._transition_result = transition_result
        self.transition_calls: list[str] = []

    def transition(self, owner: str) -> TransitionResult:
        self.transition_calls.append(owner)
        return self._transition_result


class FakeTask:
    def __init__(self) -> None:
        self._done = False
        self.cancel_calls = 0

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancel_calls += 1


async def test_barrier_manager_handle_completion_starts_next(
    fake_orchestrator: Any,
) -> None:
    graph = FakeGraph(TransitionResult(steps_to_start=["next"]))

    manager = _BarrierManager(
        fake_orchestrator,
        cast(Any, graph),
        cast(Any, object()),
    )
    manager.handle_completion("start")

    assert graph.transition_calls == ["start"]
    assert len(fake_orchestrator.schedules) == 1
    assert fake_orchestrator.schedules[0].name == "next"


async def test_barrier_manager_handle_completion_schedules_barrier(
    fake_orchestrator: Any,
) -> None:
    graph = FakeGraph(TransitionResult(barriers_to_schedule=[("barrier", 1.0)]))
    manager = _BarrierManager(
        fake_orchestrator,
        cast(Any, graph),
        cast(Any, object()),
    )
    manager.handle_completion("p1")

    assert graph.transition_calls == ["p1"]
    assert len(fake_orchestrator.spawns) == 1
    # Close the spawned coroutine to silence the "never awaited" warning.
    fake_orchestrator.spawns[0].coro.close()
    assert "barrier" in manager._barrier_tasks


async def test_barrier_manager_stop(fake_orchestrator: Any) -> None:
    task = FakeTask()

    manager = _BarrierManager(
        fake_orchestrator,
        cast(Any, FakeGraph(TransitionResult())),
        cast(Any, object()),
    )
    manager._barrier_tasks["t1"] = cast(Any, task)

    manager.stop()

    assert task.cancel_calls == 1
    assert len(manager._barrier_tasks) == 0
