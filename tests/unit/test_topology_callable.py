import pytest
from typing import Any
from justpipe import Pipe, Stop
from justpipe.types import _resolve_name
from justpipe.steps import _StandardStep


def global_step_a(state: Any) -> None:
    pass


def global_step_b(state: Any) -> None:
    pass


def test_resolve_name_callable() -> None:
    assert _resolve_name(global_step_a) == "global_step_a"


def test_pipe_step_callable_routing() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step()
    def step_b(state: Any) -> None:
        pass

    @pipe.step(to=step_b)
    def step_a(state: Any) -> None:
        pass

    assert "step_a" in pipe._topology
    assert pipe._topology["step_a"] == ["step_b"]


def test_pipe_step_list_callable_routing() -> None:
    pipe: Pipe[None, None] = Pipe()

    def step_c(state: Any) -> None:
        pass

    @pipe.step()
    def step_b(state: Any) -> None:
        pass

    @pipe.step(to=[step_b, step_c])
    def step_a(state: Any) -> None:
        pass

    # Manually register step_c since it wasn't decorated
    pipe._steps["step_c"] = _StandardStep(name="step_c", func=step_c)

    assert "step_a" in pipe._topology
    assert "step_b" in pipe._topology["step_a"]
    assert "step_c" in pipe._topology["step_a"]


def test_pipe_map_callable_routing() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step()
    def processor(item: Any) -> None:
        pass

    @pipe.step()
    def step_b(state: Any) -> None:
        pass

    @pipe.map(using=processor, to=step_b)
    def generator(state: Any) -> list[int]:
        return [1, 2, 3]

    # Check internal metadata
    assert pipe._step_metadata["generator"]["map_target"] == "processor"
    assert pipe._topology["generator"] == ["step_b"]


def test_pipe_switch_callable_routing() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step()
    def path_a(state: Any) -> None:
        pass

    @pipe.step()
    def path_b(state: Any) -> None:
        pass

    @pipe.switch(routes={"a": path_a, "b": path_b}, default=path_b)
    def decider(state: Any) -> str:
        return "a"

    meta = pipe._step_metadata["decider"]
    assert meta["switch_routes"]["a"] == "path_a"
    assert meta["switch_routes"]["b"] == "path_b"
    assert meta["switch_default"] == "path_b"


def test_pipe_switch_stop_routing() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.switch(routes={"a": Stop})
    def decider(state: Any) -> str:
        return "a"

    # Should not raise warning for Stop
    assert pipe._step_metadata["decider"]["switch_routes"]["a"] == "Stop"


def test_pipe_validation_ok() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step(to="step_b")
    def step_a(state: Any) -> None:
        pass

    @pipe.step()
    def step_b(state: Any) -> None:
        pass

    pipe.validate()


def test_pipe_validation_broken_ref() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step(to="unknown")
    def step_a(state: Any) -> None:
        pass

    with pytest.raises(ValueError, match="targets unknown step 'unknown'"):
        pipe.validate()


def test_pipe_validation_cycle() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step(to="step_b")
    def step_a(state: Any) -> None:
        pass

    @pipe.step(to="step_a")
    def step_b(state: Any) -> None:
        pass

    with pytest.raises(ValueError, match="Circular dependency"):
        pipe.validate()


def test_pipe_validation_unreachable_cycle() -> None:
    pipe: Pipe[None, None] = Pipe()
    # A cycle with no entry point
    pipe._topology["a"] = ["b"]
    pipe._topology["b"] = ["a"]
    pipe._steps["a"] = _StandardStep(name="a", func=lambda s: None)
    pipe._steps["b"] = _StandardStep(name="b", func=lambda s: None)

    with pytest.raises(ValueError, match="no entry points found"):
        pipe.validate()


def test_map_missing_using() -> None:
    pipe: Pipe[None, None] = Pipe()
    with pytest.raises(ValueError, match="requires 'using'"):

        @pipe.map("mapper", using=None)
        def mapper() -> None:
            pass


def test_map_on_error_and_to() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.step("target")
    def target(x: Any) -> None:
        pass

    @pipe.step("next")
    def next_step() -> None:
        pass

    @pipe.map("mapper", using="target", to="next", on_error=lambda e: None)
    def mapper() -> list[int]:
        return [1]

    # Just ensure no error and metadata is correct
    assert pipe._step_metadata["mapper"]["map_target"] == "target"
    assert pipe._step_metadata["mapper"]["on_error"] is not None


def test_switch_missing_routes() -> None:
    pipe: Pipe[None, None] = Pipe()
    with pytest.raises(ValueError, match="requires 'routes'"):

        @pipe.switch("switcher", routes=None)
        def switcher() -> None:
            pass


def test_validate_unreachable_cycle_detached() -> None:
    pipe: Pipe[None, None] = Pipe()

    # Create a detached cycle: A -> B -> A
    @pipe.step("A", to="B")
    def a() -> None:
        pass

    @pipe.step("B", to="A")
    def b() -> None:
        pass

    # Entry point C
    @pipe.step("C")
    def c() -> None:
        pass

    # A and B are unreachable from roots (C)
    with pytest.raises(ValueError, match="Unreachable steps"):
        pipe.validate()


def test_validate_unknown_switch_target() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.switch("s", routes={"x": "unknown"})
    def s() -> str:
        return "x"

    with pytest.raises(ValueError, match="routes to unknown step"):
        pipe.validate()


def test_validate_unknown_switch_default() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.switch("s", routes={}, default="unknown")
    def s() -> str:
        return "x"

    with pytest.raises(ValueError, match="unknown default route"):
        pipe.validate()


def test_validate_unknown_map_target() -> None:
    pipe: Pipe[None, None] = Pipe()

    @pipe.map("m", using="unknown")
    def m() -> list[Any]:
        return []

    with pytest.raises(ValueError, match="targets unknown step"):
        pipe.validate()