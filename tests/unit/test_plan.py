from justpipe._internal.graph.execution_plan import compile_execution_plan
from justpipe._internal.definition.steps import _StandardStep


def test_compile_execution_plan_roots_and_parents_map() -> None:
    steps: dict[str, _StandardStep] = {
        "a": _StandardStep("a", lambda: None),
        "b": _StandardStep("b", lambda: None),
    }
    topology = {"a": ["b"]}
    plan, graph = compile_execution_plan(steps, topology, {})
    assert plan.roots == {"a"}
    assert plan.parents_map["b"] == {"a"}
    assert graph.parents_map_snapshot() == plan.parents_map
