"""Unit tests for Pipe.describe() method."""

from __future__ import annotations

from typing import Any

from justpipe import Pipe


class TestDescribe:
    def test_basic_structure(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test_pipe", metadata={"env": "test"})

        @pipe.step(to="b")
        async def a(state: None) -> None:
            pass

        @pipe.step()
        async def b(state: None) -> None:
            pass

        desc = pipe.describe()
        assert desc["name"] == "test_pipe"
        assert isinstance(desc["pipeline_hash"], str)
        assert len(desc["pipeline_hash"]) == 16
        assert "a" in desc["nodes"]
        assert "b" in desc["nodes"]
        assert desc["topology"] == {"a": ["b"]}
        assert desc["roots"] == ["a"]
        assert desc["metadata"] == {"env": "test"}

    def test_node_details(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test")

        @pipe.step(to="b", timeout=5.0, retries=3)
        async def a(state: None) -> None:
            pass

        @pipe.step()
        async def b(state: None) -> None:
            pass

        desc = pipe.describe()
        node_a = desc["nodes"]["a"]
        assert node_a["kind"] == "step"
        assert node_a["targets"] == ["b"]
        assert node_a["timeout"] == 5.0
        assert node_a["retries"] == 3

    def test_hooks_reported(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test")

        @pipe.on_startup
        async def setup(state: None) -> None:
            pass

        @pipe.on_shutdown
        async def teardown(state: None) -> None:
            pass

        @pipe.on_error
        async def handle_error(state: None) -> None:
            pass

        @pipe.step()
        async def a(state: None) -> None:
            pass

        desc = pipe.describe()
        assert desc["hooks"]["startup"] == ["setup"]
        assert desc["hooks"]["shutdown"] == ["teardown"]
        assert desc["hooks"]["on_error"] == "handle_error"

    def test_empty_metadata(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test")

        @pipe.step()
        async def a(state: None) -> None:
            pass

        desc = pipe.describe()
        assert desc["metadata"] == {}

    def test_empty_hooks(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test")

        @pipe.step()
        async def a(state: None) -> None:
            pass

        desc = pipe.describe()
        assert desc["hooks"] == {}

    def test_hash_stable(self) -> None:
        pipe: Pipe[Any, Any] = Pipe(name="test")

        @pipe.step(to="b")
        async def a(state: None) -> None:
            pass

        @pipe.step()
        async def b(state: None) -> None:
            pass

        h1 = pipe.describe()["pipeline_hash"]
        h2 = pipe.describe()["pipeline_hash"]
        assert h1 == h2
