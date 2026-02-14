from typing import Any
from collections.abc import Callable
from unittest.mock import patch

import pytest

from justpipe import Pipe, StepContext


def test_middleware_kwargs_passing() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    captured_ctx: dict[str, Any] = {}

    def capture_middleware(
        func: Callable[..., Any], ctx: StepContext
    ) -> Callable[..., Any]:
        captured_ctx["name"] = ctx.name
        captured_ctx["kwargs"] = ctx.kwargs
        captured_ctx["pipe_name"] = ctx.pipe_name
        return func

    pipe.add_middleware(capture_middleware)

    @pipe.step("test", foo="bar", limit=10)
    async def test() -> None:
        pass

    # Middleware is applied at finalize time
    pipe.registry.finalize()
    assert captured_ctx["name"] == "test"
    assert captured_ctx["kwargs"] == {"foo": "bar", "limit": 10}
    assert captured_ctx["pipe_name"] == "Pipe"


def test_tenacity_missing_warning() -> None:
    """Verify warning when tenacity is requested but missing."""
    with patch("justpipe.middleware.HAS_TENACITY", False):
        pipe: Pipe[Any, Any] = Pipe()

        @pipe.step("retry_step", retries=1)
        async def retry_step() -> None:
            pass

        with pytest.warns(UserWarning, match="tenacity"):
            pipe.registry.finalize()


def test_retry_on_async_generator_warning() -> None:
    with patch("justpipe.middleware.HAS_TENACITY", True):
        pipe: Pipe[Any, Any] = Pipe()

        @pipe.step("stream_step", retries=2)
        async def stream_step() -> Any:
            yield 1

        with pytest.warns(UserWarning, match="Streaming step.*cannot retry"):
            pipe.registry.finalize()
