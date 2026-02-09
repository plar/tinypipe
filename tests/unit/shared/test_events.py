import pytest
from unittest.mock import AsyncMock, MagicMock
from justpipe.types import Event, EventType
from justpipe._internal.runtime.orchestration.event_manager import _EventManager
from justpipe.observability import ObserverMeta


@pytest.mark.asyncio
async def test_event_manager_notify_start() -> None:
    observer = MagicMock()
    observer.on_pipeline_start = AsyncMock()

    manager = _EventManager(observers=[observer], pipe_name="TestPipe")
    context = {"ctx": 1}
    await manager.notify_start(state={"foo": "bar"}, context=context)

    observer.on_pipeline_start.assert_called_once()
    state_arg, context_arg, meta_arg = observer.on_pipeline_start.call_args.args
    assert state_arg == {"foo": "bar"}
    assert context_arg is context
    assert isinstance(meta_arg, ObserverMeta)
    assert meta_arg.pipe_name == "TestPipe"
    assert meta_arg.started_at is not None


@pytest.mark.asyncio
async def test_event_manager_notify_event() -> None:
    observer = MagicMock()
    observer.on_event = AsyncMock()

    manager = _EventManager(observers=[observer], pipe_name="TestPipe")
    context = {"ctx": 1}
    await manager.notify_start(state="state", context=context)
    event = Event(EventType.START, "system")
    await manager.notify_event(event, state="state")

    observer.on_event.assert_called_once()
    state_arg, context_arg, meta_arg, event_arg = observer.on_event.call_args.args
    assert state_arg == "state"
    assert context_arg is context
    assert isinstance(meta_arg, ObserverMeta)
    assert meta_arg.pipe_name == "TestPipe"
    assert meta_arg.started_at is not None
    assert event_arg is event


def test_event_manager_apply_hooks() -> None:
    def hook(ev: Event) -> Event:
        return Event(
            type=ev.type,
            stage="hooked",
            payload=ev.payload,
            timestamp=ev.timestamp,
        )

    manager = _EventManager(event_hooks=[hook])
    event = Event(EventType.START, "original")
    result = manager.apply_hooks(event)

    assert result.stage == "hooked"


@pytest.mark.asyncio
async def test_event_manager_observer_error_handling(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = MagicMock()
    observer.on_event = AsyncMock(side_effect=RuntimeError("Boom"))

    manager = _EventManager(observers=[observer])
    event = Event(EventType.START, "system")

    # Should not raise
    await manager.notify_event(event, state="state")

    assert "Observer MagicMock.on_event error: Boom" in caplog.text
