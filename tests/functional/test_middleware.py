import pytest
from tinypipe import Pipe


@pytest.mark.asyncio
async def test_add_middleware():
    pipe = Pipe()
    log = []

    def logging_middleware(func, kwargs):
        async def wrapper(state, context):
            log.append("before")
            res = await func(state, context)
            log.append("after")
            return res

        return wrapper

    pipe.add_middleware(logging_middleware)

    @pipe.step("test")
    async def step_test(s, c):
        log.append("inside")

    await pipe._steps["test"]({}, None)
    assert log == ["before", "inside", "after"]


@pytest.mark.asyncio
async def test_middleware_order():
    pipe = Pipe()
    log = []

    def mw1(func, kwargs):
        async def wrapper(s, c):
            log.append("1_in")
            res = await func(s, c)
            log.append("1_out")
            return res

        return wrapper

    def mw2(func, kwargs):
        async def wrapper(s, c):
            log.append("2_in")
            res = await func(s, c)
            log.append("2_out")
            return res

        return wrapper

    pipe.add_middleware(mw1)
    pipe.add_middleware(mw2)

    @pipe.step("test")
    async def step_test(s, c):
        log.append("core")

    await pipe._steps["test"]({}, None)

    # Outer middleware (mw2) wraps inner (mw1)
    assert log == ["2_in", "1_in", "core", "1_out", "2_out"]


@pytest.mark.asyncio
async def test_tenacity_retry():
    pipe = Pipe()
    count = 0

    @pipe.step("retry_test", retries=2)
    async def fail_twice():
        nonlocal count
        count += 1
        if count < 3:
            raise ValueError("fail")
        return "success"

    await pipe._steps["retry_test"]()
    assert count == 3
