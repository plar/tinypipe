from typing import Any

import pytest

from justpipe import DefinitionError, Pipe


def test_pipe_init() -> None:
    pipe: Pipe[Any, Any] = Pipe(name="MyPipe")
    assert pipe.name == "MyPipe"

    from justpipe.middleware import tenacity_retry_middleware

    assert pipe.middleware == [tenacity_retry_middleware]


def test_step_registration_basics() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("start", to="next_step")
    async def start(state: Any, context: Any) -> None:
        pass

    assert {s.name for s in pipe.steps()} >= {"start"}
    assert pipe.topology["start"] == ["next_step"]


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

    names = {s.name for s in pipe.steps()}
    assert "auto_named" in names
    assert "auto_named2" in names
    assert "explicit" in names
    assert pipe.topology["explicit"] == ["a", "b"]


def test_step_resolve_callable_targets() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    async def target() -> None:
        pass

    @pipe.step("start", to=target)
    async def start() -> None:
        pass

    assert pipe.topology["start"] == ["target"]


def test_step_decorator_no_parens_explicit_call() -> None:
    # Explicitly calling pipe.step(func)
    pipe: Pipe[Any, Any] = Pipe()

    async def my_step() -> None:
        pass

    # This simulates @pipe.step without ()
    pipe.step(my_step)

    assert "my_step" in {s.name for s in pipe.steps()}


def test_duplicate_step_name_raises() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    @pipe.step("dup")
    async def first() -> None:
        pass

    with pytest.raises(DefinitionError, match="already registered"):

        @pipe.step("dup")
        async def second() -> None:
            pass
