from typing import Any

import pytest

from justpipe import DefinitionError, EventType, Pipe
from justpipe.observability import Observer


@pytest.mark.asyncio
async def test_definition_mutation_is_blocked_after_first_run() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start")
    async def start() -> None:
        pass

    events = [event async for event in pipe.run({})]
    assert events[-1].type is EventType.FINISH

    with pytest.raises(RuntimeError, match="frozen after first run"):
        pipe.add_event_hook(lambda event: event)

    with pytest.raises(RuntimeError, match="frozen after first run"):

        @pipe.step("late")
        async def late() -> None:
            pass

    with pytest.raises(RuntimeError, match="frozen after first run"):

        @pipe.on_startup
        async def startup() -> None:
            pass

    class _NoopObserver(Observer):
        async def on_event(
            self, state: Any, context: Any, meta: Any, event: Any
        ) -> None:
            _ = (state, context, meta, event)

    with pytest.raises(RuntimeError, match="frozen after first run"):
        pipe.add_observer(_NoopObserver())


@pytest.mark.asyncio
async def test_registry_mutation_is_blocked_after_first_run() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start")
    async def start() -> None:
        pass

    _ = [event async for event in pipe.run({})]

    with pytest.raises(RuntimeError, match="frozen after first run"):
        pipe.registry.add_middleware(lambda func, ctx: func)


@pytest.mark.asyncio
async def test_read_only_introspection_still_works_after_freeze() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start")
    async def start() -> None:
        pass

    _ = [event async for event in pipe.run({})]

    assert "start" in {step.name for step in pipe.steps()}
    assert isinstance(pipe.topology, dict)
    assert isinstance(pipe.graph(), str)


@pytest.mark.asyncio
async def test_validation_failure_does_not_freeze_definition() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to="missing")
    async def start() -> None:
        pass

    with pytest.raises(DefinitionError):
        _ = [event async for event in pipe.run({})]

    @pipe.step("missing")
    async def missing() -> None:
        pass

    events = [event async for event in pipe.run({})]
    assert events[-1].type is EventType.FINISH
