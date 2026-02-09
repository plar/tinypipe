import logging
import time
from typing import Any, TypeVar
from collections.abc import Callable

from justpipe.observability import ObserverMeta
from justpipe.types import Event

ContextT = TypeVar("ContextT")


class _EventManager:
    """Internal manager for pipeline events, hooks, and observers."""

    def __init__(
        self,
        event_hooks: list[Callable[[Event], Event]] | None = None,
        observers: list[Any] | None = None,
        pipe_name: str = "Pipe",
    ):
        self._event_hooks = event_hooks or []
        self._observers = observers or []
        self._pipe_name = pipe_name
        self._context: Any = None
        self._meta = ObserverMeta(pipe_name=pipe_name)

    def apply_hooks(self, event: Event) -> Event:
        """Apply all registered event hooks to transform the event."""
        for hook in self._event_hooks:
            result = hook(event)
            hook_name = getattr(hook, "__name__", repr(hook))
            if result is None:
                raise ValueError(
                    f"Event hook {hook_name} returned None, expected Event"
                )
            if not isinstance(result, Event):
                raise TypeError(
                    f"Event hook {hook_name} returned {type(result).__name__}, expected Event"
                )
            event = result
        return event

    async def notify_start(self, state: Any, context: Any) -> None:
        """Notify all observers that pipeline is starting."""
        self._context = context
        self._meta = ObserverMeta(
            pipe_name=self._pipe_name,
            started_at=time.time(),
        )

        for observer in self._observers:
            try:
                await observer.on_pipeline_start(state, context, self._meta)
            except Exception as e:
                self._log_observer_error(observer, "on_pipeline_start", e)

    async def notify_event(self, event: Event, state: Any) -> None:
        """Notify all observers of an event."""
        for observer in self._observers:
            try:
                await observer.on_event(state, self._context, self._meta, event)
            except Exception as e:
                self._log_observer_error(observer, "on_event", e, event)

    async def notify_end(self, state: Any, duration: float) -> None:
        """Notify all observers that pipeline completed successfully."""
        for observer in self._observers:
            try:
                await observer.on_pipeline_end(
                    state, self._context, self._meta, duration
                )
            except Exception as e:
                self._log_observer_error(observer, "on_pipeline_end", e)

    async def notify_error(self, error: Exception, state: Any) -> None:
        """Notify all observers that pipeline failed."""
        for observer in self._observers:
            try:
                await observer.on_pipeline_error(
                    state, self._context, self._meta, error
                )
            except Exception as e:
                self._log_observer_error(observer, "on_pipeline_error", e)

    def _log_observer_error(
        self,
        observer: Any,
        method: str,
        error: Exception,
        event: Event | None = None,
    ) -> None:
        """Safe logging of observer failures."""
        extra = {
            "observer": observer.__class__.__name__,
            "method": method,
            "error_type": type(error).__name__,
        }
        if event:
            extra.update(
                {
                    "event_type": event.type.value if hasattr(event, "type") else None,
                    "event_stage": event.stage if hasattr(event, "stage") else None,
                }
            )

        logging.error(
            "Observer %s.%s error: %s",
            observer.__class__.__name__,
            method,
            str(error),
            extra=extra,
            exc_info=True,
        )
