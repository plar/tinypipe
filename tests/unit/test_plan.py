from justpipe._internal.graph.execution_plan import compile_execution_plan
from justpipe._internal.definition.steps import _StandardStep


def _step(name: str) -> _StandardStep:
    return _StandardStep(name, lambda: None)


def test_compile_execution_plan_roots_and_parents_map() -> None:
    steps = {"a": _step("a"), "b": _step("b")}
    topology = {"a": ["b"]}
    plan, graph = compile_execution_plan(steps, topology, {})
    assert plan.roots == {"a"}
    assert plan.parents_map["b"] == {"a"}
    assert graph.parents_map_snapshot() == plan.parents_map


def test_multiple_roots() -> None:
    """Two disconnected steps are both roots."""
    steps = {"x": _step("x"), "y": _step("y")}
    plan, _ = compile_execution_plan(steps, {}, {})
    assert plan.roots == {"x", "y"}


def test_diamond_topology() -> None:
    """a->[b,c]->d: d has two parents."""
    steps = {n: _step(n) for n in "abcd"}
    topology = {"a": ["b", "c"], "b": ["d"], "c": ["d"]}
    plan, _ = compile_execution_plan(steps, topology, {})
    assert plan.roots == {"a"}
    assert plan.parents_map["d"] == {"b", "c"}


def test_single_step() -> None:
    """A single step with no topology is a root with empty parents_map."""
    steps = {"solo": _step("solo")}
    plan, _ = compile_execution_plan(steps, {}, {})
    assert plan.roots == {"solo"}
    assert plan.parents_map == {}


def test_empty_steps() -> None:
    """Empty steps dict produces empty plan without crashing."""
    plan, _ = compile_execution_plan({}, {}, {})
    assert plan.roots == set()
    assert plan.parents_map == {}
