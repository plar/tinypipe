import pytest
from typing import Any, List, Dict
from justpipe import Pipe, EventType
from justpipe.types import Next


@pytest.mark.asyncio
async def test_linear_execution_flow(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    events = []

    @pipe.step("start", to="step2")
    async def start() -> None:
        return None

    @pipe.step("step2")
    async def step2() -> None:
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
async def test_streaming_execution(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    tokens = []

    @pipe.step("streamer")
    async def streamer() -> Any:
        yield "a"
        yield "b"

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            tokens.append(event.data)
    assert tokens == ["a", "b"]


@pytest.mark.asyncio
async def test_dynamic_routing(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    executed: List[bool] = []

    @pipe.step("start")
    async def start() -> Next:
        return Next("target")

    @pipe.step("target")
    async def target() -> None:
        executed.append(True)

    async for _ in pipe.run(state):
        pass
    assert executed


@pytest.mark.parametrize("state_arg", ["s", "state"])
@pytest.mark.parametrize("ctx_arg", ["c", "ctx", "context"])
@pytest.mark.asyncio
async def test_smart_injection_fallbacks(
    state: Any, context: Any, state_arg: str, ctx_arg: str
) -> None:
    pipe: Pipe[Any, Any] = Pipe()

    # Use exec to create a function with exact parameter names
    ldict: Dict[str, Any] = {}
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
async def test_type_aware_injection(state: Any, context: Any) -> None:
    state_type = type(state)
    context_type = type(context)
    pipe = Pipe[state_type, context_type]()  # type: ignore

    @pipe.step
    async def typed_step(ctx: context_type, s: state_type) -> None:  # type: ignore
        assert s is state
        assert ctx is context

    async for _ in pipe.run(state, context):
        pass


@pytest.mark.asyncio
async def test_startup_handlers(state: Any, context: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log = []

    async def _startup(ctx: Any) -> None:
        log.append("startup")

    async def _shutdown(ctx: Any) -> None:
        log.append("shutdown")

    pipe.on_startup(_startup)
    pipe.on_shutdown(_shutdown)

    @pipe.step("start")
    async def start() -> None:
        pass

    async for _ in pipe.run(state, context):
        pass
    assert log == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_step_not_found(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    errors = []

    @pipe.step("start", to="non_existent")
    async def start() -> None:
        pass

    async for event in pipe.run(state):
        if event.type == EventType.ERROR:
            errors.append(event)
    assert any("Step not found" in str(e.data) for e in errors)


def test_async_gen_retry_warning() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    with pytest.warns(UserWarning, match="cannot retry automatically"):

        @pipe.step("stream", retries=3)
        async def stream() -> Any:
            yield 1


def test_advanced_retry_config() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    # Should not raise
    @pipe.step("retry", retries={"stop": 1})
    async def retry_step() -> None:
        pass

    assert "retry" in pipe._steps


def test_pipe_type_extraction(state: Any, context: Any) -> None:
    state_type = type(state)
    context_type = type(context)

    pipe = Pipe[state_type, context_type]()  # type: ignore
    st, ct = pipe._get_types()
    assert st is state_type
    assert ct is context_type

    pipe_default: Pipe[Any, Any] = Pipe()
    st, ct = pipe_default._get_types()
    assert st is Any
