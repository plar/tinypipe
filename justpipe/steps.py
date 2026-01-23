from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING
import inspect

from justpipe.types import (
    StepConfig,
    _Map,
    _Next,
    _Run,
    _Stop,
    Stop,
    StepContext,
)

if TYPE_CHECKING:
    from justpipe.middleware import Middleware

class _BaseStep(ABC):
    """Abstract base class for all pipeline steps."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        timeout: Optional[float] = None,
        retries: Union[int, Dict[str, Any]] = 0,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        pipe_name: str = "Pipe",
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.original_func = func
        self.timeout = timeout
        self.retries = retries
        self.barrier_timeout = barrier_timeout
        self.on_error = on_error
        self.pipe_name = pipe_name
        self.extra = extra or {}
        
        self._wrapped_func: Optional[Callable[..., Any]] = None

    def wrap_middleware(self, middleware: List["Middleware"]) -> None:
        """Apply middleware to the step function."""
        # Create a temporary config object for middleware context
        # This preserves backward compatibility for middleware expecting StepConfig
        # In a future iteration, StepContext should accept BaseStep directly
        config_compat = self.to_config()
        
        wrapped = self.original_func
        ctx = StepContext(
            name=self.name,
            kwargs=self.extra,
            pipe_name=self.pipe_name,
            config=config_compat
        )
        for mw in middleware:
            wrapped = mw(wrapped, ctx)
        self._wrapped_func = wrapped

    @abstractmethod
    def get_kind(self) -> str:
        pass

    @abstractmethod
    def get_targets(self) -> List[str]:
        pass

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the step logic."""
        func = self._wrapped_func if self._wrapped_func is not None else self.original_func
        res = func(**kwargs)
        
        if inspect.isawaitable(res):
            return await res
        return res

    def to_config(self) -> StepConfig:
        """Convert back to StepConfig for backward compatibility."""
        return StepConfig(
            name=self.name,
            func=self.original_func,
            timeout=self.timeout,
            retries=self.retries,
            barrier_timeout=self.barrier_timeout,
            on_error=self.on_error,
            extra=self.extra,
        )


class _StandardStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        to: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.to = to or []

    def get_kind(self) -> str:
        return "step"

    def get_targets(self) -> List[str]:
        return self.to

    async def execute(self, **kwargs: Any) -> Any:
        return await super().execute(**kwargs)

    def to_config(self) -> StepConfig:
        cfg = super().to_config()
        # The 'to' topology is stored separately in the registry/graph,
        # but StepConfig doesn't hold 'to' for standard steps explicitly
        # other than for generic 'get_targets'.
        # We'll rely on the fact that standard steps are topology-driven.
        return cfg


class _MapStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        map_target: str,
        to: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.map_target = map_target
        self.to = to or []

    def get_kind(self) -> str:
        return "map"

    def get_targets(self) -> List[str]:
        return [self.map_target] + self.to

    async def execute(self, **kwargs: Any) -> Any:
        func = self._wrapped_func if self._wrapped_func is not None else self.original_func
        
        res = func(**kwargs)
        if inspect.isawaitable(res):
            res = await res

        if inspect.isasyncgen(res):
            items = [item async for item in res]
            return _Map(items=items, target=self.map_target)

        try:
            items = list(res)
        except TypeError:
            raise ValueError(
                f"Step '{self.name}' decorated with @pipe.map "
                f"must return an iterable, got {type(res)}"
            )
        return _Map(items=items, target=self.map_target)

    def to_config(self) -> StepConfig:
        cfg = super().to_config()
        cfg.map_target = self.map_target
        return cfg


class _SwitchStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        routes: Union[Dict[Any, str], Callable[[Any], Union[str, _Stop]]],
        default: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.routes = routes
        self.default = default

    def get_kind(self) -> str:
        return "switch"

    def get_targets(self) -> List[str]:
        targets: List[str] = []
        if isinstance(self.routes, dict):
            targets.extend(t for t in self.routes.values() if t != "Stop")
        if self.default:
            targets.append(self.default)
        return targets

    async def execute(self, **kwargs: Any) -> Any:
        func = self._wrapped_func if self._wrapped_func is not None else self.original_func
        
        res = func(**kwargs)
        if inspect.isawaitable(res):
            result = await res
        else:
            result = res
        
        target: Union[str, _Stop, None] = None
        if isinstance(self.routes, dict):
            target = self.routes.get(result, self.default)
        else:
            target = self.routes(result)
            
        if target is None:
             # If using callable routes and it returns None, check default
             if not isinstance(self.routes, dict) and self.default:
                 target = self.default
             else:
                raise ValueError(
                    f"Step '{self.name}' (switch) returned {result}, "
                    f"which matches no route and no default was provided."
                )

        return Stop if (isinstance(target, _Stop) or target == "Stop") else _Next(target)

    def to_config(self) -> StepConfig:
        cfg = super().to_config()
        cfg.switch_routes = self.routes # type: ignore
        cfg.switch_default = self.default
        return cfg


class _SubPipelineStep(_BaseStep):
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        sub_pipeline_name: str,
        sub_pipeline_obj: Any,
        to: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        super().__init__(name, func, **kwargs)
        self.sub_pipeline_name = sub_pipeline_name
        self.sub_pipeline_obj = sub_pipeline_obj
        self.to = to or []

    def get_kind(self) -> str:
        return "sub"

    def get_targets(self) -> List[str]:
        return self.to

    async def execute(self, **kwargs: Any) -> Any:
        func = self._wrapped_func if self._wrapped_func is not None else self.original_func
        
        res = func(**kwargs)
        if inspect.isawaitable(res):
            result = await res
        else:
            result = res
            
        return _Run(pipe=self.sub_pipeline_obj, state=result)

    def to_config(self) -> StepConfig:
        cfg = super().to_config()
        cfg.sub_pipeline = self.sub_pipeline_name
        cfg.sub_pipeline_obj = self.sub_pipeline_obj
        return cfg
