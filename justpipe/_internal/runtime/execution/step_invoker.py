from __future__ import annotations

import asyncio
import inspect
from typing import Any, Generic, TypeVar, TYPE_CHECKING
from collections.abc import Callable

from justpipe.types import (
    CancellationToken,
    EventType,
    HookSpec,
    InjectionMetadataMap,
    NodeKind,
    Suspend,
    _Map,
    _Next,
    _Run,
)
from justpipe._internal.shared.utils import _resolve_injection_kwargs

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep
    from justpipe._internal.runtime.orchestration.protocols import InvokerOrchestrator

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class _StepInvoker(Generic[StateT, ContextT]):
    """Encapsulates the execution logic for individual pipeline steps."""

    def __init__(
        self,
        steps: dict[str, _BaseStep],
        injection_metadata: InjectionMetadataMap,
        on_error: HookSpec | None = None,
        cancellation_token: CancellationToken | None = None,
    ):
        self._steps = steps
        self._injection_metadata = injection_metadata
        self._on_error = on_error
        self._cancellation_token = cancellation_token

    @property
    def global_error_handler(self) -> HookSpec | None:
        """Return the global error hook."""
        return self._on_error

    _KIND_MAP = {"map": NodeKind.MAP, "switch": NodeKind.SWITCH, "sub": NodeKind.SUB}

    def get_node_kind(self, name: str) -> NodeKind:
        """Resolve event node kind from a registered step name."""
        step = self._steps.get(name)
        if step is None:
            return NodeKind.STEP
        return self._KIND_MAP.get(step.get_kind(), NodeKind.STEP)

    async def execute(
        self,
        name: str,
        orchestrator: "InvokerOrchestrator",
        state: StateT | None,
        context: ContextT | None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a single step, handling parameter injection and timeouts."""
        # Input validation
        if not name:
            raise ValueError("Step name cannot be empty")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError(f"Payload must be a dict, got {type(payload).__name__}")

        step = self._steps.get(name)
        if not step:
            from justpipe._internal.shared.utils import suggest_similar

            available = ", ".join(sorted(self._steps.keys()))
            error_msg = f"Step '{name}' not found. Registered steps: {available}. "

            # Suggest similar step names
            suggestion = suggest_similar(name, self._steps.keys())
            if suggestion:
                error_msg += f"Did you mean '{suggestion}'? "
            else:
                error_msg += "Did you forget to decorate with @pipe.step()?"

            raise ValueError(error_msg)

        timeout = step.timeout

        # Resolve dependencies
        kwargs = (payload or {}).copy()
        inj_meta = self._injection_metadata.get(name, {})
        kwargs.update(
            _resolve_injection_kwargs(
                inj_meta,
                state,
                context,
                cancellation_token=self._cancellation_token,
            )
        )

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
                            await orchestrator.emit(EventType.TOKEN, name, item)
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
                raise TimeoutError(
                    f"Step '{name}' timed out after {timeout}s. "
                    f"The step did not complete within the configured timeout. "
                    f"Consider increasing the timeout or optimizing the step logic."
                )
        return await _exec()

    async def execute_handler(
        self,
        handler: HookSpec | Callable[..., Any],
        error: Exception,
        step_name: str,
        state: StateT | None,
        context: ContextT | None,
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
            inj_meta = self._injection_metadata.get(meta_key, {})
            kwargs = _resolve_injection_kwargs(
                inj_meta,
                state,
                context,
                step_name=step_name,
                cancellation_token=self._cancellation_token,
                error=error,
            )
            func = handler.func if isinstance(handler, HookSpec) else handler

        # Call function and await result if it's awaitable
        # This handles both async functions and sync functions that return awaitables
        result = func(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
