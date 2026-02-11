import inspect
from typing import Any, TypeVar
from collections.abc import AsyncGenerator

from justpipe.types import (
    CancellationToken,
    Event,
    EventType,
)
from justpipe._internal.types import HookSpec, InjectionMetadata
from justpipe._internal.shared.utils import _resolve_injection_kwargs

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _LifecycleManager:
    """Internal manager for pipeline startup and shutdown hooks."""

    def __init__(
        self,
        startup_hooks: list[HookSpec],
        shutdown_hooks: list[HookSpec],
        cancellation_token: CancellationToken | None = None,
    ):
        self._startup = startup_hooks
        self._shutdown = shutdown_hooks
        self._cancellation_token = cancellation_token or CancellationToken()

    async def execute_startup(self, state: Any, context: Any) -> Event | None:
        """Execute startup hooks and stop at the first failure.

        Returns the first startup STEP_ERROR event, or None when all hooks succeed.
        """
        async for event in self._iter_hook_errors(
            hooks=self._startup,
            stage="startup",
            state=state,
            context=context,
            stop_on_error=True,
        ):
            return event
        return None

    async def execute_shutdown(
        self, state: Any, context: Any
    ) -> AsyncGenerator[Event, None]:
        """Execute all shutdown hooks and yield one error event per failure."""
        async for event in self._iter_hook_errors(
            hooks=self._shutdown,
            stage="shutdown",
            state=state,
            context=context,
            stop_on_error=False,
        ):
            yield event

    def _resolve_hook_kwargs(
        self, meta: InjectionMetadata, state: Any, context: Any
    ) -> dict[str, Any]:
        """Resolve dependency injection for hooks."""
        return _resolve_injection_kwargs(
            meta,
            state,
            context,
            cancellation_token=self._cancellation_token,
        )

    async def _invoke_hook(self, hook: HookSpec, state: Any, context: Any) -> None:
        kwargs = self._resolve_hook_kwargs(hook.injection_metadata, state, context)
        result = hook.func(**kwargs)
        if inspect.isawaitable(result):
            await result

    async def _iter_hook_errors(
        self,
        hooks: list[HookSpec],
        stage: str,
        state: Any,
        context: Any,
        *,
        stop_on_error: bool,
    ) -> AsyncGenerator[Event, None]:
        for hook in hooks:
            try:
                await self._invoke_hook(hook, state, context)
            except Exception as error:
                yield Event(EventType.STEP_ERROR, stage, str(error))
                if stop_on_error:
                    return
