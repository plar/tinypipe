import asyncio
import pytest
from typing import Any, Dict, List, AsyncGenerator
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_backpressure_slow_consumer() -> None:
    # Pipe with a very small queue (max 1 item)
    pipe: Pipe[Dict[str, Any], None] = Pipe(queue_size=1)

    produced_tokens: List[int] = []

    @pipe.step()
    async def producer(state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        for i in range(5):
            await asyncio.sleep(0.01)  # Simulate some work
            yield f"token_{i}"
            produced_tokens.append(i)

    # Run the pipe
    state: Dict[str, Any] = {}
    it = pipe.run(state).__aiter__()

    # 1. START event
    ev = await it.__anext__()
    assert ev.type == EventType.START

    # 2. STEP_START event for 'producer'
    ev = await it.__anext__()
    assert ev.type == EventType.STEP_START
    assert ev.stage == "producer"

    # At this point the queue is empty.
    # The producer task is running.
    # It will yield 'token_0'.
    # The runner will put(token_0) -> queue has 1 item.
    # Then producer will yield 'token_1'.
    # The runner will try to put(token_1) -> this will BLOCK because queue is full.

    await asyncio.sleep(0.05)

    # Producer should be blocked after yielding the second token (trying to put it).
    # So produced_tokens should contain [0], and it's currently stuck trying to put 1.
    # Wait, 'produced_tokens.append(i)' happens AFTER 'yield'.
    # If 'yield' blocks, 'produced_tokens' won't be updated for the blocked token.

    assert len(produced_tokens) == 1
    assert produced_tokens == [0]

    # 3. Consume 'token_0'
    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.data == "token_0"

    # Now queue has space. token_1 should be put into the queue.
    # Producer should continue and try to yield token_2.

    await asyncio.sleep(0.05)
    assert len(produced_tokens) == 2
    assert produced_tokens == [0, 1]

    # 4. Consume 'token_1'
    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.data == "token_1"

    await asyncio.sleep(0.05)
    assert len(produced_tokens) == 3

    # Finish the rest
    remaining: List[Any] = []
    async for ev in pipe.run(state, queue_size=1):
        if ev.type == EventType.TOKEN:
            remaining.append(ev.data)

    assert len(remaining) == 5
    assert remaining == ["token_0", "token_1", "token_2", "token_3", "token_4"]


@pytest.mark.asyncio
async def test_backpressure_with_next_steps() -> None:
    # Test that backpressure also works when multiple steps are producing events
    pipe: Pipe[Dict[str, Any], None] = Pipe(queue_size=1)

    @pipe.step(to="step_b")
    async def step_a(state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        yield "token_a"

    @pipe.step()
    async def step_b(state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        yield "token_b"

    it = pipe.run({}).__aiter__()

    # Consume START, STEP_START(a)
    await it.__anext__()  # START
    await it.__anext__()  # STEP_START a

    # Now 'token_a' should be in queue.
    # step_a should be blocked trying to put STEP_END(a) or the runner result.

    ev = await it.__anext__()
    assert ev.type == EventType.TOKEN
    assert ev.data == "token_a"

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
    assert ev.data == "token_b"