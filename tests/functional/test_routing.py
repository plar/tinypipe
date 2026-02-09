"""Functional tests for routing logic (switches, dynamic returns)."""

import pytest
from typing import Any
from justpipe import Pipe, EventType, Stop, DefinitionError
from justpipe._internal.types import _Next


@pytest.mark.asyncio
async def test_dynamic_routing(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    executed: list[bool] = []

    @pipe.step("start")
    async def start() -> _Next:
        return _Next("target")

    @pipe.step("target")
    async def target() -> None:
        executed.append(True)

    async for _ in pipe.run(state):
        pass
    assert executed


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    async for _ in pipe.run(None):
        pass


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_dynamic_override_static() -> None:
    """Test that returning a dynamic route prevents the static route from running."""
    pipe: Pipe[Any, Any] = Pipe()
    trace: list[str] = []

    @pipe.step("start", to="static_next")
    async def start(state: Any) -> _Next:
        trace.append("start")
        return _Next("dynamic_next")

    @pipe.step("static_next")
    async def static_next(state: Any) -> None:
        trace.append("static_next")

    @pipe.step("dynamic_next")
    async def dynamic_next(state: Any) -> None:
        trace.append("dynamic_next")

    async for _ in pipe.run({}, start="start"):
        pass

    # Expected: start -> dynamic_next
    # 'static_next' should be skipped because 'start' returned a dynamic route.
    assert trace == ["start", "dynamic_next"]


@pytest.mark.asyncio
async def test_dynamic_override_static_raw_string() -> None:
    """Test that returning a raw string as a dynamic route prevents the static route from running."""
    pipe: Pipe[Any, Any] = Pipe()
    trace: list[str] = []

    @pipe.step("start", to="static_next")
    async def start(state: Any) -> str:
        trace.append("start")
        return "dynamic_next"

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    events = [e async for e in pipe.run(None)]
    assert any(e.type == EventType.FINISH for e in events)


@pytest.mark.asyncio
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


# ============================================================================
# Return Value Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_return_dict_triggers_warning() -> None:
    """Test that returning a dict triggers a warning."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> dict[str, str]:
        return {"data": "lost"}

    # Catch warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        # Should have exactly one warning
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "bad_step" in str(w[0].message)
        assert "dict" in str(w[0].message)
        assert "will be ignored" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_list_triggers_warning() -> None:
    """Test that returning a list triggers a warning."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> list[int]:
        return [1, 2, 3]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert "bad_step" in str(w[0].message)
        assert "list" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_object_triggers_warning() -> None:
    """Test that returning an arbitrary object triggers a warning."""
    import warnings

    class CustomObject:
        pass

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> CustomObject:
        return CustomObject()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert "bad_step" in str(w[0].message)
        assert "CustomObject" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_none_no_warning() -> None:
    """Test that returning None does not trigger a warning."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def good_step(state: Any) -> None:
        return None

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        # Should have no warnings
        assert len(w) == 0


@pytest.mark.asyncio
async def test_return_string_no_warning() -> None:
    """Test that returning a step name (string) does not trigger a warning."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def target(state: Any) -> None:
        pass

    @pipe.step()
    async def start(state: Any) -> str:
        return "target"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None, start="start"):
            pass

        # Should have no warnings
        assert len(w) == 0


@pytest.mark.asyncio
async def test_return_stop_no_warning() -> None:
    """Test that returning Stop does not trigger a warning."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def stop_step(state: Any) -> Any:
        return Stop

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        # Should have no warnings
        assert len(w) == 0


@pytest.mark.asyncio
async def test_warning_message_contains_helpful_info() -> None:
    """Test that warning message contains helpful information."""
    import warnings

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("my_step")
    async def bad_step(state: Any) -> dict[str, str]:
        return {"key": "value"}

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        message = str(w[0].message)

        # Should contain step name
        assert "my_step" in message

        # Should contain type
        assert "dict" in message

        # Should explain it's ignored
        assert "ignored" in message

        # Should suggest alternatives
        assert "mutate state" in message or "yield" in message
