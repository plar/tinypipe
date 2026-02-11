import inspect
from typing import Any, get_type_hints
from collections.abc import Callable

from justpipe.types import (
    CancellationToken,
    DefinitionError,
)
from justpipe._internal.types import InjectionMetadata, InjectionSource

STATE_ALIASES: frozenset[str] = frozenset({"s", "state"})
CONTEXT_ALIASES: frozenset[str] = frozenset({"c", "ctx", "context"})
ERROR_ALIASES: frozenset[str] = frozenset({"e", "error", "exception"})
STEP_NAME_ALIASES: frozenset[str] = frozenset({"step_name", "stage"})
CANCEL_ALIASES: frozenset[str] = frozenset({"cancel", "cancellation_token"})


class _TypeResolver:
    """Internal component for analyzing function signatures and resolving injections."""

    def analyze_signature(
        self,
        func: Callable[..., Any],
        state_type: type[Any],
        context_type: type[Any],
        expected_unknowns: int = 0,
    ) -> InjectionMetadata:
        """
        Analyze a function's signature to determine which parameters should be injected.

        Args:
            func: The function to analyze.
            state_type: The type of the pipeline state.
            context_type: The type of the pipeline context.
            expected_unknowns: Number of parameters that are allowed to be unknown
                             (e.g. for map workers).

        Returns:
            A dictionary mapping parameter names to their source (state, context, etc.).
        """
        try:
            hints = get_type_hints(func)
        except (TypeError, NameError):
            # Fallback for complex types or forward refs that can't be resolved
            hints = {}

        sig = inspect.signature(func)
        mapping: InjectionMetadata = {}
        unknowns = []

        for name, param in sig.parameters.items():
            # Skip *args and **kwargs
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Skip parameters with defaults
            if param.default is not param.empty:
                continue

            param_type = hints.get(name, param.annotation)

            # 1. Match by type
            if self._is_subclass(param_type, state_type):
                mapping[name] = InjectionSource.STATE
            elif self._is_subclass(param_type, context_type):
                mapping[name] = InjectionSource.CONTEXT
            elif self._is_subclass(param_type, CancellationToken):
                mapping[name] = InjectionSource.CANCEL
            elif self._is_subclass(param_type, Exception):
                mapping[name] = InjectionSource.ERROR
            # 2. Match by Name (Fallback)
            elif name in STATE_ALIASES:
                mapping[name] = InjectionSource.STATE
            elif name in CONTEXT_ALIASES:
                mapping[name] = InjectionSource.CONTEXT
            elif name in ERROR_ALIASES:
                mapping[name] = InjectionSource.ERROR
            elif name in STEP_NAME_ALIASES:
                mapping[name] = InjectionSource.STEP_NAME
            elif name in CANCEL_ALIASES:
                mapping[name] = InjectionSource.CANCEL
            # 3. Handle Unknowns (for Map items)
            else:
                mapping[name] = InjectionSource.UNKNOWN
                unknowns.append(name)

        if len(unknowns) > expected_unknowns:
            error_msg = (
                f"Step '{func.__name__}' has {len(unknowns)} unrecognized parameters: {unknowns}. "
                f"Expected {expected_unknowns} unknown parameter(s) for this step type. "
            )

            # Add context-specific help
            if expected_unknowns == 0:
                error_msg += (
                    "Lifecycle hooks (on_startup, on_shutdown, on_error) should only use "
                    "typed parameters like 'state: State' or 'ctx: Context'. "
                )
            elif expected_unknowns == 1:
                error_msg += "Regular steps allow one injected parameter (e.g., 'item' in map workers). "

            state_name = (
                state_type.__name__
                if hasattr(state_type, "__name__")
                else str(state_type)
            )
            context_name = (
                context_type.__name__
                if hasattr(context_type, "__name__")
                else str(context_type)
            )

            error_msg += (
                f"Parameters must be typed as {state_name} or {context_name}, "
                f"or use special names: 'state', 'context', 'error', 'step_name'."
            )

            raise DefinitionError(error_msg)

        return mapping

    def _is_subclass(self, param_type: Any, target_type: Any) -> bool:
        """
        Check if target_type is a subclass of param_type.
        This allows injecting a specific state (e.g. ChildState) into a
        parameter typed as a superclass (e.g. BaseState).
        """
        if param_type is inspect.Parameter.empty or target_type is Any:
            return False
        try:
            return issubclass(target_type, param_type)
        except TypeError:
            return param_type is target_type
