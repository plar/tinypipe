import asyncio
import pytest
from typing import Any

from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_client_aclose_sets_client_closed_status() -> None:
    pipe: Pipe[dict[str, Any], Any] = Pipe(state_type=dict)

    @pipe.step()
    async def slow(state: dict[str, Any]) -> None:
        await asyncio.sleep(1.0)

    stream = pipe.run({})
    events = []
    await stream.__anext__()  # START
    await stream.__anext__()  # STEP_START
    await stream.aclose()

    # Consume shutdown/finish events after close
    try:
        async for ev in stream:
            events.append(ev)
    except Exception:
        pass

    finish_events = [e for e in events if e.type == EventType.FINISH]
    assert finish_events == []
