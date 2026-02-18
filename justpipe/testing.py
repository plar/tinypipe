from dataclasses import dataclass
from typing import Any, TypeVar, Generic, cast
from collections.abc import Callable
from unittest.mock import AsyncMock

from justpipe.pipe import Pipe
from justpipe.types import Event, EventType, InjectionMetadata

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


@dataclass
class TestResult(Generic[StateT]):
    """Container for pipeline execution results and events."""

    events: list[Event]
    final_state: StateT

    def filter(self, event_type: EventType) -> list[Event]:
        """Filter events by type."""
        return [e for e in self.events if e.type == event_type]

    @property
    def step_starts(self) -> list[str]:
        """Names of steps that started."""
        return [e.stage for e in self.events if e.type == EventType.STEP_START]

    @property
    def tokens(self) -> list[Any]:
        """All data tokens yielded by steps (EventType.TOKEN)."""
        return [e.payload for e in self.events if e.type == EventType.TOKEN]

    def was_called(self, stage: str) -> bool:
        """Check if a specific step or hook was executed."""
        return any(e.stage == stage for e in self.events)

    def find_error(self, stage: str | None = None) -> str | None:
        """Find error message for a specific stage or the first error found."""
        for e in self.events:
            if e.type == EventType.STEP_ERROR:
                if stage is None or e.stage == stage:
                    return str(e.payload)
        return None


class TestPipe(Generic[StateT, ContextT]):
    """
    A testing harness for justpipe pipelines.
    Allows mocking steps, capturing events, and performing assertions.
    """

    __test__ = False

    def __init__(self, pipe: Pipe[StateT, ContextT]):
        self.pipe = pipe
        self._mocks: dict[str, AsyncMock] = {}
        # We store (_original_func, original_wrapped, original_metadata)
        self._originals: dict[
            str,
            tuple[
                Callable[..., Any],
                Callable[..., Any] | None,
                InjectionMetadata,
            ],
        ] = {}
        self._original_startup: list[
            tuple[int, Callable[..., Any], InjectionMetadata]
        ] = []
        self._original_error_hook: (
            tuple[Callable[..., Any], InjectionMetadata] | None
        ) = None

    def mock(
        self, step_name: str, return_value: Any = None, side_effect: Any = None
    ) -> AsyncMock:
        """
        Mock a step by name.
        Returns an AsyncMock that will be called instead of the original step.
        """
        if step_name not in self.pipe.registry.steps:
            available = ", ".join(self.pipe.registry.steps.keys())
            raise ValueError(f"Step '{step_name}' not found. Available: {available}")

        # Create the mock
        m = AsyncMock(return_value=return_value, side_effect=side_effect)
        self._mocks[step_name] = m

        # Store original if not already stored
        step_obj = self.pipe.registry.steps[step_name]
        if step_name not in self._originals:
            self._originals[step_name] = (
                step_obj._original_func,
                step_obj._wrapped_func,
                self.pipe.registry.injection_metadata.get(step_name, {}).copy(),
            )

        # We need a wrapper that matches the signature expectations of justpipe
        # but calls our mock with the right arguments.
        async def mock_wrapper(**kwargs: Any) -> Any:
            return await m(**kwargs)

        # Update step object and metadata
        step_obj._original_func = mock_wrapper
        step_obj._wrapped_func = None  # Force re-wrap during finalize()

        return m

    def mock_startup(
        self, return_value: Any = None, side_effect: Any = None
    ) -> AsyncMock:
        """Mock all startup hooks with a single mock."""
        m = AsyncMock(return_value=return_value, side_effect=side_effect)

        if not self._original_startup:
            for idx, hook in enumerate(self.pipe.registry.startup_hooks):
                self._original_startup.append((idx, hook.func, hook.injection_metadata))

        # Replace functions in hooks
        for hook in self.pipe.registry.startup_hooks:

            async def hook_wrapper(**kwargs: Any) -> Any:
                return await m(**kwargs)

            hook.func = hook_wrapper

        return m

    def mock_on_error(
        self, return_value: Any = None, side_effect: Any = None
    ) -> AsyncMock:
        """Mock the global error handler."""
        if not self.pipe.registry.error_hook:
            raise ValueError("No global error hook registered on this pipeline.")

        m = AsyncMock(return_value=return_value, side_effect=side_effect)

        if not self._original_error_hook:
            hook = self.pipe.registry.error_hook
            self._original_error_hook = (hook.func, hook.injection_metadata)

        async def error_wrapper(**kwargs: Any) -> Any:
            return await m(**kwargs)

        self.pipe.registry.error_hook.func = error_wrapper
        return m

    async def run(
        self, state: StateT, context: ContextT | None = None, **kwargs: Any
    ) -> TestResult[StateT]:
        """Run the pipeline and collect all events and final state."""
        events = []
        # Track state from stream events instead of returning the initial reference.
        # This keeps final_state accurate if the runtime swaps state objects.
        last_state = state
        root_steps = set(self.pipe.registry.steps)

        # Collect all events from the stream
        async for event in self.pipe.run(state, context, **kwargs):
            events.append(event)
            if event.type == EventType.START:
                last_state = cast(StateT, event.payload)
            elif event.type == EventType.STEP_END and event.stage in root_steps:
                last_state = cast(StateT, event.payload)

        return TestResult(events=events, final_state=last_state)

    def __enter__(self) -> "TestPipe[StateT, ContextT]":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.restore()

    def restore(self) -> None:
        """Restore all mocked steps and hooks to their original state."""
        # Restore steps
        for name, (orig_func, orig_wrapped, orig_meta) in self._originals.items():
            step_obj = self.pipe.registry.steps[name]
            step_obj._original_func = orig_func
            step_obj._wrapped_func = orig_wrapped
            self.pipe.registry.injection_metadata[name] = orig_meta

        # Restore startup hooks
        for idx, orig_func, orig_meta in self._original_startup:
            self.pipe.registry.startup_hooks[idx].func = orig_func
            self.pipe.registry.startup_hooks[idx].injection_metadata = orig_meta

        # Restore error hook
        if self._original_error_hook:
            hook = self.pipe.registry.error_hook
            if hook:
                hook.func, hook.injection_metadata = self._original_error_hook

        self._mocks.clear()
        self._originals.clear()
        self._original_startup.clear()
        self._original_error_hook = None
