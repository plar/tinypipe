from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
    Iterator,
)

from justpipe.middleware import Middleware, tenacity_retry_middleware
from justpipe.types import (
    Event,
    StepInfo,
    StepConfig,
    _resolve_name,
    _Stop,
)
from justpipe.steps import (
    _BaseStep,
    _StandardStep,
    _MapStep,
    _SwitchStep,
    _SubPipelineStep,
)
from justpipe.utils import _analyze_signature
from justpipe.graph import _validate_routing_target

class _PipelineRegistry:
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
        
        # Maps step name to the executable _BaseStep object
        self.steps: Dict[str, _BaseStep] = {}
        self.topology: Dict[str, List[str]] = {}
        self.startup_hooks: List[Callable[..., Any]] = []
        self.shutdown_hooks: List[Callable[..., Any]] = []
        self.on_error_handler: Optional[Callable[..., Any]] = None
        self.injection_metadata: Dict[str, Dict[str, str]] = {}
        self.event_hooks: List[Callable[[Event], Event]] = []

    @property
    def step_configs(self) -> Dict[str, StepConfig]:
        """Backward compatibility property returning StepConfig objects."""
        return {name: step.to_config() for name, step in self.steps.items()}

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

    def _register_step(
        self,
        step_obj: _BaseStep,
        to: Union[
            str, List[str], Callable[..., Any], List[Callable[..., Any]], None
        ] = None,
        on_error: Optional[Callable[..., Any]] = None,
        expected_unknowns: int = 1,
    ) -> str:
        stage_name = step_obj.name
        self.steps[stage_name] = step_obj

        # Apply middleware immediately
        step_obj.wrap_middleware(self.middleware)

        self.injection_metadata[stage_name] = _analyze_signature(
            step_obj.original_func,
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
            stage_name = _resolve_name(name or func)
            
            # Extract generic step kwargs
            timeout = kwargs.pop("timeout", None)
            retries = kwargs.pop("retries", 0)
            
            step_obj = _StandardStep(
                name=stage_name,
                func=func,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])] if to else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs
            )
            
            self._register_step(step_obj, to, on_error)
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
            stage_name = _resolve_name(name or func)
            target_name = _resolve_name(using)
            
            timeout = kwargs.pop("timeout", None)
            retries = kwargs.pop("retries", 0)

            step_obj = _MapStep(
                name=stage_name,
                func=func,
                map_target=target_name,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])] if to else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs
            )

            self._register_step(step_obj, to, on_error)
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
            stage_name = _resolve_name(name or func)
            
            normalized_routes = {}
            if isinstance(routes, dict):
                for key, target in routes.items():
                    normalized_routes[key] = (
                        "Stop" if isinstance(target, _Stop) else _resolve_name(target)
                    )
            
            timeout = kwargs.pop("timeout", None)
            retries = kwargs.pop("retries", 0)

            step_obj = _SwitchStep(
                name=stage_name,
                func=func,
                routes=normalized_routes if isinstance(routes, dict) else routes,
                default=_resolve_name(default) if default else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs
            )

            self._register_step(step_obj, None, on_error)
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
            stage_name = _resolve_name(name or func)
            
            timeout = kwargs.pop("timeout", None)
            retries = kwargs.pop("retries", 0)

            step_obj = _SubPipelineStep(
                name=stage_name,
                func=func,
                sub_pipeline_name=using.name if hasattr(using, "name") else "SubPipe",
                sub_pipeline_obj=using,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])] if to else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs
            )

            self._register_step(step_obj, to, on_error)
            return func

        return decorator

    def get_steps_info(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        for name, step in self.steps.items():
            targets = list(self.topology.get(name, []))
            targets.extend(step.get_targets())
            
            # Use set to dedup targets that might be in both topology and step internal config
            # (though normally StandardStep separates them, but get_targets for StandardStep returns self.to)
            # Actually topology dict is the primary source for StandardStep in the current implementation,
            # but StandardStep.get_targets() returns self.to which is initialized from 'to'.
            
            # Wait, in _register_step I add 'to' to self.topology. 
            # StandardStep also stores it. Duplicate?
            # self.topology stores explicit routing.
            # step.get_targets() stores targets inherent to the step logic (map target, switch routes).
            # StandardStep: get_targets() returns self.to.
            
            # If I put 'to' in self.topology AND in step.to, I have duplication.
            # But the graph builder looks at topology AND step_configs.get_targets().
            # I should align this.
            
            # Current Registry behavior:
            # 1. Stores 'to' in self.topology.
            # 2. Config doesn't store 'to'.
            # New behavior:
            # 1. Stores 'to' in self.topology.
            # 2. StandardStep stores 'to' in self.to.
            
            # Let's just yield unique targets.
            unique_targets = sorted(list(set(targets)))

            yield StepInfo(
                name=name,
                timeout=step.timeout,
                retries=step.retries if isinstance(step.retries, int) else 0,
                barrier_timeout=step.barrier_timeout,
                has_error_handler=step.on_error is not None,
                targets=unique_targets,
                kind=step.get_kind(),
            )
