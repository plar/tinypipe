import pytest
import asyncio
from typing import Any, List, Dict, AsyncGenerator
from justpipe import Pipe, EventType, Stop
from justpipe.types import _Next


@pytest.mark.asyncio
async def test_linear_execution_flow(state: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    events: List[Any] = []

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
    tokens: List[Any] = []

    @pipe.step("streamer")
    async def streamer() -> AsyncGenerator[str, None]:
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
    executed: List[str] = []

    @pipe.switch("start", routes={"a": "step_a", "b": "step_b"})
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
    async def typed_step(ctx: Any, s: Any) -> None:
        assert s is state
        assert ctx is context

    async for _ in pipe.run(state, context):
        pass


@pytest.mark.asyncio
async def test_startup_handlers(state: Any, context: Any) -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log: List[str] = []

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
    errors: List[Any] = []

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
        async def stream() -> AsyncGenerator[int, None]:
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

    @pipe.switch("switch", routes=route_logic)
    async def switch() -> bool:
        return True

    async def run() -> None:
        async for _ in pipe.run(None):
            pass

    # We just ensure it runs without error and routes correctly (implied by no error)
    await run()


@pytest.mark.asyncio
async def test_switch_no_match_no_default() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", routes={"x": "y"})
    async def switch() -> str:
        return "z"  # No match

    async def run() -> List[Any]:
        events = []
        async for ev in pipe.run(None):
            if ev.type == EventType.ERROR:
                events.append(ev)
        return events

    events = await run()
    assert len(events) > 0
    assert "matches no route" in str(events[0].data)


@pytest.mark.asyncio
async def test_switch_returns_stop() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", routes={"stop": Stop})
    async def switch() -> str:
        return "stop"

    async def run() -> None:
        events = []
        async for ev in pipe.run(None):
            events.append(ev)

    await run()


@pytest.mark.asyncio
async def test_step_timeout_execution() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("slow", timeout=0.1)
    async def slow() -> None:
        await asyncio.sleep(0.5)

    events: List[Any] = []
    async for ev in pipe.run(None):
        if ev.type == EventType.ERROR:
            events.append(ev)

    assert len(events) == 1
    assert "timed out" in str(events[0].data)


@pytest.mark.asyncio
async def test_switch_callable_returns_stop() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.switch("switch", routes=lambda x: Stop)
    async def switch() -> str:
        return "ignored"

    # Should run without error and stop
    async for _ in pipe.run(None):
        pass
