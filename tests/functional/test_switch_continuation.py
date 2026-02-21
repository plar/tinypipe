"""Tests for switch handler continuation (Issue #7).

Switch targets are mutually exclusive — only one runs per execution.
When multiple switch handlers share a downstream step via `to=`, the
ALL barrier must recognize that unreachable siblings won't complete
and allow the downstream step to proceed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from justpipe import EventType, Pipe, Stop


async def _collect_events(
    pipe: Pipe[Any, Any], state: Any = None, **kwargs: Any
) -> list[Any]:
    return [e async for e in pipe.run(state, **kwargs)]


def _stages(events: list[Any], event_type: EventType) -> list[str]:
    return [e.stage for e in events if e.type == event_type]


# ---------------------------------------------------------------------------
# Issue #7 reproduction: switch handler with `to=` terminates early
# ---------------------------------------------------------------------------


@dataclass
class NumberState:
    value: int = 0
    path: str = ""
    result: str = ""


async def test_switch_handler_continues_to_next_step():
    """Direct reproduction of Issue #7: even path should reach result_log."""
    pipe = Pipe[NumberState, None](NumberState, type(None))

    @pipe.step(to="number_detector")
    async def start(s: NumberState):
        s.value = 4

    @pipe.switch(to={True: "even_handler", False: "odd_handler"})
    async def number_detector(s: NumberState):
        return s.value % 2 == 0

    @pipe.step(to="result_log")
    async def even_handler(s: NumberState):
        s.path = "even"

    @pipe.step(to="result_log")
    async def odd_handler(s: NumberState):
        s.path = "odd"

    @pipe.step()
    async def result_log(s: NumberState):
        s.result = f"Got {s.path}"

    events = await _collect_events(pipe, NumberState(value=0))
    started = _stages(events, EventType.STEP_START)
    ended = _stages(events, EventType.STEP_END)

    assert "result_log" in started, f"result_log never started. Started: {started}"
    assert "result_log" in ended, f"result_log never ended. Ended: {ended}"
    assert "even_handler" in ended
    assert "odd_handler" not in started  # Only the even path should run


async def test_switch_both_paths_reach_downstream():
    """Both even and odd paths should reach result_log when taken."""
    pipe = Pipe[NumberState, None](NumberState, type(None))

    @pipe.step(to="number_detector")
    async def start(s: NumberState):
        pass  # value is set via initial state

    @pipe.switch(to={True: "even_handler", False: "odd_handler"})
    async def number_detector(s: NumberState):
        return s.value % 2 == 0

    @pipe.step(to="result_log")
    async def even_handler(s: NumberState):
        s.path = "even"

    @pipe.step(to="result_log")
    async def odd_handler(s: NumberState):
        s.path = "odd"

    @pipe.step()
    async def result_log(s: NumberState):
        s.result = f"Got {s.path}"

    # Test even path
    events = await _collect_events(pipe, NumberState(value=4))
    ended = _stages(events, EventType.STEP_END)
    assert "even_handler" in ended
    assert "result_log" in ended

    # Test odd path
    events = await _collect_events(pipe, NumberState(value=3))
    ended = _stages(events, EventType.STEP_END)
    assert "odd_handler" in ended
    assert "result_log" in ended


async def test_switch_handlers_to_different_targets():
    """Handlers pointing to different downstream steps (no sibling group)."""

    @dataclass
    class S:
        value: int = 0
        result: str = ""

    pipe = Pipe[S, None](S, type(None))

    @pipe.step(to="detector")
    async def start(s: S):
        pass

    @pipe.switch(to={True: "path_a", False: "path_b"})
    async def detector(s: S):
        return s.value > 0

    @pipe.step(to="finish")
    async def path_a(s: S):
        s.result = "positive"

    @pipe.step()
    async def path_b(s: S):
        s.result = "non-positive"

    @pipe.step()
    async def finish(s: S):
        s.result += " done"

    events = await _collect_events(pipe, S(value=5))
    ended = _stages(events, EventType.STEP_END)
    assert "path_a" in ended
    assert "finish" in ended
    assert "path_b" not in ended


async def test_switch_with_stop_target():
    """One switch route is Stop, the other has `to=` continuation."""

    @dataclass
    class S:
        value: int = 0
        reached: bool = False

    pipe = Pipe[S, None](S, type(None))

    @pipe.step(to="checker")
    async def start(s: S):
        pass

    @pipe.switch(to={True: "process", False: Stop})
    async def checker(s: S):
        return s.value > 0

    @pipe.step(to="done")
    async def process(s: S):
        s.reached = True

    @pipe.step()
    async def done(s: S):
        pass

    # True path: should reach process and done
    events = await _collect_events(pipe, S(value=1))
    ended = _stages(events, EventType.STEP_END)
    assert "process" in ended
    assert "done" in ended

    # False path: should stop after checker
    events = await _collect_events(pipe, S(value=0))
    ended = _stages(events, EventType.STEP_END)
    assert "process" not in ended
    assert "done" not in ended
