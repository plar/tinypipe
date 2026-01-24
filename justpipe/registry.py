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
    DefinitionError,
    Event,
    HookSpec,
    Stop,
    StepInfo,
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
        self.startup_hooks: List[HookSpec] = []
        self.shutdown_hooks: List[HookSpec] = []
        self.error_hook: Optional[HookSpec] = None
        self.injection_metadata: Dict[str, Dict[str, str]] = {}
        self.event_hooks: List[Callable[[Event], Event]] = []

    def add_middleware(self, mw: Middleware) -> None:
        self.middleware.append(mw)

    def add_event_hook(self, hook: Callable[[Event], Event]) -> None:
        self.event_hooks.append(hook)

    def on_startup(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.startup_hooks.append(
            HookSpec(
                func=func,
                injection_metadata=_analyze_signature(
                    func, self.state_type, self.context_type, expected_unknowns=0
                ),
            )
        )
        return func

    def on_shutdown(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.shutdown_hooks.append(
            HookSpec(
                func=func,
                injection_metadata=_analyze_signature(
                    func, self.state_type, self.context_type, expected_unknowns=0
                ),
            )
        )
        return func

    def on_error(self, func: Callable[..., Any]) -> Callable[..., Any]:
        self.error_hook = HookSpec(
            func=func,
            injection_metadata=_analyze_signature(
                func, self.state_type, self.context_type, expected_unknowns=0
            ),
        )
        return func

    def finalize(self) -> None:
        """Apply middleware to all steps. Called before run to ensure all middleware is applied."""
        for step in self.steps.values():
            if step._wrapped_func is None:
                step.wrap_middleware(self.middleware)

    def _pop_common_step_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> tuple[Optional[float], Union[int, Dict[str, Any]]]:
        timeout = kwargs.pop("timeout", None)
        retries = kwargs.pop("retries", 0)
        return timeout, retries

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
        if stage_name in self.steps:
            raise DefinitionError(f"Step '{stage_name}' is already registered")
        self.steps[stage_name] = step_obj

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

            timeout, retries = self._pop_common_step_kwargs(kwargs)

            step_obj = _StandardStep(
                name=stage_name,
                func=func,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])]
                if to
                else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs,
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

            timeout, retries = self._pop_common_step_kwargs(kwargs)

            step_obj = _MapStep(
                name=stage_name,
                func=func,
                map_target=target_name,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])]
                if to
                else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs,
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
                        Stop if isinstance(target, _Stop) else _resolve_name(target)
                    )

            timeout, retries = self._pop_common_step_kwargs(kwargs)

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
                extra=kwargs,
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

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            timeout, retries = self._pop_common_step_kwargs(kwargs)

            step_obj = _SubPipelineStep(
                name=stage_name,
                func=func,
                sub_pipeline_name=using.name if hasattr(using, "name") else "SubPipe",
                sub_pipeline_obj=using,
                to=[_resolve_name(t) for t in (to if isinstance(to, list) else [to])]
                if to
                else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=kwargs,
            )

            self._register_step(step_obj, to, on_error)
            return func

        return decorator

    def get_steps_info(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        for name, step in self.steps.items():
            targets = list(self.topology.get(name, []))
            targets.extend(step.get_targets())

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
