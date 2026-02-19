from typing import (
    Any,
)
from collections.abc import Callable, Iterator

from justpipe.types import (
    BarrierType,
    DefinitionError,
    InjectionMetadataMap,
    Stop,
    StepInfo,
)
from justpipe._internal.shared.utils import _resolve_name
from justpipe._internal.definition.steps import (
    _StandardStep,
    _MapStep,
    _SwitchStep,
    _BaseStep,
    _SubPipelineStep,
)
from justpipe._internal.definition.type_resolver import _TypeResolver
from justpipe._internal.definition.registry_validator import _RegistryValidator


LinearTo = str | list[str] | Callable[..., Any] | list[Callable[..., Any]] | None
StepDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


class _StepRegistry:
    """Owns step registration data and routing topology.

    This class is the source of truth for:
    - Registered step objects (`steps`)
    - Graph edges (`topology`)
    - Injection metadata (`injection_metadata`)
    """

    def __init__(
        self,
        pipe_name: str,
        state_type: Any,
        context_type: Any,
        resolver: _TypeResolver,
        validator: _RegistryValidator,
        max_map_items: int | None = None,
    ):
        self.pipe_name = pipe_name
        self.state_type = state_type
        self.context_type = context_type
        self._resolver = resolver
        self._validator = validator
        self.max_map_items = max_map_items

        self.steps: dict[str, _BaseStep] = {}
        self.topology: dict[str, list[str]] = {}
        self.injection_metadata: InjectionMetadataMap = {}
        self._pending_validations: list[dict[str, Any]] = []
        self._frozen = False

    def freeze(self) -> None:
        self._frozen = True

    def _assert_mutable(self, action: str) -> None:
        if self._frozen:
            raise RuntimeError(
                f"Pipeline definition is frozen after first run; cannot {action}."
            )

    def _pop_common_step_kwargs(
        self, kwargs: dict[str, Any]
    ) -> tuple[float | None, int | dict[str, Any]]:
        timeout = kwargs.pop("timeout", None)
        retries = kwargs.pop("retries", 0)
        return timeout, retries

    def _normalize_linear_targets(self, to: LinearTo) -> list[str] | None:
        if not to:
            return None
        return [_resolve_name(t) for t in (to if isinstance(to, list) else [to])]

    def _build_linear_decorator(
        self,
        *,
        name: str | Callable[..., Any] | None,
        to: LinearTo,
        on_error: Callable[..., Any] | None,
        kwargs: dict[str, Any],
        build_step: Callable[..., _BaseStep],
        pre_validate: Callable[[str], None] | None = None,
    ) -> StepDecorator:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)
            if pre_validate:
                pre_validate(stage_name)
            self._validator.validate_linear_to(stage_name, to)

            step_kwargs = kwargs.copy()
            timeout, retries = self._pop_common_step_kwargs(step_kwargs)
            normalized_to = self._normalize_linear_targets(to)

            step_obj = build_step(
                stage_name,
                func,
                normalized_to,
                timeout,
                retries,
                step_kwargs,
            )

            self._register_step(step_obj, normalized_to, on_error)
            return func

        return decorator

    def _register_step(
        self,
        step_obj: _BaseStep,
        targets: list[str] | None = None,
        on_error: Callable[..., Any] | None = None,
        expected_unknowns: int = 1,
    ) -> str:
        self._assert_mutable("register new steps")
        stage_name = step_obj.name
        if stage_name in self.steps:
            existing_step = self.steps[stage_name]
            error_msg = (
                f"Step '{stage_name}' is already registered. "
                f"Each step name must be unique within a pipeline. "
            )

            if hasattr(existing_step, "_original_func") and hasattr(
                step_obj, "_original_func"
            ):
                existing_func = existing_step._original_func.__name__
                new_func = step_obj._original_func.__name__
                if existing_func != new_func:
                    error_msg += (
                        f"Previously registered by function '{existing_func}', "
                        f"now attempting to register with '{new_func}'. "
                    )

            error_msg += (
                "Either rename one of the steps using @pipe.step('unique_name') "
                "or remove the duplicate decorator."
            )
            raise DefinitionError(error_msg)
        self.steps[stage_name] = step_obj

        self.injection_metadata[stage_name] = self._resolver.analyze_signature(
            step_obj._original_func,
            self.state_type,
            self.context_type,
            expected_unknowns=expected_unknowns,
        )

        if on_error:
            self.injection_metadata[f"{stage_name}:on_error"] = (
                self._resolver.analyze_signature(
                    on_error,
                    self.state_type,
                    self.context_type,
                    expected_unknowns=0,
                )
            )

        if targets:
            self.topology[stage_name] = targets

        return stage_name

    def step(
        self,
        name: str | Callable[..., Any] | None = None,
        to: LinearTo = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        self._assert_mutable("register steps")

        def build_step(
            stage_name: str,
            func: Callable[..., Any],
            normalized_to: list[str] | None,
            timeout: float | None,
            retries: int | dict[str, Any],
            extra: dict[str, Any],
        ) -> _BaseStep:
            return _StandardStep(
                name=stage_name,
                func=func,
                to=normalized_to,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                barrier_type=barrier_type,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=extra,
            )

        decorator = self._build_linear_decorator(
            name=name,
            to=to,
            on_error=on_error,
            kwargs=kwargs,
            build_step=build_step,
        )
        if callable(name) and to is None and not kwargs:
            return decorator(name)
        return decorator

    def map(
        self,
        name: str | Callable[..., Any] | None = None,
        each: str | Callable[..., Any] | None = None,
        to: LinearTo = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        max_concurrency: int | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        self._assert_mutable("register map steps")

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            if each is None:
                raise DefinitionError(
                    f"Step '{stage_name}' (map) requires 'each' parameter"
                )

            self._validator.validate_routing_target_type(each, stage_name)
            target_name = _resolve_name(each)
            self._validator.validate_linear_to(stage_name, to)

            map_kwargs = kwargs.copy()
            timeout, retries = self._pop_common_step_kwargs(map_kwargs)
            normalized_to = self._normalize_linear_targets(to)

            step_obj = _MapStep(
                name=stage_name,
                func=func,
                each=target_name,
                to=normalized_to,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                barrier_type=barrier_type,
                on_error=on_error,
                pipe_name=self.pipe_name,
                max_concurrency=max_concurrency,
                max_map_items=self.max_map_items,
                extra=map_kwargs,
            )

            self._register_step(step_obj, normalized_to, on_error)
            return func

        return decorator

    def switch(
        self,
        name: str | Callable[..., Any] | None = None,
        to: dict[Any, str | Callable[..., Any] | type[Stop]]
        | Callable[[Any], str | type[Stop]]
        | None = None,
        default: str | Callable[..., Any] | None = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        self._assert_mutable("register switch steps")

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            stage_name = _resolve_name(name or func)

            if to is None:
                raise DefinitionError(
                    f"Step '{stage_name}' (switch) requires a 'to' parameter (dict or callable)"
                )

            if not isinstance(to, (dict, type(lambda: None))) and not callable(to):
                raise DefinitionError(
                    f"Step '{stage_name}' is a switch but 'to' is {type(to).__name__}. "
                    "The 'to' parameter in @pipe.switch must be a dictionary (routing table) "
                    "or a callable (dynamic router)."
                )

            self._validator.validate_routing_target_type(to, stage_name)
            if default:
                self._validator.validate_routing_target_type(default, stage_name)

            normalized_routes = {}
            if isinstance(to, dict):
                for key, target in to.items():
                    normalized_routes[key] = (
                        Stop if target is Stop else _resolve_name(target)
                    )

            switch_kwargs = kwargs.copy()
            timeout, retries = self._pop_common_step_kwargs(switch_kwargs)

            step_obj = _SwitchStep(
                name=stage_name,
                func=func,
                to=normalized_routes if isinstance(to, dict) else to,
                default=_resolve_name(default) if default else None,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                barrier_type=barrier_type,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=switch_kwargs,
            )

            if isinstance(to, dict):
                targets = set()
                for target in normalized_routes.values():
                    if target is not Stop:
                        targets.add(target)
                if default:
                    targets.add(_resolve_name(default))

                self._pending_validations.append(
                    {
                        "type": "switch_routes",
                        "switch_name": stage_name,
                        "targets": targets,
                    }
                )

            self._register_step(step_obj, None, on_error)
            return func

        return decorator

    def sub(
        self,
        name: str | Callable[..., Any] | None = None,
        pipeline: Any = None,
        to: LinearTo = None,
        barrier_timeout: float | None = None,
        barrier_type: BarrierType | None = None,
        on_error: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        self._assert_mutable("register sub-pipeline steps")

        def pre_validate(stage_name: str) -> None:
            if pipeline is None:
                raise DefinitionError(
                    f"Step '{stage_name}' (sub) requires 'pipeline' parameter"
                )

        def build_step(
            stage_name: str,
            func: Callable[..., Any],
            normalized_to: list[str] | None,
            timeout: float | None,
            retries: int | dict[str, Any],
            extra: dict[str, Any],
        ) -> _BaseStep:
            return _SubPipelineStep(
                name=stage_name,
                func=func,
                pipeline=pipeline,
                to=normalized_to,
                timeout=timeout,
                retries=retries,
                barrier_timeout=barrier_timeout,
                barrier_type=barrier_type,
                on_error=on_error,
                pipe_name=self.pipe_name,
                extra=extra,
            )

        return self._build_linear_decorator(
            name=name,
            to=to,
            on_error=on_error,
            kwargs=kwargs,
            build_step=build_step,
            pre_validate=pre_validate,
        )

    def validate_all(self) -> None:
        """Validate all pending checks after registration complete."""
        for validation in self._pending_validations:
            if validation["type"] == "switch_routes":
                self._validator.validate_switch_routes(validation, self.steps.keys())
        self._pending_validations.clear()

    def get_steps_info(self) -> Iterator[StepInfo]:
        """Iterate over registered steps with their configuration."""
        for name, step in self.steps.items():
            targets = list(self.topology.get(name, []))
            targets.extend(step.get_targets())

            unique_targets = sorted(list(set(targets)))

            yield StepInfo(
                name=name,
                timeout=step.timeout,
                retries=step.retries,
                barrier_timeout=step.barrier_timeout,
                has_error_handler=step.on_error is not None,
                targets=unique_targets,
                kind=step.get_kind(),
            )
