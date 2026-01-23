import pytest
from typing import Any, List, Set, AsyncGenerator
from justpipe import Pipe, Event, EventType


@pytest.mark.asyncio
async def test_add_event_hook_single() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    events: List[Event] = []

    def capture_hook(event: Event) -> Event:
        events.append(event)
        return event

    pipe.add_event_hook(capture_hook)

    @pipe.step("test")
    async def test_step() -> None:
        pass

    async for _ in pipe.run({}):
        pass

    assert len(events) > 0
    event_types = [e.type for e in events]
    assert EventType.START in event_types
    assert EventType.FINISH in event_types


@pytest.mark.asyncio
async def test_event_hook_transforms_event() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    def add_metadata(event: Event) -> Event:
        event.data = {"original": event.data, "enriched": True}
        return event

    pipe.add_event_hook(add_metadata)

    @pipe.step("test")
    async def test_step() -> None:
        pass

    collected: List[Event] = []

    async for event in pipe.run({"initial": "state"}):
        collected.append(event)

    start_event = next(e for e in collected if e.type == EventType.START)
    assert isinstance(start_event.data, dict)
    assert start_event.data["enriched"] is True
    assert start_event.data["original"] == {"initial": "state"}


@pytest.mark.asyncio
async def test_multiple_event_hooks_chained() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    call_order: List[int] = []

    def hook1(event: Event) -> Event:
        call_order.append(1)
        return event

    def hook2(event: Event) -> Event:
        call_order.append(2)
        return event

    def hook3(event: Event) -> Event:
        call_order.append(3)
        return event

    pipe.add_event_hook(hook1)
    pipe.add_event_hook(hook2)
    pipe.add_event_hook(hook3)

    @pipe.step("test")
    async def test_step() -> None:
        pass

    async for _ in pipe.run({}):
        pass

    # Hooks are called in order for each event
    # We should see pattern 1,2,3 repeated for each event
    assert call_order[:3] == [1, 2, 3]


@pytest.mark.asyncio
async def test_event_hook_receives_all_event_types() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    seen_types: Set[EventType] = set()

    def collect_types(event: Event) -> Event:
        seen_types.add(event.type)
        return event

    pipe.add_event_hook(collect_types)

    @pipe.step("first", to="second")
    async def first() -> None:
        pass

    @pipe.step("second")
    async def second() -> AsyncGenerator[str, None]:
        yield "token1"
        yield "token2"

    async for _ in pipe.run({}):
        pass

    assert EventType.START in seen_types
    assert EventType.STEP_START in seen_types
    assert EventType.STEP_END in seen_types
    assert EventType.TOKEN in seen_types
    assert EventType.FINISH in seen_types


@pytest.mark.asyncio
async def test_event_hook_with_error() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    error_events: List[Event] = []

    def capture_errors(event: Event) -> Event:
        if event.type == EventType.ERROR:
            error_events.append(event)
        return event

    pipe.add_event_hook(capture_errors)

    @pipe.step("fail")
    async def fail() -> None:
        raise ValueError("test error")

    async for _ in pipe.run({}):
        pass

    assert len(error_events) == 1
    assert "test error" in error_events[0].data