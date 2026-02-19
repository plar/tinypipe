from typing import Any
from unittest.mock import AsyncMock


from justpipe._internal.runtime.orchestration.event_publisher import (
    make_event_publisher,
)
from justpipe.types import Event


def _fake_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = {
        "type": "step_start",
        "stage": "step_a",
        "timestamp": 1.0,
        "run_id": "run-1",
        "origin_run_id": "run-1",
        "parent_run_id": None,
        "seq": 1,
        "node_kind": "step",
        "invocation_id": "inv-1",
        "parent_invocation_id": None,
        "owner_invocation_id": None,
        "attempt": 1,
        "scope": (),
        "meta": {},
        "payload": None,
    }
    defaults.update(overrides)
    return Event(**defaults)


async def test_all_callables_fire_in_correct_order() -> None:
    """prepare_event -> apply_hooks -> on_event -> notify_event."""
    order: list[str] = []
    event = _fake_event()

    def prepare(e: Event) -> Event:
        order.append("prepare")
        return e

    def hooks(e: Event) -> Event:
        order.append("hooks")
        return e

    async def on(e: Event) -> None:
        order.append("on_event")

    async def notify(e: Event, state: Any) -> None:
        order.append("notify")

    publish = make_event_publisher(
        notify_event=notify,
        apply_hooks=hooks,
        state_getter=lambda: None,
        prepare_event=prepare,
        on_event=on,
    )
    await publish(event)
    assert order == ["prepare", "hooks", "on_event", "notify"]


async def test_optional_callbacks_skipped() -> None:
    """When prepare_event=None and on_event=None, only hooks + notify fire."""
    order: list[str] = []
    event = _fake_event()

    def hooks(e: Event) -> Event:
        order.append("hooks")
        return e

    async def notify(e: Event, state: Any) -> None:
        order.append("notify")

    publish = make_event_publisher(
        notify_event=notify,
        apply_hooks=hooks,
        state_getter=lambda: None,
        prepare_event=None,
        on_event=None,
    )
    await publish(event)
    assert order == ["hooks", "notify"]


async def test_hook_mutation_visible_to_observers() -> None:
    """apply_hooks modifies the event; notify_event receives the modified event."""
    original = _fake_event(seq=1)
    mutated = _fake_event(seq=99)
    received: list[Event] = []

    def hooks(e: Event) -> Event:
        return mutated

    async def notify(e: Event, state: Any) -> None:
        received.append(e)

    publish = make_event_publisher(
        notify_event=notify,
        apply_hooks=hooks,
        state_getter=lambda: None,
    )
    await publish(original)
    assert received == [mutated]


async def test_state_passed_to_notify() -> None:
    """state_getter() return value is passed as second arg to notify_event."""
    state_obj = {"key": "value"}
    captured_state: list[Any] = []
    event = _fake_event()

    async def notify(e: Event, state: Any) -> None:
        captured_state.append(state)

    publish = make_event_publisher(
        notify_event=notify,
        apply_hooks=lambda e: e,
        state_getter=lambda: state_obj,
    )
    await publish(event)
    assert captured_state == [state_obj]


async def test_returns_possibly_mutated_event() -> None:
    """publish() returns the event after hook mutation."""
    original = _fake_event(seq=1)
    mutated = _fake_event(seq=42)

    publish = make_event_publisher(
        notify_event=AsyncMock(),
        apply_hooks=lambda e: mutated,
        state_getter=lambda: None,
    )
    result = await publish(original)
    assert result is mutated


async def test_hooks_run_before_on_event_and_notify() -> None:
    """Verify apply_hooks runs before on_event and notify_event by tracking call order."""
    order: list[str] = []
    event = _fake_event()

    def hooks(e: Event) -> Event:
        order.append("hooks")
        return e

    async def on(e: Event) -> None:
        order.append("on_event")

    async def notify(e: Event, state: Any) -> None:
        order.append("notify")

    publish = make_event_publisher(
        notify_event=notify,
        apply_hooks=hooks,
        state_getter=lambda: None,
        on_event=on,
    )
    await publish(event)
    assert order.index("hooks") < order.index("on_event")
    assert order.index("hooks") < order.index("notify")
