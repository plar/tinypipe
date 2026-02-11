"""Unit tests for function signature analysis (injection logic)."""

from typing import Any

import pytest

from justpipe._internal.definition.type_resolver import _TypeResolver
from justpipe._internal.types import InjectionSource
from justpipe.types import DefinitionError


class MockState:
    pass


class MockContext:
    pass


def test_analyze_by_type() -> None:
    resolver = _TypeResolver()

    async def step(s: MockState, c: MockContext) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": InjectionSource.STATE, "c": InjectionSource.CONTEXT}


def test_analyze_by_name_fallback() -> None:
    resolver = _TypeResolver()

    async def step(state: Any, context: Any) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {
        "state": InjectionSource.STATE,
        "context": InjectionSource.CONTEXT,
    }


def test_analyze_short_names() -> None:
    resolver = _TypeResolver()

    async def step(s: Any, c: Any) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": InjectionSource.STATE, "c": InjectionSource.CONTEXT}


def test_analyze_with_defaults() -> None:
    resolver = _TypeResolver()

    async def step(s: Any, d: int = 1) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {"s": InjectionSource.STATE}
    assert "d" not in mapping


def test_analyze_unknown_arg_allowed() -> None:
    resolver = _TypeResolver()

    async def step(unknown_arg: Any, s: Any) -> None:
        pass

    mapping = resolver.analyze_signature(
        step, MockState, MockContext, expected_unknowns=1
    )
    assert mapping["unknown_arg"] == InjectionSource.UNKNOWN
    assert mapping["s"] == InjectionSource.STATE


def test_analyze_no_state_no_ctx() -> None:
    resolver = _TypeResolver()

    async def step() -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {}


def test_analyze_prefers_type_over_name_alias() -> None:
    resolver = _TypeResolver()

    async def step(state: MockContext, context: MockState) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {
        "state": InjectionSource.CONTEXT,
        "context": InjectionSource.STATE,
    }


def test_analyze_type_wins_when_name_suggests_state() -> None:
    resolver = _TypeResolver()

    async def conflict(state: MockContext) -> None:
        pass

    mapping = resolver.analyze_signature(conflict, MockState, MockContext)
    assert mapping == {"state": InjectionSource.CONTEXT}


def test_analyze_special_name_aliases() -> None:
    resolver = _TypeResolver()

    async def step(
        cancellation_token: Any,
        exception: Any,
        stage: Any,
        ctx: Any,
    ) -> None:
        pass

    mapping = resolver.analyze_signature(step, MockState, MockContext)
    assert mapping == {
        "cancellation_token": InjectionSource.CANCEL,
        "exception": InjectionSource.ERROR,
        "stage": InjectionSource.STEP_NAME,
        "ctx": InjectionSource.CONTEXT,
    }


def test_analyze_unknown_rejected_by_default() -> None:
    resolver = _TypeResolver()

    async def step(payload: Any) -> None:
        pass

    with pytest.raises(DefinitionError) as exc_info:
        resolver.analyze_signature(step, MockState, MockContext)

    message = str(exc_info.value)
    assert "Expected 0 unknown parameter(s)" in message
    assert "Lifecycle hooks (on_startup, on_shutdown, on_error)" in message
    assert "Parameters must be typed as MockState or MockContext" in message


def test_analyze_unknown_error_message_for_regular_step() -> None:
    resolver = _TypeResolver()

    async def step(item: Any, extra: Any) -> None:
        pass

    with pytest.raises(DefinitionError) as exc_info:
        resolver.analyze_signature(step, MockState, MockContext, expected_unknowns=1)

    message = str(exc_info.value)
    assert "Expected 1 unknown parameter(s)" in message
    assert "Regular steps allow one injected parameter" in message
