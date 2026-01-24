import pytest
from unittest.mock import patch
from typing import Any, Callable, Dict, List
from justpipe import Pipe, simple_logging_middleware, StepContext


@pytest.mark.asyncio
async def test_simple_logging_middleware_integration() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    pipe.add_middleware(simple_logging_middleware)

    @pipe.step("test")
    async def test() -> None:
        pass

    with patch("logging.Logger.debug") as mock_debug:
        async for _ in pipe.run({}):
            pass

        mock_debug.assert_called()
        # Verify it contains the step name and execution time
        args, _ = mock_debug.call_args
        assert "Step 'test' took" in args[0]


@pytest.mark.asyncio
async def test_middleware_application() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log: List[str] = []

    def logging_middleware(
        func: Callable[..., Any], ctx: StepContext
    ) -> Callable[..., Any]:
        async def wrapped(*args: Any, **kw: Any) -> Any:
            log.append("before")
            res = await func(*args, **kw)
            log.append("after")
            return res

        return wrapped

    pipe.add_middleware(logging_middleware)

    @pipe.step("test")
    async def test() -> None:
        log.append("exec")

    async for _ in pipe.run({}):
        pass

    assert log == ["before", "exec", "after"]


def test_middleware_kwargs_passing() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    captured_ctx: Dict[str, Any] = {}

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


@pytest.mark.asyncio
async def test_middleware_chaining() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    order: List[int] = []

    def mw1(func: Callable[..., Any], ctx: StepContext) -> Callable[..., Any]:
        async def w(*a: Any, **k: Any) -> Any:
            order.append(1)
            return await func(*a, **k)

        return w

    def mw2(func: Callable[..., Any], ctx: StepContext) -> Callable[..., Any]:
        async def w(*a: Any, **k: Any) -> Any:
            order.append(2)
            return await func(*a, **k)

        return w

    pipe.add_middleware(mw1)
    pipe.add_middleware(mw2)

    @pipe.step("t")
    async def t() -> None:
        order.append(3)

    async for _ in pipe.run({}):
        pass

    # Middleware applied in order: mw2(mw1(func))
    # Execution: mw2 -> mw1 -> func
    assert order == [2, 1, 3]


@pytest.mark.asyncio
async def test_retry_middleware_integration() -> None:
    # This tests the default retry middleware
    pipe: Pipe[Any, Any] = Pipe()
    attempts = 0

    @pipe.step("fail_twice", retries=2, retry_wait_min=0.01)
    async def fail_twice() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("fail")

    async for _ in pipe.run({}):
        pass

    assert attempts == 3


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
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("stream_step", retries=2)
    async def stream_step() -> Any:
        yield 1

    with pytest.warns(UserWarning, match="Streaming step.*cannot retry"):
        pipe.registry.finalize()


@pytest.mark.asyncio
async def test_retry_with_dict_config() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    attempts = 0

    @pipe.step("retry_step", retries={"stop": lambda _: False, "reraise": True})
    async def retry_step() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("fail")

    async for _ in pipe.run(None):
        pass

    assert attempts == 2


@pytest.mark.asyncio
async def test_simple_logging_middleware_generator() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    pipe.add_middleware(simple_logging_middleware)

    @pipe.step("stream")
    async def stream() -> Any:
        yield 1
        yield 2

    with patch("logging.Logger.debug") as mock_debug:
        async for _ in pipe.run({}):
            pass

        mock_debug.assert_called()
        args, _ = mock_debug.call_args
        assert "Step 'stream' took" in args[0]


@pytest.mark.asyncio
async def test_simple_logging_middleware_sync_step() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    pipe.add_middleware(simple_logging_middleware)

    @pipe.step("sync_step")
    def sync_step() -> None:
        return None

    with patch("logging.Logger.debug") as mock_debug:
        async for _ in pipe.run({}):
            pass

        mock_debug.assert_called()
        args, _ = mock_debug.call_args
        assert "Step 'sync_step' took" in args[0]
