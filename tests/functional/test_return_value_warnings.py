"""Functional tests for step return-value validation warnings."""

import warnings

import pytest
from typing import Any

from justpipe import Pipe, Stop


@pytest.mark.asyncio
async def test_return_dict_triggers_warning() -> None:
    """Test that returning a dict triggers a warning."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> dict[str, str]:
        return {"data": "lost"}

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "bad_step" in str(w[0].message)
        assert "dict" in str(w[0].message)
        assert "will be ignored" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_list_triggers_warning() -> None:
    """Test that returning a list triggers a warning."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> list[int]:
        return [1, 2, 3]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert "bad_step" in str(w[0].message)
        assert "list" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_object_triggers_warning() -> None:
    """Test that returning an arbitrary object triggers a warning."""

    class CustomObject:
        pass

    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> CustomObject:
        return CustomObject()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert "bad_step" in str(w[0].message)
        assert "CustomObject" in str(w[0].message)


@pytest.mark.asyncio
async def test_return_none_no_warning() -> None:
    """Test that returning None does not trigger a warning."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def good_step(state: Any) -> None:
        return None

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 0


@pytest.mark.asyncio
async def test_return_string_no_warning() -> None:
    """Test that returning a step name (string) does not trigger a warning."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def target(state: Any) -> None:
        pass

    @pipe.step()
    async def start(state: Any) -> str:
        return "target"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None, start="start"):
            pass

        assert len(w) == 0


@pytest.mark.asyncio
async def test_return_stop_no_warning() -> None:
    """Test that returning Stop does not trigger a warning."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def stop_step(state: Any) -> Any:
        return Stop

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 0


@pytest.mark.asyncio
async def test_warning_message_contains_helpful_info() -> None:
    """Test that warning message contains helpful information."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("my_step")
    async def bad_step(state: Any) -> dict[str, str]:
        return {"key": "value"}

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        message = str(w[0].message)

        # Should contain step name
        assert "my_step" in message

        # Should contain type
        assert "dict" in message

        # Should explain it's ignored
        assert "ignored" in message

        # Should suggest alternatives
        assert "mutate state" in message or "yield" in message
