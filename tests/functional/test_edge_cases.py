"""Edge case tests for tinypipe."""



from tinypipe import EventType, Pipe


async def test_empty_pipeline():
    """Empty pipeline should yield ERROR and FINISH, not crash."""
    pipe = Pipe()
    events = [e async for e in pipe.run({})]

    assert len(events) >= 2
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1
    assert "No steps registered" in error_events[0].data
    assert events[-1].type == EventType.FINISH


async def test_startup_exception_runs_shutdown():
    """If startup hook fails, shutdown hooks should still run."""
    shutdown_called = False

    pipe = Pipe()

    @pipe.on_startup
    async def bad_startup(ctx):
        raise ValueError("Startup failed!")

    @pipe.on_shutdown
    async def cleanup(ctx):
        nonlocal shutdown_called
        shutdown_called = True

    @pipe.step
    async def dummy(s):
        pass

    events = [e async for e in pipe.run({})]

    # Should have startup error
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Startup failed" in str(e.data) for e in error_events)

    # Shutdown should have been called
    assert shutdown_called

    # Should end with FINISH
    assert events[-1].type == EventType.FINISH


async def test_shutdown_exception_yields_error():
    """Shutdown hook exception should yield ERROR event."""
    pipe = Pipe()

    @pipe.on_shutdown
    async def bad_shutdown(ctx):
        raise ValueError("Shutdown failed!")

    @pipe.step
    async def dummy(s):
        pass

    events = [e async for e in pipe.run({})]

    # Should have shutdown error
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Shutdown failed" in str(e.data) for e in error_events)

    # Should still end with FINISH
    assert events[-1].type == EventType.FINISH


async def test_concurrent_token_streaming():
    """Parallel steps should both have their tokens collected."""
    pipe = Pipe()

    @pipe.step("start", to=["a", "b"])
    async def start(s):
        pass

    @pipe.step("a")
    async def step_a(s):
        yield "token_from_a"

    @pipe.step("b")
    async def step_b(s):
        yield "token_from_b"

    events = [e async for e in pipe.run({})]

    token_events = [e for e in events if e.type == EventType.TOKEN]
    token_data = {e.data for e in token_events}

    assert "token_from_a" in token_data
    assert "token_from_b" in token_data


async def test_streaming_exception_midstream():
    """Exception mid-stream should yield ERROR but collect prior tokens."""
    pipe = Pipe()

    @pipe.step
    async def failing_stream(s):
        yield "before_error"
        raise ValueError("Mid-stream failure!")
        yield "after_error"  # Never reached

    events = [e async for e in pipe.run({})]

    # Should have the token before the error
    token_events = [e for e in events if e.type == EventType.TOKEN]
    assert any(e.data == "before_error" for e in token_events)

    # Should have error event
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert any("Mid-stream failure" in str(e.data) for e in error_events)

    # Should end with FINISH
    assert events[-1].type == EventType.FINISH


async def test_multiple_startup_hooks_partial_failure():
    """If second startup hook fails, first ran and shutdown still runs."""
    hooks_called = []

    pipe = Pipe()

    @pipe.on_startup
    async def startup1(ctx):
        hooks_called.append("startup1")

    @pipe.on_startup
    async def startup2(ctx):
        hooks_called.append("startup2")
        raise ValueError("Second startup failed!")

    @pipe.on_shutdown
    async def shutdown1(ctx):
        hooks_called.append("shutdown1")

    @pipe.step
    async def dummy(s):
        pass

    events = [e async for e in pipe.run({})]

    assert "startup1" in hooks_called
    assert "startup2" in hooks_called
    assert "shutdown1" in hooks_called
    assert events[-1].type == EventType.FINISH


async def test_context_none_handling():
    """Steps and hooks should handle context=None gracefully."""
    pipe = Pipe()

    @pipe.on_startup
    async def startup(ctx):
        # ctx is None, should not crash
        pass

    @pipe.on_shutdown
    async def shutdown(ctx):
        # ctx is None, should not crash
        pass

    @pipe.step
    async def step_with_ctx(s, ctx):
        # ctx is None
        assert ctx is None

    events = [e async for e in pipe.run({}, context=None)]

    assert events[-1].type == EventType.FINISH
    # No errors
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 0
