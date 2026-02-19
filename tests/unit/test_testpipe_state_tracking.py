"""Unit tests for TestPipe state tracking with fake event streams."""

from typing import Any

from justpipe import Pipe, Event, EventType, TestPipe


async def test_run_tracks_final_state_from_step_end_events() -> None:
    pipe: Pipe[int, Any] = Pipe(state_type=int)

    @pipe.step()
    async def step_a(state: int) -> None:
        return None

    async def fake_run(state: int, context: Any = None, **kwargs: Any) -> Any:
        yield Event(EventType.START, "system", state)
        yield Event(EventType.STEP_END, "step_a", state + 1)
        yield Event(EventType.FINISH, "system")

    pipe.run = fake_run  # type: ignore[assignment]

    tester = TestPipe(pipe)
    result = await tester.run(1)
    assert result.final_state == 2


async def test_run_ignores_nested_subpipeline_step_end_state() -> None:
    pipe: Pipe[int, Any] = Pipe(state_type=int)

    @pipe.step()
    async def outer(state: int) -> None:
        return None

    async def fake_run(state: int, context: Any = None, **kwargs: Any) -> Any:
        yield Event(EventType.START, "system", state)
        # Simulates forwarded sub-pipeline STEP_END event.
        yield Event(EventType.STEP_END, "outer:inner", 999)
        # Top-level owner completion should win.
        yield Event(EventType.STEP_END, "outer", state + 1)
        yield Event(EventType.FINISH, "system")

    pipe.run = fake_run  # type: ignore[assignment]

    tester = TestPipe(pipe)
    result = await tester.run(41)
    assert result.final_state == 42
