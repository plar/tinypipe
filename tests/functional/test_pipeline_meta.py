"""Functional tests for Meta integration with pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from justpipe import EventType, Meta, Pipe, PipelineEndData


@dataclass
class MetaContext:
    meta: Meta | None = None


@dataclass
class PlainContext:
    val: int = 0


class TestMetaStepScope:
    @pytest.mark.asyncio
    async def test_step_meta_in_finish_snapshot(self) -> None:
        pipe: Pipe[None, MetaContext] = Pipe(context_type=MetaContext, name="test")

        @pipe.step()
        async def my_step(state: None, ctx: MetaContext) -> None:
            ctx.meta.step.set("model", "gpt-4")  # type: ignore[union-attr]
            ctx.meta.step.add_tag("llm")  # type: ignore[union-attr]
            ctx.meta.step.record_metric("latency", 1.5)  # type: ignore[union-attr]
            ctx.meta.step.increment("tokens", 150)  # type: ignore[union-attr]

        ctx = MetaContext()
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is not None
        steps = end_data.user_meta["steps"]
        assert "my_step" in steps
        step_meta = steps["my_step"]
        assert step_meta["data"]["model"] == "gpt-4"
        assert "llm" in step_meta["tags"]
        assert step_meta["metrics"]["latency"] == [1.5]
        assert step_meta["counters"]["tokens"] == 150


class TestMetaRunScope:
    @pytest.mark.asyncio
    async def test_run_meta_in_finish_snapshot(self) -> None:
        pipe: Pipe[None, MetaContext] = Pipe(context_type=MetaContext, name="test")

        @pipe.step(to="step_b")
        async def step_a(state: None, ctx: MetaContext) -> None:
            ctx.meta.run.set("started_by", "step_a")  # type: ignore[union-attr]
            ctx.meta.run.increment("total_items", 5)  # type: ignore[union-attr]

        @pipe.step()
        async def step_b(state: None, ctx: MetaContext) -> None:
            ctx.meta.run.increment("total_items", 3)  # type: ignore[union-attr]

        ctx = MetaContext()
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is not None
        run_meta = end_data.user_meta["run"]
        assert run_meta["data"]["started_by"] == "step_a"
        assert run_meta["counters"]["total_items"] == 8


class TestMetaPipelineScope:
    @pytest.mark.asyncio
    async def test_pipeline_metadata_readable(self) -> None:
        pipe: Pipe[None, MetaContext] = Pipe(
            context_type=MetaContext,
            name="test",
            metadata={"version": "1.0", "env": "test"},
        )
        captured: dict[str, Any] = {}

        @pipe.step()
        async def my_step(state: None, ctx: MetaContext) -> None:
            captured["version"] = ctx.meta.pipeline.get("version")  # type: ignore[union-attr]
            captured["env"] = ctx.meta.pipeline.get("env")  # type: ignore[union-attr]
            captured["missing"] = ctx.meta.pipeline.get("missing", "default")  # type: ignore[union-attr]

        ctx = MetaContext()
        async for _ in pipe.run(None, ctx):
            pass

        assert captured["version"] == "1.0"
        assert captured["env"] == "test"
        assert captured["missing"] == "default"


class TestMetaParallelIsolation:
    @pytest.mark.asyncio
    async def test_step_meta_isolated_per_step(self) -> None:
        pipe: Pipe[None, MetaContext] = Pipe(
            context_type=MetaContext,
            name="test",
            allow_multi_root=True,
        )

        @pipe.step()
        async def step_a(state: None, ctx: MetaContext) -> None:
            ctx.meta.step.set("source", "a")  # type: ignore[union-attr]

        @pipe.step()
        async def step_b(state: None, ctx: MetaContext) -> None:
            ctx.meta.step.set("source", "b")  # type: ignore[union-attr]

        ctx = MetaContext()
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is not None
        steps = end_data.user_meta["steps"]
        assert steps["step_a"]["data"]["source"] == "a"
        assert steps["step_b"]["data"]["source"] == "b"


class TestNoMetaUnchanged:
    @pytest.mark.asyncio
    async def test_pipeline_without_meta_runs_normally(self) -> None:
        pipe: Pipe[None, PlainContext] = Pipe(context_type=PlainContext, name="test")

        @pipe.step()
        async def my_step(state: None, ctx: PlainContext) -> None:
            ctx.val = 42

        ctx = PlainContext()
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is None
        assert ctx.val == 42

    @pytest.mark.asyncio
    async def test_pipeline_no_context(self) -> None:
        pipe: Pipe[None, None] = Pipe(name="test")

        @pipe.step()
        async def my_step(state: None) -> None:
            pass

        end_data: PipelineEndData | None = None
        async for event in pipe.run(None):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is None


class TestMetaEmptySnapshot:
    @pytest.mark.asyncio
    async def test_meta_unused_returns_none(self) -> None:
        """If Meta is declared but never written to, user_meta should be None."""
        pipe: Pipe[None, MetaContext] = Pipe(context_type=MetaContext, name="test")

        @pipe.step()
        async def my_step(state: None, ctx: MetaContext) -> None:
            pass  # No meta writes

        ctx = MetaContext()
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.FINISH:
                end_data = event.payload

        assert end_data is not None
        assert end_data.user_meta is None
