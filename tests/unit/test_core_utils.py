import pytest
from justpipe.core import _resolve_name, _analyze_signature


def test_resolve_name_string():
    assert _resolve_name("foo") == "foo"


def test_resolve_name_callable():
    def bar():
        pass

    assert _resolve_name(bar) == "bar"


def test_resolve_name_invalid():
    with pytest.raises(ValueError):
        _resolve_name(123)


class MockState:
    pass


class MockContext:
    pass


def test_analyze_by_type():
    async def step(s: MockState, c: MockContext):
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state", "c": "context"}


def test_analyze_by_name_fallback():
    async def step(state, context):
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"state": "state", "context": "context"}


# Simplified robust tests
def test_analyze_short_names():
    async def step(s, c):
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state", "c": "context"}


def test_analyze_with_defaults():
    async def step(s, d=1):
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": "state"}
    assert "d" not in mapping


def test_analyze_invalid_arg():
    async def step(unknown_arg, s):
        pass

    with pytest.raises(ValueError, match="Unknown argument 'unknown_arg'"):
        _analyze_signature(step, MockState, MockContext)


def test_analyze_no_state_no_ctx():
    async def step():
        pass

    mapping = _analyze_signature(step, MockState, MockContext)
    assert mapping == {}
