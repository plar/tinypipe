from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, TYPE_CHECKING
from collections.abc import Callable

from justpipe._internal.runtime.orchestration.event_manager import _EventManager
from justpipe._internal.graph.dependency_graph import _DependencyGraph
from justpipe._internal.runtime.execution.step_invoker import _StepInvoker
from justpipe._internal.runtime.orchestration.lifecycle_manager import _LifecycleManager
from justpipe._internal.graph.execution_plan import (
    ExecutionPlan,
    compile_execution_plan,
)
from justpipe._internal.runtime.orchestration.runtime_kernel import _RuntimeKernel
from justpipe._internal.shared.execution_tracker import _ExecutionTracker
from justpipe._internal.types import HookSpec, InjectionMetadataMap
from justpipe.types import (
    CancellationToken,
    Event,
    FailureClassificationConfig,
)

if TYPE_CHECKING:
    from justpipe._internal.runtime.engine.pipeline_runner import _PipelineRunner
    from justpipe._internal.definition.steps import _BaseStep

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


@dataclass(frozen=True, slots=True)
class RunnerConfig(Generic[StateT, ContextT]):
    steps: dict[str, _BaseStep]
    topology: dict[str, list[str]]
    injection_metadata: InjectionMetadataMap
    startup_hooks: list[HookSpec]
    shutdown_hooks: list[HookSpec]
    on_error: HookSpec | None = None
    queue_size: int = 0
    event_hooks: list[Callable[[Event], Event]] | None = None
    observers: list[Any] | None = None
    pipe_name: str = "Pipe"
    cancellation_token: CancellationToken | None = None
    failure_classification: FailureClassificationConfig | None = None


@dataclass(slots=True)
class RunnerDeps(Generic[StateT, ContextT]):
    tracker: _ExecutionTracker
    events: _EventManager
    lifecycle: _LifecycleManager
    invoker: _StepInvoker[StateT, ContextT]
    graph: _DependencyGraph
    kernel: _RuntimeKernel
    queue: asyncio.Queue[Any]
    plan: ExecutionPlan


def build_runner_deps(
    config: RunnerConfig[StateT, ContextT],
) -> RunnerDeps[StateT, ContextT]:
    """Compose runner collaborators in one place."""
    tracker = _ExecutionTracker()
    events = _EventManager(config.event_hooks, config.observers, config.pipe_name)
    lifecycle = _LifecycleManager(
        config.startup_hooks,
        config.shutdown_hooks,
        config.cancellation_token,
    )
    invoker = _StepInvoker[StateT, ContextT](
        config.steps,
        config.injection_metadata,
        config.on_error,
        config.cancellation_token,
    )
    # Build plan and runtime graph in one pass.
    plan, graph = compile_execution_plan(
        config.steps,
        config.topology,
        config.injection_metadata,
    )
    queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=config.queue_size)
    kernel = _RuntimeKernel(tracker, queue)

    return RunnerDeps(
        tracker=tracker,
        events=events,
        lifecycle=lifecycle,
        invoker=invoker,
        graph=graph,
        kernel=kernel,
        queue=queue,
        plan=plan,
    )


def build_runner(
    config: RunnerConfig[StateT, ContextT],
) -> "_PipelineRunner[StateT, ContextT]":
    """Create a fully wired runner from config."""
    from justpipe._internal.runtime.engine.pipeline_runner import _PipelineRunner

    return _PipelineRunner(config)
