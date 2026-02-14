"""Meta implementation — structured metadata with step/run/pipeline scopes."""

from __future__ import annotations

import dataclasses
import types as builtin_types
import typing
from contextvars import ContextVar
from typing import Any, Union, get_type_hints

from justpipe.types import DefinitionError, Meta

_current_step_meta_var: ContextVar[_ScopedMeta | None] = ContextVar(
    "_jp_current_step_meta", default=None
)


class _ScopedMeta:
    """Shared implementation for step and run scopes."""

    __slots__ = ("_data", "_tags", "_metrics", "_counters")

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._tags: set[str] = set()
        self._metrics: dict[str, list[float]] = {}
        self._counters: dict[str, float] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def add_tag(self, tag: str) -> None:
        self._tags.add(tag)

    def record_metric(self, name: str, value: float) -> None:
        self._metrics.setdefault(name, []).append(value)

    def increment(self, name: str, amount: float = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + amount

    def _snapshot(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        if self._data:
            snap["data"] = dict(self._data)
        if self._tags:
            snap["tags"] = sorted(self._tags)
        if self._metrics:
            snap["metrics"] = {k: list(v) for k, v in self._metrics.items()}
        if self._counters:
            snap["counters"] = dict(self._counters)
        return snap


class _StepMetaImpl:
    """Step-scoped metadata — stateless proxy that delegates to ``_current_step_meta_var``.

    The coordinator sets a fresh ``_ScopedMeta`` per invocation via the contextvar;
    this proxy simply forwards calls to whichever ``_ScopedMeta`` is active.
    """

    __slots__ = ()

    @staticmethod
    def _current() -> _ScopedMeta:
        meta = _current_step_meta_var.get()
        if meta is None:
            raise RuntimeError(
                "ctx.meta.step is only available inside a step execution"
            )
        return meta

    def set(self, key: str, value: Any) -> None:
        self._current().set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._current().get(key, default)

    def add_tag(self, tag: str) -> None:
        self._current().add_tag(tag)

    def record_metric(self, name: str, value: float) -> None:
        self._current().record_metric(name, value)

    def increment(self, name: str, amount: float = 1) -> None:
        self._current().increment(name, amount)


class _PipelineMetaImpl:
    """Read-only pipeline definition metadata."""

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class _MetaImpl:
    """Concrete Meta implementation. Created by framework, set on user's context."""

    __slots__ = ("_step", "_run", "_pipeline")

    def __init__(self, pipe_metadata: dict[str, Any] | None = None) -> None:
        self._step = _StepMetaImpl()
        self._run = _ScopedMeta()
        self._pipeline = _PipelineMetaImpl(pipe_metadata or {})

    @property
    def step(self) -> _StepMetaImpl:
        return self._step

    @property
    def run(self) -> _ScopedMeta:
        return self._run

    @property
    def pipeline(self) -> _PipelineMetaImpl:
        return self._pipeline

    def _snapshot(self) -> dict[str, Any]:
        return self._run._snapshot()


def _is_meta_type(tp: Any) -> bool:
    """Check if a type annotation refers to Meta."""
    if tp is Meta:
        return True

    # Handle Meta | None, Optional[Meta], Union[Meta, None]
    origin = typing.get_origin(tp)
    if origin is Union or origin is builtin_types.UnionType:
        args = typing.get_args(tp)
        non_none = [a for a in args if a is not type(None)]
        return len(non_none) == 1 and non_none[0] is Meta

    return False


def detect_and_init_meta(
    context: Any,
    pipe_metadata: dict[str, Any] | None = None,
) -> _MetaImpl | None:
    """Scan context type hints for Meta-typed field, init with implementation.

    Returns the _MetaImpl instance if Meta field found and initialized, None otherwise.

    Raises:
        DefinitionError: If context is frozen or has multiple Meta fields.
    """
    if context is None:
        return None

    ctx_type = type(context)

    # Get type hints
    try:
        hints = get_type_hints(ctx_type)
    except Exception:
        # Fallback for complex forward refs
        hints = getattr(ctx_type, "__annotations__", {})

    if not hints:
        return None

    # Find Meta fields
    meta_fields: list[str] = [name for name, tp in hints.items() if _is_meta_type(tp)]

    if not meta_fields:
        return None

    if len(meta_fields) > 1:
        raise DefinitionError(
            "Only one Meta field allowed on context, "
            f"found {len(meta_fields)}: {', '.join(meta_fields)}"
        )

    field_name = meta_fields[0]

    # Check frozen dataclass
    if dataclasses.is_dataclass(ctx_type):
        dc_fields = {f.name: f for f in dataclasses.fields(ctx_type)}
        if field_name in dc_fields:
            # Check if the dataclass is frozen
            params = getattr(ctx_type, "__dataclass_params__", None)
            if params and getattr(params, "frozen", False):
                raise DefinitionError(
                    "Meta requires a mutable context. "
                    "Use `@dataclass` without `frozen=True`."
                )

    meta_impl = _MetaImpl(pipe_metadata)
    setattr(context, field_name, meta_impl)
    return meta_impl
