from typing import Any
from justpipe import Pipe, TestPipe


class State:
    def __init__(self, val: int):
        self.val = val


async def test_mock_single_step() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.step(to="step_b")
    async def step_a(state: State) -> None:
        state.val += 1

    @pipe.step()
    async def step_b(state: State) -> None:
        state.val += 1

    tester = TestPipe(pipe)

    async def mock_a_impl(state: State) -> None:
        state.val = 10

    mock_a = tester.mock("step_a", side_effect=mock_a_impl)

    result = await tester.run(State(0))

    # Assertions
    mock_a.assert_called_once()
    assert result.final_state.val == 11  # 10 (mock_a) + 1 (step_b)
    assert "step_a" in result.step_starts
    assert "step_b" in result.step_starts


async def test_mock_with_side_effect() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.step()
    async def step_a(state: State) -> None:
        state.val += 1

    tester = TestPipe(pipe)

    async def side_effect(state: State) -> None:
        state.val += 100

    tester.mock("step_a", side_effect=side_effect)

    result = await tester.run(State(1))
    assert result.final_state.val == 101


async def test_restore_functionality() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.step()
    async def step_a(state: State) -> None:
        state.val += 1

    tester = TestPipe(pipe)

    async def mock_impl(state: State) -> None:
        state.val = 100

    tester.mock("step_a", side_effect=mock_impl)

    await tester.run(State(0))
    tester.restore()

    # Run again without mock
    result = await tester.run(State(0))
    assert result.final_state.val == 1


async def test_context_manager() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.step()
    async def step_a(state: State) -> None:
        state.val += 1

    with TestPipe(pipe) as tester:

        async def mock_impl(state: State) -> None:
            state.val = 50

        tester.mock("step_a", side_effect=mock_impl)
        result = await tester.run(State(0))
        assert result.final_state.val == 50

    # Outside context manager, original step should be restored
    tester2 = TestPipe(pipe)
    result = await tester2.run(State(0))
    assert result.final_state.val == 1


async def test_mock_injection() -> None:
    """Verify that mocks receive the correct injected arguments."""
    pipe: Pipe[State, dict[str, Any]] = Pipe(state_type=State, context_type=dict)

    @pipe.step()
    async def step_a(state: State, ctx: dict[str, Any]) -> None:
        state.val += ctx["val"]

    tester = TestPipe(pipe)

    async def mock_a_impl(state: State, ctx: dict[str, Any]) -> None:
        state.val += ctx["val"] * 2

    mock_a = tester.mock("step_a", side_effect=mock_a_impl)

    result = await tester.run(State(1), context={"val": 10})

    assert result.final_state.val == 21  # 1 + 10*2
    # Verify mock was called with correct kwargs
    kwargs = mock_a.call_args.kwargs
    assert kwargs["state"].val == 21  # State is mutated
    assert kwargs["ctx"] == {"val": 10}


async def test_tokens_and_was_called() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.step()
    async def streamer(state: State) -> Any:
        yield "token1"
        yield "token2"

    tester = TestPipe(pipe)
    result = await tester.run(State(0))

    assert result.tokens == ["token1", "token2"]
    assert result.was_called("streamer")
    assert not result.was_called("non_existent")


async def test_mock_startup() -> None:
    pipe: Pipe[State, Any] = Pipe(state_type=State)

    @pipe.on_startup
    async def startup(state: State) -> None:
        state.val = 1

    @pipe.step()
    async def step_a(state: State) -> None:
        pass

    tester = TestPipe(pipe)
    mock_start = tester.mock_startup()

    result = await tester.run(State(0))
    mock_start.assert_called_once()
    assert result.final_state.val == 0  # Startup was mocked, so val didn't change to 1

    tester.restore()
    result = await tester.run(State(0))
    assert result.final_state.val == 1  # Restored, so startup ran
