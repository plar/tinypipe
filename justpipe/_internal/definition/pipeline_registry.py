from __future__ import annotations

from typing import (
    Any,
    TYPE_CHECKING,
)
from collections.abc import Callable

from justpipe.middleware import Middleware
from justpipe.types import (
    Event,
)
from justpipe._internal.types import HookSpec, InjectionMetadataMap
from justpipe._internal.definition.step_registry import _StepRegistry
from justpipe._internal.definition.middleware_coordinator import _MiddlewareCoordinator
from justpipe._internal.definition.type_resolver import _TypeResolver
from justpipe._internal.definition.registry_validator import _RegistryValidator

if TYPE_CHECKING:
    from justpipe._internal.definition.steps import _BaseStep
    from justpipe.observability import ObserverProtocol


class _PipelineRegistry:
    """Facade for pipeline definition concerns.

    Ownership:
    - Delegates `steps`, `topology`, and `injection_metadata` to `_StepRegistry`.
    - Delegates middleware and event hooks to `_MiddlewareCoordinator`.
    - Directly owns lifecycle hooks (`startup`, `shutdown`, `error`) and observers.
    """

    def __init__(
        self,
        pipe_name: str = "Pipe",
        middleware: list[Middleware] | None = None,
        state_type: Any = Any,
        context_type: Any = Any,
        resolver: _TypeResolver | None = None,
        validator: _RegistryValidator | None = None,
        max_map_items: int | None = None,
    ):
        self.pipe_name = pipe_name
        self.state_type = state_type
        self.context_type = context_type
        self._resolver = resolver or _TypeResolver()

        self._step_registry = _StepRegistry(
            pipe_name=pipe_name,
            state_type=state_type,
            context_type=context_type,
            resolver=self._resolver,
            validator=validator or _RegistryValidator(),
            max_map_items=max_map_items,
        )

        self._middleware = _MiddlewareCoordinator(middleware=middleware)

        self.startup_hooks: list[HookSpec] = []
        self.shutdown_hooks: list[HookSpec] = []
        self.error_hook: HookSpec | None = None
        self.observers: list[ObserverProtocol] = []
        self._frozen = False

    def freeze(self) -> None:
        """Freeze all definition-time mutation APIs."""
        if self._frozen:
            return
        self._frozen = True
        self._step_registry.freeze()
        self._middleware.freeze()

    def _assert_mutable(self, action: str) -> None:
        if self._frozen:
            raise RuntimeError(
                f"Pipeline definition is frozen after first run; cannot {action}."
            )

    # --- Delegated properties ---

    @property
    def steps(self) -> dict[str, _BaseStep]:
        return self._step_registry.steps

    @property
    def topology(self) -> dict[str, list[str]]:
        return self._step_registry.topology

    @property
    def injection_metadata(self) -> InjectionMetadataMap:
        return self._step_registry.injection_metadata

    @property
    def step_registry(self) -> _StepRegistry:
        return self._step_registry

    @property
    def middleware(self) -> list[Middleware]:
        return self._middleware.middleware

    @property
    def event_hooks(self) -> list[Callable[[Event], Event]]:
        return self._middleware.event_hooks

    # --- Middleware delegation ---

    def add_middleware(self, mw: Middleware) -> None:
        self._assert_mutable("add middleware")
        self._middleware.add_middleware(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self._assert_mutable("add event hooks")
        self._middleware.add_event_hook(hook)

    # --- Hooks (kept directly) ---

    def _make_hook(
        self,
        func: Callable[..., Any],
        expected_unknowns: int = 0,
    ) -> HookSpec:
        return HookSpec(
            func=func,
            injection_metadata=self._resolver.analyze_signature(
                func,
                self.state_type,
                self.context_type,
                expected_unknowns=expected_unknowns,
            ),
        )

    def add_observer(self, observer: ObserverProtocol) -> None:
        """Add an observer to receive pipeline lifecycle events."""
        self._assert_mutable("add observers")
        self.observers.append(observer)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._assert_mutable("register startup hooks")
        self.startup_hooks.append(self._make_hook(func))
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._assert_mutable("register shutdown hooks")
        self.shutdown_hooks.append(self._make_hook(func))
        return func

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self._assert_mutable("register error hooks")
        self.error_hook = self._make_hook(func)
        return func

    # --- Finalization ---

    def finalize(self) -> None:
        """Validate pending checks, then apply middleware to all steps."""
        self._step_registry.validate_all()
        self._middleware.apply_middleware(self._step_registry.steps)
