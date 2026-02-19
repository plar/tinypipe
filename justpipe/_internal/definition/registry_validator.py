from __future__ import annotations

from typing import Any
from collections.abc import Iterable

from justpipe.types import DefinitionError, Stop
from justpipe._internal.shared.utils import _resolve_name


class _RegistryValidator:
    """Internal component for validating pipeline registry configurations."""

    def validate_routing_target_type(
        self, target: Any, step_name: str = "Unknown"
    ) -> None:
        """Validate that a routing target is a valid name or callable."""
        if isinstance(target, str) or callable(target):
            return
        if isinstance(target, list):
            for t in target:
                self.validate_routing_target_type(t, step_name)
        elif isinstance(target, dict):
            for t in target.values():
                if t is not Stop:
                    self.validate_routing_target_type(t, step_name)
        else:
            raise DefinitionError(
                f"Step '{step_name}' has invalid routing target type: {type(target).__name__}. "
                "Expected str, callable, list, or dict."
            )

    def validate_linear_to(
        self,
        step_name: str,
        to: str | list[str] | Any | None,
    ) -> None:
        """Validate that 'to' parameter is appropriate for linear steps (step, map, sub)."""
        if to is None:
            return

        if isinstance(to, dict):
            raise DefinitionError(
                f"Step '{step_name}' uses a dictionary for 'to='. "
                "Standard steps only support linear transitions (string, list, or callable). "
                "Use @pipe.switch if you need conditional routing (switch-case)."
            )

        # Ensure it's something _resolve_name can handle without crashing if it's not a list
        if not isinstance(to, (str, list)) and not callable(to):
            raise DefinitionError(
                f"Step '{step_name}' has invalid 'to=' type: {type(to).__name__}. "
                "Expected string, list of strings, or callable."
            )

    def validate_routing_target(self, target: Any, owner_name: str) -> None:
        """Ensure a step doesn't route to itself or have other invalid targets."""
        targets = target if isinstance(target, list) else [target]
        for t in targets:
            # Resolve name if it's a callable
            t_name = _resolve_name(t)
            if t_name == owner_name:
                raise DefinitionError(
                    f"Step '{owner_name}' cannot route to itself. "
                    f"Infinite loops are not allowed in the static topology. "
                    f"If you need cycles, use runtime redirection by returning a step name string."
                )

    def validate_switch_routes(
        self, validation: dict[str, Any], available_steps: Iterable[str]
    ) -> None:
        """Validate switch route targets exist."""
        from justpipe._internal.shared.utils import suggest_similar

        switch_name = validation["switch_name"]
        targets = validation["targets"]
        steps_list = list(available_steps)

        for target in targets:
            if target not in steps_list:
                available = ", ".join(sorted(steps_list))
                error_msg = (
                    f"Switch '{switch_name}' routes to undefined step '{target}'. "
                    f"Available steps: {available}. "
                )

                # Suggest similar step names
                suggestion = suggest_similar(target, steps_list)
                if suggestion:
                    error_msg += f"Did you mean '{suggestion}'? "

                error_msg += (
                    f"Define step '{target}' before calling run() or fix route."
                )
                raise DefinitionError(error_msg)
