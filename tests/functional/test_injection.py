"""Functional tests for dependency injection."""

import pytest
from typing import Any
from justpipe import Pipe


@pytest.mark.parametrize("state_arg", ["s", "state"])
@pytest.mark.parametrize("ctx_arg", ["c", "ctx", "context"])
async def test_smart_injection_fallbacks(
    state: Any, context: Any, state_arg: str, ctx_arg: str
) -> None:
    pipe: Pipe[Any, Any] = Pipe()

    # Use exec to create a function with exact parameter names
    ldict: dict[str, Any] = {}
    code = f"""
async def dynamic_step({state_arg}, {ctx_arg}):
    # Just verify injection works - no return needed
    assert {state_arg} is not None
    assert {ctx_arg} is not None
"""
    exec(code, globals(), ldict)
    func = ldict["dynamic_step"]

    pipe.step("test")(func)

    # Run it and verify injection
    # We verify it doesn't crash.
    async for _ in pipe.run(state, context, start="test"):
        pass


async def test_type_aware_injection(state: Any, context: Any) -> None:
    state_type = type(state)
    context_type = type(context)
    pipe = Pipe(state_type, context_type)

    @pipe.step
    async def typed_step(ctx: Any, s: Any) -> None:
        assert s is state
        assert ctx is context

    async for _ in pipe.run(state, context):
        pass


async def test_type_injection_with_subclass() -> None:
    class BaseState:
        pass

    class ChildState(BaseState):
        pass

    class BaseContext:
        pass

    class ChildContext(BaseContext):
        pass

    state = ChildState()
    context = ChildContext()
    pipe = Pipe(ChildState, ChildContext)

    @pipe.step
    async def typed_step(state_obj: BaseState, context_obj: BaseContext) -> None:
        assert state_obj is state
        assert context_obj is context

    async for _ in pipe.run(state, context):
        pass
