import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

from justpipe.types import (
    Event,
    EventType,
    _Map,
    _Next,
    _Run,
    Suspend,
)
from justpipe.steps import _BaseStep

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
        on_error: Optional[Callable[..., Any]] = None,
    ):
        self._steps = steps
        self._injection_metadata = injection_metadata
        self._on_error = on_error
        self._state: Optional[StateT] = None
        self._context: Optional[ContextT] = None

    def set_context(self, state: StateT, context: Optional[ContextT]) -> None:
        """Set the execution context for the current run."""
        self._state = state
        self._context = context

    def _resolve_injections(
        self,
        meta_key: str,
        error: Optional[Exception] = None,
        step_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve dependency injection parameters for a step or handler."""
        inj_meta = self._injection_metadata.get(meta_key, {})
        kwargs: Dict[str, Any] = {}
        for param_name, source in inj_meta.items():
            if source == "state":
                kwargs[param_name] = self._state
            elif source == "context":
                kwargs[param_name] = self._context
            elif source == "error":
                kwargs[param_name] = error
            elif source == "step_name":
                kwargs[param_name] = step_name
        return kwargs

    async def execute(
        self,
        name: str,
        queue: asyncio.Queue[Union[Event, _StepResult]],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a single step, handling parameter injection and timeouts."""
        step = self._steps.get(name)
        if not step:
            raise ValueError(f"Step not found: {name}")

        timeout = step.timeout

        # Resolve dependencies
        kwargs = (payload or {}).copy()
        kwargs.update(self._resolve_injections(name))

        async def _exec() -> Any:
            # We await execute() which calls the middleware-wrapped function.
            # If the underlying function is a generator, execute() returns the generator object.
            # If it's a regular function, it returns the result.
            result = await step.execute(**kwargs)
            
            if inspect.isasyncgen(result):
                last_val = None
                async for item in result:
                    if isinstance(item, (_Next, _Map, _Run, Suspend)):
                        last_val = item
                    else:
                        await queue.put(Event(EventType.TOKEN, name, item))
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
        handler: Callable[..., Any], 
        error: Exception, 
        step_name: str,
        is_global: bool = False
    ) -> Any:
        """Execute a specific error handler."""
        # For global handlers, we might use a specific metadata key
        meta_key = "system:on_error" if is_global else f"{step_name}:on_error"
        
        # If the handler is the global one but attached locally (edge case),
        # we might need to be careful, but generally the caller decides the context.
        
        kwargs = self._resolve_injections(meta_key, error=error, step_name=step_name)

        if inspect.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return handler(**kwargs)
