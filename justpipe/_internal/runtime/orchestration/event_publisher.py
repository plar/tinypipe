from __future__ import annotations

from typing import Any
from collections.abc import Awaitable, Callable

from justpipe.types import Event


def make_event_publisher(
    *,
    notify_event: Callable[[Event, Any], Awaitable[None]],
    apply_hooks: Callable[[Event], Event],
    state_getter: Callable[[], Any],
    prepare_event: Callable[[Event], Event] | None = None,
    on_event: Callable[[Event], Awaitable[None]] | None = None,
) -> Callable[[Event], Awaitable[Event]]:
    """Create a bound event publisher closure used by the runner."""

    async def _publish(event: Event) -> Event:
        if prepare_event is not None:
            event = prepare_event(event)
        if on_event is not None:
            await on_event(event)
        state = state_getter()
        await notify_event(event, state)
        return apply_hooks(event)

    return _publish
