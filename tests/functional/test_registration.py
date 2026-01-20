from typing import Any
from justpipe import Pipe


def test_pipe_init() -> None:
    pipe: Pipe[Any, Any] = Pipe("MyPipe")
    assert pipe.name == "MyPipe"

    from justpipe.core import tenacity_retry_middleware

    assert pipe.middleware == [tenacity_retry_middleware]


def test_step_registration_basics() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to="next_step")
    async def start(state: Any, context: Any) -> None:
        pass

    assert "start" in pipe._steps
    assert pipe._topology["start"] == ["next_step"]


def test_step_decorator_variations() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step
    async def auto_named() -> None:
        pass

    @pipe.step(to="explicit")
    async def auto_named2() -> None:
        pass

    @pipe.step("explicit", to=["a", "b"])
    async def explicit() -> None:
        pass

    assert "auto_named" in pipe._steps
    assert "auto_named2" in pipe._steps
    assert "explicit" in pipe._steps
    assert pipe._topology["explicit"] == ["a", "b"]


def test_step_resolve_callable_targets() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    async def target() -> None:
        pass

    @pipe.step("start", to=target)
    async def start() -> None:
        pass

    assert pipe._topology["start"] == ["target"]


def test_step_decorator_no_parens_explicit_call() -> None:
    # Explicitly calling pipe.step(func)
    pipe: Pipe[Any, Any] = Pipe()

    async def my_step() -> None:
        pass

    # This simulates @pipe.step without ()
    pipe.step(my_step)

    assert "my_step" in pipe._steps
