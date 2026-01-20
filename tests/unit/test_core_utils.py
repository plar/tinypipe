import pytest
from typing import Any
from justpipe.core import _analyze_signature
from justpipe.types import _resolve_name


def test_resolve_name_string() -> None:
    assert _resolve_name("foo") == "foo"


def test_resolve_name_callable() -> None:
    def bar() -> None:
        pass

    assert _resolve_name(bar) == "bar"


def test_resolve_name_invalid() -> None:
    with pytest.raises(ValueError):
        _resolve_name(123)  # type: ignore


class MockState:
    pass


class MockContext:
    pass


def test_analyze_by_type() -> None:
    async def step(s: MockState, c: MockContext) -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state", "c": "context"}


def test_analyze_by_name_fallback() -> None:
    async def step(state: Any, context: Any) -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"state": "state", "context": "context"}


# Simplified robust tests
def test_analyze_short_names() -> None:
    async def step(s: Any, c: Any) -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state", "c": "context"}


def test_analyze_with_defaults() -> None:
    async def step(s: Any, d: int = 1) -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state"}
    assert "d" not in mapping


def test_analyze_unknown_arg_allowed() -> None:
    async def step(unknown_arg: Any, s: Any) -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext, expected_unknowns=1)
    assert mapping["unknown_arg"] == "unknown"
    assert mapping["s"] == "state"


def test_analyze_no_state_no_ctx() -> None:
    async def step() -> None:
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {}
