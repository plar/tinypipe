"""Functional tests for step return-value validation warnings."""

import warnings

import pytest
from typing import Any

from justpipe import Pipe, Stop


class _CustomObject:
    pass


@pytest.mark.parametrize(
    ("return_value", "expected_type_name"),
    [
        pytest.param({"data": "lost"}, "dict", id="dict"),
        pytest.param([1, 2, 3], "list", id="list"),
        pytest.param(_CustomObject(), "_CustomObject", id="object"),
    ],
)
async def test_return_value_triggers_warning(
    return_value: Any, expected_type_name: str
) -> None:
    """Returning a non-routing value triggers a warning with step name and type."""
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step()
    async def bad_step(state: Any) -> Any:
        return return_value

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        async for _ in pipe.run(None):
            pass

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "bad_step" in str(w[0].message)
        assert expected_type_name in str(w[0].message)


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
