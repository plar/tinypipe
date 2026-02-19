"""Functional tests for routing logic (switches, dynamic returns)."""

import pytest
from typing import Any
from justpipe import Pipe, EventType, Stop, DefinitionError
from justpipe.types import _Next


async def test_dynamic_routing(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[bool] = []

    @pipe.step("start")
    async def start() -> _Next:
        return _Next("target")

    @pipe.step("target")
    async def target() -> None:
        executed.append(True)

    async for _ in pipe.run(state, start="start"):
        pass
    assert executed


async def test_declarative_switch(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[str] = []

    @pipe.switch("start", to={"a": "step_a", "b": "step_b"})
    async def start() -> str:
        return "b"

    @pipe.step("step_a")
    async def step_a() -> None:
        executed.append("a")

    @pipe.step("step_b")
    async def step_b() -> None:
        executed.append("b")

    async for _ in pipe.run(state):
        pass
    assert executed == ["b"]


async def test_switch_callable_routes() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("a")
    async def a() -> None:
        pass

    @pipe.step("b")
    async def b() -> None:
        pass

    def route_logic(val: bool) -> str:
        return "a" if val else "b"

    @pipe.switch("switch", to=route_logic)
    async def switch() -> bool:
        return True

    # We just ensure it runs without error and routes correctly (implied by no error)
    async for _ in pipe.run(None, start="switch"):
        pass


async def test_switch_no_match_no_default() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to={"x": "y"})
    async def switch() -> str:
        return "z"  # No match

    @pipe.step("y")
    async def y() -> None:
        pass  # Define step to pass validation

    events = []
    async for ev in pipe.run(None):
        if ev.type == EventType.STEP_ERROR:
            events.append(ev)

    assert len(events) > 0
    assert "matches no route" in str(events[0].payload)


async def test_switch_returns_stop() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to={"stop": Stop})
    async def switch() -> str:
        return "stop"

    events = []
    async for ev in pipe.run(None):
        events.append(ev)

    # Should finish successfully when routing to Stop
    assert any(e.type == EventType.FINISH for e in events)
    # Should not have any errors
    assert not any(e.type == EventType.STEP_ERROR for e in events)


async def test_switch_callable_returns_stop() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to=lambda x: Stop)
    async def switch() -> str:
        return "ignored"

    # Should run without error and stop
    events = [e async for e in pipe.run(None)]

    # Should finish successfully
    assert any(e.type == EventType.FINISH for e in events)
    # Should not have any errors
    assert not any(e.type == EventType.STEP_ERROR for e in events)


@pytest.mark.parametrize(
    "dynamic_return",
    [_Next("dynamic_next"), "dynamic_next"],
    ids=["_Next", "raw_string"],
)
async def test_dynamic_override_static(dynamic_return: Any) -> None:
    """Returning a dynamic route (via _Next or raw string) skips the static route."""
    pipe: Pipe[Any, Any] = Pipe()
    trace: list[str] = []

    @pipe.step("start", to="static_next")
    async def start(state: Any) -> Any:
        trace.append("start")
        return dynamic_return

    @pipe.step("static_next")
    async def static_next(state: Any) -> None:
        trace.append("static_next")

    @pipe.step("dynamic_next")
    async def dynamic_next(state: Any) -> None:
        trace.append("dynamic_next")

    async for _ in pipe.run({}, start="start"):
        pass

    assert trace == ["start", "dynamic_next"]


# ============================================================================
# Switch Route Validation Tests
# ============================================================================


async def test_switch_route_validation_static() -> None:
    """Test that static switch routes are validated at finalize time."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to={"a": "nonexistent_step"})
    async def switch_step(state: Any) -> str:
        return "a"

    with pytest.raises(DefinitionError) as exc_info:
        async for _ in pipe.run(None):
            pass

    assert "routes to unknown step" in str(exc_info.value)
    assert "nonexistent_step" in str(exc_info.value)
    assert "Available steps:" in str(exc_info.value)


async def test_switch_route_validation_with_default() -> None:
    """Test that switch default route is also validated."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to={"a": "step2"}, default="nonexistent_default")
    async def switch_step(state: Any) -> str:
        return "unknown"

    @pipe.step("step2")
    async def step2(state: Any) -> None:
        pass

    with pytest.raises(DefinitionError) as exc_info:
        async for _ in pipe.run(None):
            pass

    assert "nonexistent_default" in str(exc_info.value)


async def test_switch_route_validation_dynamic_not_validated() -> None:
    """Test that dynamic switch routes (callable) are NOT validated at definition time."""
    pipe: Pipe[Any, Any] = Pipe()

    # Dynamic routes - validation happens at runtime, not definition time
    @pipe.switch("switch", to=lambda x: "nonexistent" if x == "bad" else "good_step")
    async def switch_step(state: Any) -> str:
        return "good"

    @pipe.step("good_step")
    async def good_step(state: Any) -> None:
        pass

    # Should not raise at finalize time (dynamic routes)
    events = [e async for e in pipe.run(None, start="switch")]
    assert any(e.type == EventType.FINISH for e in events)


async def test_switch_multiple_invalid_routes() -> None:
    """Test error message when multiple routes are invalid."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", to={"a": "missing1", "b": "missing2"})
    async def switch_step(state: Any) -> str:
        return "a"

    with pytest.raises(DefinitionError) as exc_info:
        async for _ in pipe.run(None):
            pass

    error_msg = str(exc_info.value)
    # Should mention at least one missing step
    assert "missing1" in error_msg or "missing2" in error_msg
