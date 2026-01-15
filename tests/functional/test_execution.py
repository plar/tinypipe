import pytest
from typing import Any
from tinypipe import Pipe, EventType, Next


@pytest.mark.asyncio
async def test_linear_execution_flow(state):
    pipe = Pipe()
    events = []

    @pipe.step("start", to="step2")
    async def start():
        return None

    @pipe.step("step2")
    async def step2():
        pass

    async for event in pipe.run(state):
        events.append(event)

    types = [e.type for e in events]
    assert EventType.START in types
    assert EventType.FINISH in types
    assert [e.stage for e in events if e.type == EventType.STEP_START] == [
        "start",
        "step2",
    ]


@pytest.mark.asyncio
async def test_streaming_execution(state):
    pipe = Pipe()
    tokens = []

    @pipe.step("streamer")
    async def streamer():
        yield "a"
        yield "b"

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            tokens.append(event.data)
    assert tokens == ["a", "b"]


@pytest.mark.asyncio
async def test_dynamic_routing(state):
    pipe = Pipe()
    executed = []

    @pipe.step("start")
    async def start():
        return Next("target")

    @pipe.step("target")
    async def target():
        executed.append(True)

    async for _ in pipe.run(state):
        pass
    assert executed


@pytest.mark.parametrize("state_arg", ["s", "state"])
@pytest.mark.parametrize("ctx_arg", ["c", "ctx", "context"])
@pytest.mark.asyncio
async def test_smart_injection_fallbacks(state, context, state_arg, ctx_arg):
    pipe = Pipe()

    # Use exec to create a function with exact parameter names
    ldict = {}
    code = f"""
async def dynamic_step({state_arg}, {ctx_arg}): 
    return {state_arg}, {ctx_arg}
"""
    exec(code, globals(), ldict)
    func = ldict["dynamic_step"]

    pipe.step("test")(func)

    # Run it and verify injection
    # We verify it doesn't crash.
    async for _ in pipe.run(state, context, start="test"):
        pass


@pytest.mark.asyncio
async def test_type_aware_injection(state, context):
    state_type = type(state)
    context_type = type(context)
    pipe = Pipe[state_type, context_type]()  # type: ignore

    @pipe.step
    async def typed_step(ctx: context_type, s: state_type):  # type: ignore
        assert s is state
        assert ctx is context

    async for _ in pipe.run(state, context):
        pass


@pytest.mark.asyncio
async def test_startup_handlers(state, context):
    pipe = Pipe()
    log = []

    async def _startup(ctx):
        log.append("startup")

    async def _shutdown(ctx):
        log.append("shutdown")

    pipe.on_startup(_startup)
    pipe.on_shutdown(_shutdown)

    @pipe.step("start")
    async def start():
        pass

    async for _ in pipe.run(state, context):
        pass
    assert log == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_step_not_found(state):
    pipe = Pipe()
    errors = []

    @pipe.step("start", to="non_existent")
    async def start():
        pass

    async for event in pipe.run(state):
        if event.type == EventType.ERROR:
            errors.append(event)
    assert any("Step not found" in str(e.data) for e in errors)


def test_async_gen_retry_warning():
    pipe = Pipe()
    with pytest.warns(UserWarning, match="cannot retry automatically"):

        @pipe.step("stream", retries=3)
        async def stream():
            yield 1


def test_advanced_retry_config():
    pipe = Pipe()

    # Should not raise
    @pipe.step("retry", retries={"stop": 1})
    async def retry_step():
        pass

    assert "retry" in pipe._steps


def test_pipe_type_extraction(state, context):
    state_type = type(state)
    context_type = type(context)

    pipe = Pipe[state_type, context_type]()  # type: ignore
    st, ct = pipe._get_types()
    assert st is state_type
    assert ct is context_type

    pipe_default = Pipe()
    st, ct = pipe_default._get_types()
    assert st is Any
