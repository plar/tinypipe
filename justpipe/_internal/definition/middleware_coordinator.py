from collections.abc import Callable

from justpipe.middleware import Middleware, tenacity_retry_middleware
from justpipe._internal.definition.steps import _BaseStep
from justpipe.types import Event


class _MiddlewareCoordinator:
    def __init__(self, middleware: list[Middleware] | None = None):
        self.middleware: list[Middleware] = (
            list(middleware) if middleware is not None else [tenacity_retry_middleware]
        )
        self.event_hooks: list[Callable[[Event], Event]] = []
        self._frozen = False
        # Monotonic middleware configuration version. Increment on each add_middleware.
        self._middleware_version = 0
        # Tracks which middleware version each step was wrapped with.
        self._step_wrap_version: dict[str, int] = {}

    def freeze(self) -> None:
        self._frozen = True

    def _assert_mutable(self, action: str) -> None:
        if self._frozen:
            raise RuntimeError(
                f"Pipeline configuration is frozen after first run; cannot {action}."
            )

    def add_middleware(self, mw: Middleware) -> None:
        self._assert_mutable("add middleware")
        self.middleware.append(mw)
        self._middleware_version += 1

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self._assert_mutable("add event hooks")
        self.event_hooks.append(hook)

    def apply_middleware(self, steps: dict[str, _BaseStep]) -> None:
        """Apply middleware to all steps that are stale for current middleware version."""
        current_version = self._middleware_version
        for name, step in steps.items():
            wrapped_version = self._step_wrap_version.get(name)
            if step._wrapped_func is None or wrapped_version != current_version:
                step.wrap_middleware(self.middleware)
                self._step_wrap_version[name] = current_version

        # Drop metadata for removed steps.
        removed_steps = set(self._step_wrap_version) - set(steps)
        for name in removed_steps:
            del self._step_wrap_version[name]
