import pytest
from justpipe import Pipe


def test_pipe_init():
    pipe = Pipe("MyPipe")
    assert pipe.name == "MyPipe"

    from justpipe.core import tenacity_retry_middleware

    assert pipe.middleware == [tenacity_retry_middleware]


def test_step_registration_basics():
    pipe = Pipe()

    @pipe.step("start", to="next_step")
    async def start(state, context):
        pass

    assert "start" in pipe._steps
    assert pipe._topology["start"] == ["next_step"]


def test_step_decorator_variations():
    pipe = Pipe()

    @pipe.step
    async def auto_named():
        pass

    @pipe.step(to="explicit")
    async def auto_named2():
        pass

    @pipe.step("explicit", to=["a", "b"])
    async def explicit():
        pass

    assert "auto_named" in pipe._steps
    assert "auto_named2" in pipe._steps
    assert "explicit" in pipe._steps
    assert pipe._topology["explicit"] == ["a", "b"]


def test_step_validation_errors():
    pipe = Pipe()

    # Unknown argument
    with pytest.raises(ValueError, match="Unknown argument 'foo'"):

        @pipe.step("invalid")
        async def unknown_arg(foo):
            pass


def test_step_resolve_callable_targets():
    pipe = Pipe()

    async def target():
        pass

    @pipe.step("start", to=target)
    async def start():
        pass

    assert pipe._topology["start"] == ["target"]
