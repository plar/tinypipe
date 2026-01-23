import asyncio
from typing import Any, Dict, Optional, Union
import traceback
import time
import logging

from justpipe.invoker import _StepInvoker, _StepResult
from justpipe.steps import _BaseStep
from justpipe.types import Event, EventType

class _FailureHandler:
    """Manages error escalation and reporting."""

    def __init__(
        self,
        steps: Dict[str, _BaseStep],
        invoker: _StepInvoker[Any, Any],
        queue: asyncio.Queue[Union[Event, _StepResult]],
    ):
        self._steps = steps
        self._invoker = invoker
        self._queue = queue

    async def handle_failure(
        self,
        name: str,
        owner: str,
        payload: Optional[Dict[str, Any]],
        error: Exception,
        state: Optional[Any] = None
    ) -> None:
        """Centralized error handling logic with escalation."""
        step = self._steps.get(name)
        local_handler = step.on_error if step else None
        
        # 1. Try Local Handler
        if local_handler:
            try:
                res = await self._invoker.execute_handler(
                    local_handler, error, name, is_global=False
                )
                await self._queue.put(_StepResult(owner, name, res, payload))
                return
            except Exception as new_error:
                # Local handler failed, escalate to global
                error = new_error

        # 2. Try Global Handler
        global_handler = self._invoker._on_error
        if global_handler:
            try:
                res = await self._invoker.execute_handler(
                    global_handler, error, name, is_global=True
                )
                await self._queue.put(_StepResult(owner, name, res, payload))
                return
            except Exception as final_error:
                error = final_error

        # 3. Default Reporting (Terminal)
        self._log_error(name, error, state)
        await self._report_error(name, owner, error)

    async def _report_error(self, name: str, owner: str, error: Exception) -> None:
        await self._queue.put(Event(EventType.ERROR, name, str(error)))
        await self._queue.put(_StepResult(owner, name, None))

    def _log_error(self, name: str, error: Exception, state: Optional[Any]) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        stack = traceback.format_exc()
        state_str = str(state)[:1000]
        logging.error(
            f"[{timestamp}] Step '{name}' failed with {type(error).__name__}: {error}\n"
            f"State: {state_str}\n"
            f"Stack trace:\n{stack}"
        )
