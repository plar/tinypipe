from unittest.mock import AsyncMock, MagicMock

import pytest

from justpipe._internal.runtime.orchestration.event_manager import _EventManager
from justpipe.types import Event, EventType


@pytest.mark.parametrize(
    ("hook_result", "error_type", "message"),
    [
        (None, ValueError, "returned None"),
        ("nope", TypeError, "expected Event"),
    ],
)
def test_apply_hooks_rejects_invalid_hook_result(
    hook_result: Event | None | str,
    error_type: type[Exception],
    message: str,
) -> None:
    def bad_hook(event: Event) -> Event | None | str:
        _ = event
        return hook_result

    manager = _EventManager(event_hooks=[bad_hook])  # type: ignore[list-item]
    with pytest.raises(error_type, match=message):
        manager.apply_hooks(Event(EventType.START, "system"))


@pytest.mark.parametrize(
    ("hook_name", "method_name", "expected_message"),
    [
        ("on_pipeline_end", "notify_end", "Observer MagicMock.on_pipeline_end error"),
        (
            "on_pipeline_error",
            "notify_error",
            "Observer MagicMock.on_pipeline_error error",
        ),
    ],
)
@pytest.mark.asyncio
async def test_notify_logs_observer_errors(
    hook_name: str,
    method_name: str,
    expected_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = MagicMock()
    setattr(observer, hook_name, AsyncMock(side_effect=RuntimeError("boom")))

    manager = _EventManager(observers=[observer], pipe_name="TestPipe")
    if method_name == "notify_end":
        await manager.notify_end(state={}, duration=0.1)
    else:
        await manager.notify_error(RuntimeError("pipeline failed"), state={})

    assert f"{expected_message}: boom" in caplog.text
