from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from collections.abc import Callable
import inspect

from justpipe.types import (
    BarrierType,
    NodeKind,
    Stop,
    StepContext,
    _Map,
    _Next,
    _Run,
)

if TYPE_CHECKING:
    from justpipe.middleware import Middleware


class _BaseStep(ABC):
    """Abstract base class for all pipeline steps."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        timeout: float | None = None,
        retries: int | dict[str, Any] = 0,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        pipe_name: str = "Pipe",
        extra: dict[str, Any] | None = None,
    ):
        self.name = name
        self._original_func = func
        self.timeout = timeout
        self.retries = retries
        self.barrier_timeout = barrier_timeout
        self.barrier_type = barrier_type or BarrierType.ALL
        self.on_error = on_error
        self.pipe_name = pipe_name
        self.extra = extra or {}

        self._wrapped_func: Callable[..., Any] | None = None

    @property
    def _active_func(self) -> Callable[..., Any]:
        """Return the wrapped function if middleware was applied, otherwise the original."""
        return self._wrapped_func or self._original_func

    def wrap_middleware(self, middleware: list["Middleware"]) -> None:
        """Apply middleware to the step function."""
        wrapped = self._original_func
        ctx = StepContext(
            name=self.name,
            kwargs=self.extra,
            pipe_name=self.pipe_name,
            retries=self.retries,
        )
        for mw in middleware:
            wrapped = mw(wrapped, ctx)
        self._wrapped_func = wrapped

    @abstractmethod
    def get_kind(self) -> NodeKind:
        pass

    @abstractmethod
    def get_targets(self) -> list[str]:
        pass

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the step logic."""
        res = self._active_func(**kwargs)

        if inspect.isawaitable(res):
            return await res
        return res


class _StandardStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        to: list[str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.to = to or []

    def get_kind(self) -> NodeKind:
        return NodeKind.STEP

    def get_targets(self) -> list[str]:
        return self.to


class _MapStep(_BaseStep):
    # Default maximum items to materialize from async generators (safety limit)
    DEFAULT_MAX_ITEMS = 100_000

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        each: str,
        to: list[str] | None = None,
        max_concurrency: int | None = None,
        max_map_items: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.each = each
        self.to = to or []
        self.max_concurrency = max_concurrency
        self.max_map_items = max_map_items or self.DEFAULT_MAX_ITEMS

    def get_kind(self) -> NodeKind:
        return NodeKind.MAP

    def get_targets(self) -> list[str]:
        return [self.each] + self.to

    async def execute(self, **kwargs: Any) -> Any:
        res = await super().execute(**kwargs)

        if inspect.isasyncgen(res):
            # Materialize async generator with safety limit to prevent OOM
            items = []
            async for item in res:
                items.append(item)
                if len(items) > self.max_map_items:
                    raise ValueError(
                        f"Step '{self.name}' async generator exceeded maximum of "
                        f"{self.max_map_items} items. This safety limit prevents "
                        f"out-of-memory errors. Consider chunking your data or using "
                        f"a smaller batch size."
                    )
            return _Map(items=items, target=self.each)

        try:
            items = list(res)
        except TypeError:
            raise ValueError(
                f"Step '{self.name}' decorated with @pipe.map "
                f"must return an iterable, got {type(res)}"
            )
        return _Map(items=items, target=self.each)


class _SwitchStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        to: dict[Any, str | type[Stop]] | Callable[[Any], str | type[Stop]],
        default: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.to = to
        self.default = default

    def get_kind(self) -> NodeKind:
        return NodeKind.SWITCH

    def get_targets(self) -> list[str]:
        targets: list[str] = []
        if isinstance(self.to, dict):
            targets.extend(t for t in self.to.values() if isinstance(t, str))
        if self.default:
            targets.append(self.default)
        return targets

    async def execute(self, **kwargs: Any) -> Any:
        result = await super().execute(**kwargs)

        target: str | type[Stop] | None = None
        if isinstance(self.to, dict):
            target = self.to.get(result, self.default)
        else:
            target = self.to(result)

        if target is None:
            # If using callable routes and it returns None, check default
            if not isinstance(self.to, dict) and self.default:
                target = self.default
            else:
                # Build helpful error message with available routes
                error_msg = f"Step '{self.name}' (switch) returned {repr(result)}, which matches no route"

                if isinstance(self.to, dict):
                    available_routes = list(self.to.keys())
                    if available_routes:
                        routes_str = ", ".join(repr(k) for k in available_routes)
                        error_msg += f". Available routes: {routes_str}"

                        # Suggest similar keys if result is a string
                        if isinstance(result, str):
                            from justpipe._internal.shared.utils import suggest_similar

                            str_routes = [
                                k for k in available_routes if isinstance(k, str)
                            ]
                            suggestion = suggest_similar(result, str_routes)
                            if suggestion:
                                error_msg += f". Did you mean {repr(suggestion)}?"

                if self.default:
                    error_msg += f" (default route: {self.default})"
                else:
                    error_msg += ". No default route was provided"

                error_msg += "."
                raise ValueError(error_msg)

        return Stop() if target is Stop else _Next(target)


class _SubPipelineStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        pipeline: Any,
        to: list[str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.pipeline = pipeline
        self.to = to or []

    def get_kind(self) -> NodeKind:
        return NodeKind.SUB

    def get_targets(self) -> list[str]:
        return self.to

    async def execute(self, **kwargs: Any) -> Any:
        result = await super().execute(**kwargs)
        return _Run(pipe=self.pipeline, state=result)
