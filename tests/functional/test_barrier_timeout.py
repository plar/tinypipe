import asyncio
import pytest
from typing import Any, Dict, List
from justpipe import Pipe, EventType


@pytest.mark.asyncio
async def test_barrier_timeout_success() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    @pipe.step(to="combine")
    async def step_a(state: Dict[str, Any]) -> None:
        await asyncio.sleep(0.01)

    @pipe.step(to="combine")
    async def step_b(state: Dict[str, Any]) -> None:
        await asyncio.sleep(0.02)

    @pipe.step(barrier_timeout=0.1)
    async def combine(state: Dict[str, Any]) -> None:
        state["done"] = True

    state: Dict[str, Any] = {}
    async for ev in pipe.run(state):
        pass

    assert state.get("done") is True


@pytest.mark.asyncio
async def test_barrier_timeout_failure() -> None:
    pipe: Pipe[Dict[str, Any], None] = Pipe()

    @pipe.step(to="combine")
    async def step_a(state: Dict[str, Any]) -> None:
        await asyncio.sleep(0.01)

    @pipe.step(to="combine")
    async def step_b(state: Dict[str, Any]) -> None:
        # This one will take too long!
        await asyncio.sleep(0.5)

    @pipe.step(barrier_timeout=0.1)
    async def combine(state: Dict[str, Any]) -> None:
        state["done"] = True

    state: Dict[str, Any] = {}
    errors: List[Any] = []
    async for ev in pipe.run(state):
        if ev.type == EventType.ERROR:
            errors.append(ev)

    assert len(errors) >= 1
    assert "Barrier timeout" in str(errors[0].data)
    assert state.get("done") is None