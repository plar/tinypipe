from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
    Iterator,
)
import inspect

from justpipe.middleware import Middleware, tenacity_retry_middleware
from justpipe.types import (
    Event,
    Stop,
    StepContext,
    StepInfo,
    StepConfig,
    _Map,
    _Next,
    _resolve_name,
    _Run,
    _Stop,
)
from justpipe.utils import _analyze_signature
from justpipe.graph import _validate_routing_target

class PipelineRegistry:
    def __init__(
        self,
        pipe_name: str = "Pipe",
        middleware: Optional[List[Middleware]] = None,
        state_type: Any = Any,
        context_type: Any = Any,
    ):
        self.pipe_name = pipe_name
        self.middleware = (
            list(middleware) if middleware is not None else [tenacity_retry_middleware]
        )
        self.state_type = state_type
        self.context_type = context_type
        
        self.steps: Dict[str, Callable[..., Any]] = {}
        self.topology: Dict[str, List[str]] = {}
        self.startup_hooks: List[Callable[..., Any]] = []
        self.shutdown_hooks: List[Callable[..., Any]] = []
        self.on_error_handler: Optional[Callable[..., Any]] = None
        self.injection_metadata: Dict[str, Dict[str, str]] = {}
        self.step_configs: Dict[str, StepConfig] = {}
        self.event_hooks: List[Callable[[Event], Event]] = []

    def add_middleware(self, mw: Middleware) -> None:
        self.middleware.append(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self.event_hooks.append(hook)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.startup_hooks.append(func)
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.shutdown_hooks.append(func)
        return func

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.on_error_handler = func
        self.injection_metadata["system:on_error"] = _analyze_signature(
            func, self.state_type, self.context_type, expected_unknowns=0
        )
        return func

    def _register_step_config(
        self,
        name_or_func: Union[str, Callable[..., Any]],
        func: Callable[..., Any],
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        expected_unknowns: int = 1,
        **kwargs: Any,
    ) -> str:
        stage_name = _resolve_name(name_or_func)
        
        # Extract known StepConfig fields from kwargs
        timeout = kwargs.pop("timeout", None)
        retries = kwargs.pop("retries", 0)
        map_target = kwargs.pop("map_target", None)
        switch_routes = kwargs.pop("switch_routes", None)
        switch_default = kwargs.pop("switch_default", None)
        sub_pipeline = kwargs.pop("sub_pipeline", None)
        sub_pipeline_obj = kwargs.pop("sub_pipeline_obj", None)

        self.step_configs[stage_name] = StepConfig(
            name=stage_name,
            func=func,
            timeout=timeout,
            retries=retries,
            barrier_timeout=barrier_timeout,
            on_error=on_error,
            map_target=map_target,
            switch_routes=switch_routes,
            switch_default=switch_default,
            sub_pipeline=sub_pipeline,
            sub_pipeline_obj=sub_pipeline_obj,
            extra=kwargs,
        )

        self.injection_metadata[stage_name] = _analyze_signature(
            func,
            self.state_type,
            self.context_type,
            expected_unknowns=expected_unknowns,
        )

        if on_error:
            self.injection_metadata[f"{stage_name}:on_error"] = _analyze_signature(
                on_error, self.state_type, self.context_type, expected_unknowns=0
            )

        if to:
            _validate_routing_target(to)
            self.topology[stage_name] = [
                _resolve_name(t) for t in (to if isinstance(to, list) else [to])
            ]

        return stage_name

    def _wrap_step(
        self, stage_name: str, func: Callable[..., Any], kwargs: Dict[str, Any]
    ) -> None:
        wrapped = func
        config = self.step_configs.get(stage_name)
        ctx = StepContext(
            name=stage_name, 
            kwargs=kwargs, 
            pipe_name=self.pipe_name,
            config=config
        )
        for mw in self.middleware:
            wrapped = mw(wrapped, ctx)
        self.steps[stage_name] = wrapped

    def step(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = self._register_step_config(
                name or func, func, to, barrier_timeout, on_error, **kwargs
            )
            self._wrap_step(stage_name, func, kwargs)
            return func

        if callable(name) and to is None and not kwargs:
            return decorator(name)
        return decorator

    def map(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        using: Union[str, Callable[..., Any], None] = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if using is None:
            raise ValueError("@pipe.map requires 'using' parameter")

        _validate_routing_target(using)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            target_name = _resolve_name(using)
            stage_name = self._register_step_config(
                name or func,
                func,
                to,
                barrier_timeout,
                on_error,
                map_target=target_name,
                **kwargs,
            )

            async def map_wrapper(**inner_kwargs: Any) -> _Map:
                if inspect.isasyncgenfunction(func):
                    items = [item async for item in func(**inner_kwargs)]
                    return _Map(items=items, target=target_name)

                result = await func(**inner_kwargs)
                try:
                    items = list(result)
                except TypeError:
                    raise ValueError(
                        f"Step '{stage_name}' decorated with @pipe.map "
                        f"must return an iterable, got {type(result)}"
                    )
                return _Map(items=items, target=target_name)

            self._wrap_step(stage_name, map_wrapper, kwargs)
            return func

        return decorator

    def switch(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        routes: Union[
            Dict[
                Any,
                Union[
                    str,
                    Callable[..., Any],
                    _Stop,
                ],
            ],
            Callable[[Any], Union[str, _Stop]],
            None,
        ] = None,
        default: Union[str, Callable[..., Any], None] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if routes is None:
            raise ValueError("@pipe.switch requires 'routes' parameter")

        _validate_routing_target(routes)
        if default:
            _validate_routing_target(default)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            normalized_routes = {}
            if isinstance(routes, dict):
                for key, target in routes.items():
                    normalized_routes[key] = (
                        "Stop" if isinstance(target, _Stop) else _resolve_name(target)
                    )

            stage_name = self._register_step_config(
                name or func,
                func,
                None,
                barrier_timeout,
                on_error,
                switch_routes=normalized_routes
                if isinstance(routes, dict)
                else "dynamic",
                switch_default=_resolve_name(default) if default else None,
                **kwargs,
            )

            async def switch_wrapper(**inner_kwargs: Any) -> Any:
                result = await func(**inner_kwargs)
                target = (
                    routes.get(result, default)
                    if isinstance(routes, dict)
                    else routes(result)
                )

                if target is None:
                    raise ValueError(
                        f"Step '{stage_name}' (switch) returned {result}, "
                        f"which matches no route and no default was provided."
                    )

                return Stop if isinstance(target, _Stop) else _Next(target)

            self._wrap_step(stage_name, switch_wrapper, kwargs)
            return func

        return decorator

    def sub(
        self,
        name: Union[str, Callable[..., Any], None] = None,
        using: Any = None,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        barrier_timeout: Optional[float] = None,
        on_error: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if using is None:
            raise ValueError("@pipe.sub requires 'using' parameter")

        _validate_routing_target(using)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = self._register_step_config(
                name or func,
                func,
                to,
                barrier_timeout,
                on_error,
                sub_pipeline=using.name if hasattr(using, "name") else "SubPipe",
                sub_pipeline_obj=using,
                **kwargs,
            )

            async def sub_wrapper(**inner_kwargs: Any) -> _Run:
                result = await func(**inner_kwargs)
                return _Run(pipe=using, state=result)

            self._wrap_step(stage_name, sub_wrapper, kwargs)
            return func

        return decorator

    def get_steps_info(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        for name, config in self.step_configs.items():
            targets = list(self.topology.get(name, []))
            targets.extend(config.get_targets())

            yield StepInfo(
                name=name,
                timeout=config.timeout,
                retries=config.retries if isinstance(config.retries, int) else 0,
                barrier_timeout=config.barrier_timeout,
                has_error_handler=config.on_error is not None,
                targets=targets,
                kind=config.get_kind(),
            )
