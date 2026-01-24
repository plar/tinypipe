import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

from justpipe.types import (
    Event,
    EventType,
    HookSpec,
    _Map,
    _Next,
    _Run,
    Suspend,
)
from justpipe.steps import _BaseStep
from justpipe.utils import _resolve_injection_kwargs

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


@dataclass
class _StepResult:
    owner: str
    name: str
    result: Any
    payload: Optional[Dict[str, Any]] = None


class _StepInvoker(Generic[StateT, ContextT]):
    """Encapsulates the execution logic for individual pipeline steps."""

    def __init__(
        self,
        steps: Dict[str, _BaseStep],
        injection_metadata: Dict[str, Dict[str, str]],
        on_error: Optional[HookSpec] = None,
    ):
        self._steps = steps
        self._injection_metadata = injection_metadata
        self._on_error = on_error

    @property
    def global_error_handler(self) -> Optional[HookSpec]:
        """Return the global error hook."""
        return self._on_error

    def _resolve_injections(
        self,
        meta_key: str,
        state: Optional[StateT],
        context: Optional[ContextT],
        error: Optional[Exception] = None,
        step_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve dependency injection parameters for a step or handler."""
        inj_meta = self._injection_metadata.get(meta_key, {})
        return _resolve_injection_kwargs(
            inj_meta, state, context, error=error, step_name=step_name
        )

    async def execute(
        self,
        name: str,
        queue: asyncio.Queue[Union[Event, _StepResult]],
        state: Optional[StateT],
        context: Optional[ContextT],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a single step, handling parameter injection and timeouts."""
        step = self._steps.get(name)
        if not step:
            raise ValueError(f"Step not found: {name}")

        timeout = step.timeout

        # Resolve dependencies
        kwargs = (payload or {}).copy()
        kwargs.update(self._resolve_injections(name, state, context))

        async def _exec() -> Any:
            # We await execute() which calls the middleware-wrapped function.
            # If the underlying function is a generator, execute() returns the generator object.
            # If it's a regular function, it returns the result.
            result = await step.execute(**kwargs)

            if inspect.isasyncgen(result):
                last_val = None
                try:
                    async for item in result:
                        if isinstance(item, (_Next, _Map, _Run, Suspend)):
                            last_val = item
                        else:
                            await queue.put(Event(EventType.TOKEN, name, item))
                except asyncio.CancelledError:
                    await result.aclose()
                    raise
                return last_val
            else:
                return result

        if timeout:
            try:
                return await asyncio.wait_for(_exec(), timeout=timeout)
            except (asyncio.TimeoutError, TimeoutError):
                raise TimeoutError(f"Step '{name}' timed out after {timeout}s")
        return await _exec()

    async def execute_handler(
        self,
        handler: Union[HookSpec, Callable[..., Any]],
        error: Exception,
        step_name: str,
        state: Optional[StateT],
        context: Optional[ContextT],
        is_global: bool = False,
    ) -> Any:
        """Execute a specific error handler."""
        if is_global:
            if not isinstance(handler, HookSpec):
                raise TypeError("Global error hook must be a HookSpec")
            kwargs = _resolve_injection_kwargs(
                handler.injection_metadata,
                state,
                context,
                error=error,
                step_name=step_name,
            )
            func = handler.func
        else:
            meta_key = f"{step_name}:on_error"
            kwargs = self._resolve_injections(
                meta_key, state, context, error=error, step_name=step_name
            )
            func = handler.func if isinstance(handler, HookSpec) else handler

        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)
