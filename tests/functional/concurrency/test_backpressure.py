import asyncio
import pytest
from typing import Any, cast
from collections.abc import AsyncGenerator
from justpipe import Pipe, EventType

pytestmark = pytest.mark.slow


async def _wait_until(
    predicate: Any, *, timeout: float = 1.0, interval: float = 0.005
) -> None:
    """Poll until *predicate()* is truthy, or raise after *timeout*."""
    deadline = asyncio.get_event_loop().time() + timeout
    while not predicate():
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("Timed out waiting for condition")
        await asyncio.sleep(interval)


async def test_backpressure_slow_consumer() -> None:
    # Pipe with a very small queue (max 1 item)
    pipe: Pipe[dict[str, Any], None] = Pipe(queue_size=1)

    produced_tokens: list[int] = []

    @pipe.step()
    async def producer(state: dict[str, Any]) -> AsyncGenerator[str, None]:
        for i in range(5):
            await asyncio.sleep(0.01)  # Simulate some work
            yield f"token_{i}"
            produced_tokens.append(i)

    # Run the pipe
    state: dict[str, Any] = {}
    it = pipe.run(state).__aiter__()

    # 1. START event
    ev = await it.__anext__()
    assert ev.type == EventType.START

    # 2. STEP_START event for 'producer'
    ev = await it.__anext__()
    assert ev.type == EventType.STEP_START
    assert ev.stage == "producer"

    # Wait for producer to yield token_0 and get blocked on token_1.
    # produced_tokens.append(i) runs AFTER yield returns, so once we see
    # produced_tokens == [0] the producer has yielded token_0 and is blocked
    # trying to put token_1 into the full queue.
    await _wait_until(lambda: len(produced_tokens) >= 1)
    assert produced_tokens == [0]

    # 3. Consume 'token_0'
    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.payload == "token_0"

    # Now queue has space. token_1 enters; producer advances and blocks on token_2.
    await _wait_until(lambda: len(produced_tokens) >= 2)
    assert produced_tokens == [0, 1]

    # 4. Consume 'token_1'
    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.payload == "token_1"

    await _wait_until(lambda: len(produced_tokens) >= 3)

    # Finish the rest
    remaining: list[Any] = []
    async for ev in pipe.run(state, queue_size=1):
        if ev.type == EventType.TOKEN:
            remaining.append(ev.payload)

    assert len(remaining) == 5
    assert remaining == ["token_0", "token_1", "token_2", "token_3", "token_4"]


async def test_backpressure_with_next_steps() -> None:
    # Test that backpressure also works when multiple steps are producing events
    pipe: Pipe[dict[str, Any], None] = Pipe(queue_size=1)

    @pipe.step(to="step_b")
    async def step_a(state: dict[str, Any]) -> AsyncGenerator[str, None]:
        yield "token_a"

    @pipe.step()
    async def step_b(state: dict[str, Any]) -> AsyncGenerator[str, None]:
        yield "token_b"

    it = cast(AsyncGenerator[Any, None], pipe.run({}))

    # Consume START, STEP_START(a)
    await it.__anext__()  # START
    await it.__anext__()  # STEP_START a

    # Now 'token_a' should be in queue.
    # step_a should be blocked trying to put STEP_END(a) or the runner result.

    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.payload == "token_a"

    # Now queue has space. STEP_END(a) enters.
    # This triggers step_b.
    # STEP_START(b) tries to enter queue.

    ev = await it.__anext__()
    assert ev.type == EventType.STEP_END
    assert ev.stage == "step_a"

    ev = await it.__anext__()
    assert ev.type == EventType.STEP_START
    assert ev.stage == "step_b"

    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.payload == "token_b"


async def test_backpressure_iterator_aclose_has_no_generator_exit_leak() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(queue_size=1)

    @pipe.step()
    async def producer(state: dict[str, Any]) -> AsyncGenerator[str, None]:
        for i in range(100):
            await asyncio.sleep(0.001)
            yield f"token_{i}"

    it = cast(AsyncGenerator[Any, None], pipe.run({}))
    await it.__anext__()  # START
    await it.__anext__()  # STEP_START

    loop = asyncio.get_running_loop()
    captured_contexts: list[dict[str, Any]] = []
    previous_handler = loop.get_exception_handler()

    def _capture_exception(
        _loop: asyncio.AbstractEventLoop, context: dict[str, Any]
    ) -> None:
        captured_contexts.append(context)

    loop.set_exception_handler(_capture_exception)
    try:
        await it.aclose()
        await asyncio.sleep(0.05)
    finally:
        loop.set_exception_handler(previous_handler)

    leaked = [
        ctx
        for ctx in captured_contexts
        if "ignored GeneratorExit"
        in str(ctx.get("exception") or ctx.get("message") or "")
    ]
    assert leaked == []
