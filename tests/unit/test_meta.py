"""Unit tests for Meta implementations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from justpipe.types import DefinitionError, Meta
from justpipe._internal.runtime.meta import (
    _MetaImpl,
    _PipelineMetaImpl,
    _ScopedMeta,
    _StepMetaImpl,
    _current_step_var,
    detect_and_init_meta,
)


class TestScopedMeta:
    def test_set_and_get(self) -> None:
        m = _ScopedMeta()
        m.set("key", "value")
        assert m.get("key") == "value"

    def test_get_default(self) -> None:
        m = _ScopedMeta()
        assert m.get("missing") is None
        assert m.get("missing", 42) == 42

    def test_add_tag(self) -> None:
        m = _ScopedMeta()
        m.add_tag("important")
        m.add_tag("urgent")
        m.add_tag("important")  # duplicate
        assert m._tags == {"important", "urgent"}

    def test_record_metric(self) -> None:
        m = _ScopedMeta()
        m.record_metric("latency", 1.5)
        m.record_metric("latency", 2.0)
        m.record_metric("latency", 0.8)
        assert m._metrics["latency"] == [1.5, 2.0, 0.8]

    def test_increment(self) -> None:
        m = _ScopedMeta()
        m.increment("count")
        m.increment("count")
        m.increment("count", 5)
        assert m._counters["count"] == 7

    def test_increment_default_amount(self) -> None:
        m = _ScopedMeta()
        m.increment("hits")
        assert m._counters["hits"] == 1

    def test_snapshot_empty(self) -> None:
        m = _ScopedMeta()
        assert m._snapshot() == {}

    def test_snapshot_full(self) -> None:
        m = _ScopedMeta()
        m.set("key", "val")
        m.add_tag("tag1")
        m.add_tag("tag2")
        m.record_metric("lat", 1.0)
        m.increment("cnt", 3)
        snap = m._snapshot()
        assert snap == {
            "data": {"key": "val"},
            "tags": ["tag1", "tag2"],
            "metrics": {"lat": [1.0]},
            "counters": {"cnt": 3},
        }

    def test_snapshot_tags_sorted(self) -> None:
        m = _ScopedMeta()
        m.add_tag("z_tag")
        m.add_tag("a_tag")
        assert m._snapshot()["tags"] == ["a_tag", "z_tag"]


class TestStepMetaImpl:
    def test_raises_outside_step(self) -> None:
        m = _StepMetaImpl()
        with pytest.raises(RuntimeError, match="only available inside a step"):
            m.set("key", "value")

    def test_scoped_by_step_name(self) -> None:
        m = _StepMetaImpl()
        token_a = _current_step_var.set("step_a")
        try:
            m.set("x", 1)
        finally:
            _current_step_var.reset(token_a)

        token_b = _current_step_var.set("step_b")
        try:
            m.set("x", 2)
        finally:
            _current_step_var.reset(token_b)

        assert m._steps["step_a"].get("x") == 1
        assert m._steps["step_b"].get("x") == 2

    def test_lazy_creation(self) -> None:
        m = _StepMetaImpl()
        assert len(m._steps) == 0
        token = _current_step_var.set("new_step")
        try:
            m.get("anything")
        finally:
            _current_step_var.reset(token)
        assert "new_step" in m._steps

    def test_snapshot(self) -> None:
        m = _StepMetaImpl()
        token = _current_step_var.set("step_a")
        try:
            m.set("key", "val")
            m.add_tag("t")
        finally:
            _current_step_var.reset(token)

        snap = m._snapshot()
        assert "step_a" in snap
        assert snap["step_a"]["data"] == {"key": "val"}

    def test_snapshot_excludes_empty_steps(self) -> None:
        m = _StepMetaImpl()
        token = _current_step_var.set("empty_step")
        try:
            m.get("missing")  # access creates lazy step but writes nothing
        finally:
            _current_step_var.reset(token)

        snap = m._snapshot()
        assert "empty_step" not in snap

    @pytest.mark.asyncio
    async def test_parallel_isolation(self) -> None:
        """Map workers running concurrently should have isolated step meta."""
        m = _StepMetaImpl()
        results: dict[str, Any] = {}

        async def worker(step_name: str, value: int) -> None:
            token = _current_step_var.set(step_name)
            try:
                m.set("val", value)
                await asyncio.sleep(0.01)  # yield control
                results[step_name] = m.get("val")
            finally:
                _current_step_var.reset(token)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(worker("w1", 100))
            tg.create_task(worker("w2", 200))

        assert results["w1"] == 100
        assert results["w2"] == 200


class TestRunMeta:
    def test_run_uses_scoped_meta(self) -> None:
        m = _MetaImpl()
        m.run.set("key", "val")
        m.run.add_tag("t")
        m.run.record_metric("m", 1.0)
        m.run.increment("c")
        assert m.run.get("key") == "val"
        assert m.run._snapshot() == {
            "data": {"key": "val"},
            "tags": ["t"],
            "metrics": {"m": [1.0]},
            "counters": {"c": 1},
        }


class TestPipelineMetaImpl:
    def test_get(self) -> None:
        m = _PipelineMetaImpl({"version": "1.0", "env": "prod"})
        assert m.get("version") == "1.0"
        assert m.get("env") == "prod"

    def test_get_default(self) -> None:
        m = _PipelineMetaImpl({})
        assert m.get("missing") is None
        assert m.get("missing", "default") == "default"


class TestMetaImpl:
    def test_properties(self) -> None:
        m = _MetaImpl({"k": "v"})
        assert isinstance(m.step, _StepMetaImpl)
        assert isinstance(m.run, _ScopedMeta)
        assert isinstance(m.pipeline, _PipelineMetaImpl)

    def test_snapshot(self) -> None:
        m = _MetaImpl()
        m.run.set("key", "val")
        token = _current_step_var.set("s1")
        try:
            m.step.set("x", 1)
        finally:
            _current_step_var.reset(token)

        snap = m._snapshot()
        assert snap["run"]["data"] == {"key": "val"}
        assert snap["steps"]["s1"]["data"] == {"x": 1}

    def test_snapshot_empty(self) -> None:
        m = _MetaImpl()
        assert m._snapshot() == {}

    def test_pipeline_metadata_accessible(self) -> None:
        m = _MetaImpl({"env": "test"})
        assert m.pipeline.get("env") == "test"


class TestDetectAndInitMeta:
    def test_none_context(self) -> None:
        assert detect_and_init_meta(None) is None

    def test_no_meta_field(self) -> None:
        @dataclass
        class Ctx:
            val: int = 0

        ctx = Ctx()
        assert detect_and_init_meta(ctx) is None

    def test_meta_field(self) -> None:
        @dataclass
        class Ctx:
            meta: Meta = None  # type: ignore[assignment]

        ctx = Ctx()
        impl = detect_and_init_meta(ctx, {"version": "1"})
        assert impl is not None
        assert isinstance(ctx.meta, _MetaImpl)
        assert ctx.meta.pipeline.get("version") == "1"

    def test_optional_meta_field(self) -> None:
        @dataclass
        class Ctx:
            meta: Meta | None = None

        ctx = Ctx()
        impl = detect_and_init_meta(ctx)
        assert impl is not None
        assert isinstance(ctx.meta, _MetaImpl)

    def test_frozen_dataclass_raises(self) -> None:
        @dataclass(frozen=True)
        class Ctx:
            meta: Meta | None = None

        ctx = Ctx()
        with pytest.raises(DefinitionError, match="mutable context"):
            detect_and_init_meta(ctx)

    def test_multiple_meta_fields_raises(self) -> None:
        @dataclass
        class Ctx:
            meta1: Meta = None  # type: ignore[assignment]
            meta2: Meta = None  # type: ignore[assignment]

        ctx = Ctx()
        with pytest.raises(DefinitionError, match="Only one Meta field"):
            detect_and_init_meta(ctx)

    def test_plain_class(self) -> None:
        class Ctx:
            meta: Meta

        ctx = Ctx()
        impl = detect_and_init_meta(ctx, {"env": "prod"})
        assert impl is not None
        assert isinstance(ctx.meta, _MetaImpl)
        assert ctx.meta.pipeline.get("env") == "prod"

    def test_non_meta_fields_ignored(self) -> None:
        @dataclass
        class Ctx:
            name: str = "test"
            count: int = 0

        ctx = Ctx()
        assert detect_and_init_meta(ctx) is None
