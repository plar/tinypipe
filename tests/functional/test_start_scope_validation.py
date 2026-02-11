from __future__ import annotations

from typing import Any

import pytest

from justpipe import (
    DefinitionError,
    EventType,
    Pipe,
    PipelineValidationWarning,
)


@pytest.mark.asyncio
async def test_start_scope_missing_all_barrier_parent_strict_errors() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(strict=True)

    @pipe.step("sentry", to="judge")
    async def sentry(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("sentry")

    @pipe.step("judge", to="scorer")
    async def judge(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("judge")

    @pipe.step("writer", to="scorer")
    async def writer(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("writer")

    @pipe.step("scorer")
    async def scorer(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("scorer")

    with pytest.raises(DefinitionError, match="requires ALL parents"):
        async for _ in pipe.run({}, start="sentry"):
            pass


@pytest.mark.asyncio
async def test_start_scope_missing_all_barrier_parent_non_strict_warns() -> None:
    pipe: Pipe[dict[str, Any], None] = Pipe(strict=False)

    @pipe.step("sentry", to="judge")
    async def sentry(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("sentry")

    @pipe.step("judge", to="scorer")
    async def judge(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("judge")

    @pipe.step("writer", to="scorer")
    async def writer(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("writer")

    @pipe.step("scorer")
    async def scorer(state: dict[str, Any]) -> None:
        state.setdefault("trace", []).append("scorer")

    state: dict[str, Any] = {"trace": []}

    with pytest.warns(
        PipelineValidationWarning,
        match=r"cannot reach parent\(s\): writer",
    ):
        events = [event async for event in pipe.run(state, start="sentry")]

    assert "scorer" not in state["trace"]
    assert events[-1].type == EventType.FINISH
