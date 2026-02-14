"""Functional tests for Meta integration with pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from justpipe import EventType, Meta, Pipe, PipelineEndData
from justpipe.types import Event


@dataclass
class MetaContext:
    meta: Meta | None = None


@dataclass
class PlainContext:
    val: int = 0


class TestMetaStepScope:
    @pytest.mark.asyncio
    async def test_step_meta_on_step_end_event(self) -> None:
        """Step meta is attached to STEP_END Event.meta (not FINISH)."""
        pipe: Pipe[None, MetaContext] = Pipe(context_type=MetaContext, name="test")

        @pipe.step()
        async def my_step(state: None, ctx: MetaContext) -> None:
            ctx.meta.step.set("model", "gpt-4")  # type: ignore[union-attr]
            ctx.meta.step.add_tag("llm")  # type: ignore[union-attr]
            ctx.meta.step.record_metric("latency", 1.5)  # type: ignore[union-attr]
            ctx.meta.step.increment("tokens", 150)  # type: ignore[union-attr]

        ctx = MetaContext()
        step_end_events: list[Event] = []
        end_data: PipelineEndData | None = None
        async for event in pipe.run(None, ctx):
            if event.type == EventType.STEP_END and event.stage == "my_step":
                step_end_events.append(event)
            if event.type == EventType.FINISH:
                end_data = event.payload

        # Step meta should be on the STEP_END event
        assert len(step_end_events) == 1
        meta = step_end_events[0].meta
        assert meta is not None
        assert meta["data"]["model"] == "gpt-4"
        assert "llm" in meta["tags"]
        assert meta["metrics"]["latency"] == [1.5]
        assert meta["counters"]["tokens"] == 150

        # FINISH event should NOT contain step data
        assert end_data is not None
        assert end_data.run_meta is None  # No run-scope writes


class TestMetaRunScope:
    @pytest.mark.asyncio
    async def test_run_meta_in_finish_event(self) -> None:
        """Run-scope meta appears in FINISH event as run_meta."""
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
        assert end_data.run_meta is not None
        assert end_data.run_meta["data"]["started_by"] == "step_a"
        assert end_data.run_meta["counters"]["total_items"] == 8


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
    async def test_each_step_end_carries_own_meta(self) -> None:
        """Parallel steps each get their own step meta on their STEP_END events."""
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
        step_end_meta: dict[str, dict[str, Any] | None] = {}
        async for event in pipe.run(None, ctx):
            if event.type == EventType.STEP_END and event.stage in ("step_a", "step_b"):
                step_end_meta[event.stage] = event.meta

        assert "step_a" in step_end_meta
        assert "step_b" in step_end_meta
        assert step_end_meta["step_a"] is not None
        assert step_end_meta["step_b"] is not None
        assert step_end_meta["step_a"]["data"]["source"] == "a"
        assert step_end_meta["step_b"]["data"]["source"] == "b"


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
        assert end_data.run_meta is None
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
        assert end_data.run_meta is None


class TestMetaEmptySnapshot:
    @pytest.mark.asyncio
    async def test_meta_unused_returns_none(self) -> None:
        """If Meta is declared but never written to, run_meta should be None."""
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
        assert end_data.run_meta is None


class TestStepMetaOnError:
    @pytest.mark.asyncio
    async def test_step_error_carries_partial_meta(self) -> None:
        """STEP_ERROR events carry partial meta from before the failure."""
        pipe: Pipe[None, MetaContext] = Pipe(context_type=MetaContext, name="test")

        @pipe.step()
        async def my_step(state: None, ctx: MetaContext) -> None:
            ctx.meta.step.set("started", True)  # type: ignore[union-attr]
            ctx.meta.step.increment("processed", 3)  # type: ignore[union-attr]
            raise ValueError("intentional error")

        ctx = MetaContext()
        step_error_events: list[Event] = []
        async for event in pipe.run(None, ctx):
            if event.type == EventType.STEP_ERROR and event.stage == "my_step":
                step_error_events.append(event)

        assert len(step_error_events) == 1
        meta = step_error_events[0].meta
        assert meta is not None
        assert meta["data"]["started"] is True
        assert meta["counters"]["processed"] == 3


class TestEventHookEnrichmentVisible:
    @pytest.mark.asyncio
    async def test_hook_enrichment_visible_to_observers(self) -> None:
        """Event hooks run before observers, so hook-enriched meta is visible."""
        pipe: Pipe[None, None] = Pipe(name="test")
        observed_events: list[Event] = []

        @pipe.step()
        async def my_step(state: None) -> None:
            pass

        def add_trace_id(event: Event) -> Event:
            if event.type == EventType.STEP_START:
                from dataclasses import replace

                new_meta = dict(event.meta) if event.meta else {}
                new_meta["trace_id"] = "abc123"
                return replace(event, meta=new_meta)
            return event

        pipe.add_event_hook(add_trace_id)

        async for event in pipe.run(None):
            observed_events.append(event)

        # Find the STEP_START event that was enriched by the hook
        step_starts = [e for e in observed_events if e.type == EventType.STEP_START]
        assert len(step_starts) >= 1
        assert step_starts[0].meta is not None
        assert step_starts[0].meta["trace_id"] == "abc123"
