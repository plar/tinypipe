import pytest
from unittest.mock import patch
from typing import Any
from collections.abc import Callable
from justpipe import Pipe, simple_logging_middleware, StepContext


@pytest.mark.parametrize(
    ("step_name", "step_kind"),
    [
        ("test", "async"),
        ("stream", "stream"),
        ("sync_step", "sync"),
    ],
)
@pytest.mark.asyncio
async def test_simple_logging_middleware_logs_duration(
    step_name: str,
    step_kind: str,
) -> None:
    # Arrange
    pipe: Pipe[Any, Any] = Pipe()
    pipe.add_middleware(simple_logging_middleware)

    if step_kind == "async":

        @pipe.step(step_name)
        async def test_step() -> None:
            return None

    elif step_kind == "stream":

        @pipe.step(step_name)
        async def test_step() -> Any:
            yield 1
            yield 2

    else:

        @pipe.step(step_name)
        def test_step() -> None:
            return None

    _ = test_step

    # Act
    with patch("logging.Logger.debug") as mock_debug:
        async for _ in pipe.run({}):
            pass

    # Assert
    mock_debug.assert_called()
    args, _ = mock_debug.call_args
    assert f"Step '{step_name}' took" in args[0]


@pytest.mark.asyncio
async def test_middleware_application() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    log: list[str] = []

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


@pytest.mark.asyncio
async def test_middleware_chaining() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    order: list[int] = []

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

    @pipe.step("fail_twice", retries=2, retry_wait_min=0.01, retry_wait_max=0.01)
    async def fail_twice() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("fail")

    async for _ in pipe.run({}):
        pass

    assert attempts == 3


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
async def test_add_middleware_after_first_run_raises() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    order: list[str] = []

    def mw1(func: Callable[..., Any], ctx: StepContext) -> Callable[..., Any]:
        _ = ctx

        async def wrapped(**kwargs: Any) -> Any:
            order.append("mw1")
            return await func(**kwargs)

        return wrapped

    pipe.add_middleware(mw1)

    @pipe.step("test")
    async def test() -> None:
        order.append("step")

    # First run: only mw1 is configured.
    async for _ in pipe.run({}):
        pass
    assert order == ["mw1", "step"]

    with pytest.raises(RuntimeError, match="frozen after first run"):
        pipe.add_middleware(mw1)
