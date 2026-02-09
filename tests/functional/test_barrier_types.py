from typing import Any

import asyncio
import pytest

from justpipe import Pipe, BarrierType


@pytest.mark.asyncio
async def test_barrier_any_executes_on_first_parent() -> None:
    """Test that a step with BarrierType.ANY executes as soon as the first parent finishes."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_slow_parent = asyncio.Event()

    @pipe.step(to="combine")
    async def step_fast(state: dict[str, Any]) -> None:
        state["fast_done"] = True

    @pipe.step(to="combine")
    async def step_slow(state: dict[str, Any]) -> None:
        await release_slow_parent.wait()
        state["slow_done"] = True

    # This should trigger as soon as 'step_fast' finishes
    @pipe.step(barrier_type=BarrierType.ANY)
    async def combine(state: dict[str, Any]) -> None:
        if state.get("slow_done"):
            # If slow is done, we waited too long!
            state["error"] = "Waited for slow!"
        state["combine_count"] = state.get("combine_count", 0) + 1
        release_slow_parent.set()

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("fast_done") is True
    # combine should have run
    assert state.get("combine_count") == 1
    assert "error" not in state, "BarrierType.ANY waited for slow step"
    # slow should eventually finish, but combine shouldn't run again (for this DAG cycle)
    assert state.get("slow_done") is True


@pytest.mark.asyncio
async def test_barrier_any_ignores_subsequent_parents() -> None:
    """Test that a step with BarrierType.ANY does not re-execute when subsequent parents finish."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_waiting_parents = asyncio.Event()

    @pipe.step(to="combine")
    async def p1(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to="combine")
    async def p2(state: dict[str, Any]) -> None:
        _ = state
        await release_waiting_parents.wait()

    @pipe.step(to="combine")
    async def p3(state: dict[str, Any]) -> None:
        _ = state
        await release_waiting_parents.wait()

    @pipe.step(barrier_type=BarrierType.ANY)
    async def combine(state: dict[str, Any]) -> None:
        state["combine_executions"] = state.get("combine_executions", 0) + 1
        release_waiting_parents.set()

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    # Should only run once
    assert state.get("combine_executions") == 1


@pytest.mark.asyncio
async def test_barrier_all_waits_for_everyone() -> None:
    """Test that the default BarrierType.ALL waits for all parents."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_second_parent = asyncio.Event()

    @pipe.step(to="combine")
    async def p1(state: dict[str, Any]) -> None:
        state["p1"] = True
        release_second_parent.set()

    @pipe.step(to="combine")
    async def p2(state: dict[str, Any]) -> None:
        await release_second_parent.wait()
        state["p2"] = True

    @pipe.step(barrier_type=BarrierType.ALL)
    async def combine(state: dict[str, Any]) -> None:
        if not state.get("p1") or not state.get("p2"):
            state["error"] = "Did not wait for all!"
        state["combine_done"] = True

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("combine_done") is True
    assert "error" not in state


@pytest.mark.asyncio
async def test_barrier_any_with_map() -> None:
    """Test that @pipe.map respects BarrierType.ANY."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_slow_parent = asyncio.Event()

    @pipe.step(to="process_items")
    async def p1(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to="process_items")
    async def p2(state: dict[str, Any]) -> None:
        _ = state
        await release_slow_parent.wait()

    @pipe.step()
    async def worker(item: int, state: dict[str, Any]) -> None:
        state["items"] = state.get("items", []) + [item]

    @pipe.map(each=worker, barrier_type=BarrierType.ANY)
    async def process_items(state: dict[str, Any]) -> list[int]:
        state["map_started"] = True
        release_slow_parent.set()
        return [1, 2, 3]

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("map_started") is True
    assert len(state.get("items", [])) == 3


@pytest.mark.asyncio
async def test_barrier_any_with_switch() -> None:
    """Test that @pipe.switch respects BarrierType.ANY."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_slow_parent = asyncio.Event()

    @pipe.step(to="decide")
    async def p1(state: dict[str, Any]) -> None:
        state["val"] = 10

    @pipe.step(to="decide")
    async def p2(state: dict[str, Any]) -> None:
        await release_slow_parent.wait()

    @pipe.step()
    async def target(state: dict[str, Any]) -> None:
        state["reached"] = True

    @pipe.switch(to={True: target}, barrier_type=BarrierType.ANY)
    async def decide(state: dict[str, Any]) -> bool:
        release_slow_parent.set()
        return state.get("val") == 10

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("reached") is True


@pytest.mark.asyncio
async def test_barrier_any_with_sub() -> None:
    """Test that @pipe.sub respects BarrierType.ANY."""
    sub_pipe: Pipe[dict[str, Any], None] = Pipe()
    release_slow_parent = asyncio.Event()

    @sub_pipe.step()
    async def sub_step(state: dict[str, Any]) -> None:
        state["sub_done"] = True

    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.step(to="run_sub")
    async def p1(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to="run_sub")
    async def p2(state: dict[str, Any]) -> None:
        _ = state
        await release_slow_parent.wait()

    @pipe.sub(pipeline=sub_pipe, barrier_type=BarrierType.ANY)
    async def run_sub(state: dict[str, Any]) -> dict[str, Any]:
        release_slow_parent.set()
        return state

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("sub_done") is True


@pytest.mark.asyncio
async def test_barrier_any_resilience() -> None:
    """
    Test that BarrierType.ANY proceeds if one parent is skipped or fails (handled),
    and the other succeeds.
    """
    from justpipe import Skip

    pipe: Pipe[dict[str, Any], None] = Pipe()

    @pipe.step(to="combine")
    async def p1(state: dict[str, Any]) -> Skip:
        # P1 skips execution
        return Skip()

    @pipe.step(to="combine")
    async def p2(state: dict[str, Any]) -> None:
        state["p2_done"] = True

    @pipe.step(barrier_type=BarrierType.ANY)
    async def combine(state: dict[str, Any]) -> None:
        state["combine_done"] = True

    state: dict[str, Any] = {}
    async for _ in pipe.run(state):
        pass

    assert state.get("p2_done") is True
    assert state.get("combine_done") is True


@pytest.mark.asyncio
async def test_mixed_barriers() -> None:
    """Test chaining an ANY barrier step into an ALL barrier step."""
    pipe: Pipe[dict[str, Any], None] = Pipe()
    release_slow_branch = asyncio.Event()
    release_branch_d = asyncio.Event()

    # Flow:
    # A, B -> C (ANY)
    # C, D -> E (ALL)

    @pipe.step(to="c")
    async def a(state: dict[str, Any]) -> None:
        _ = state

    @pipe.step(to="c")
    async def b(state: dict[str, Any]) -> None:
        _ = state
        await release_slow_branch.wait()

    @pipe.step(to="e", barrier_type=BarrierType.ANY)
    async def c(state: dict[str, Any]) -> None:
        state["c_count"] = state.get("c_count", 0) + 1
        release_slow_branch.set()
        release_branch_d.set()

    @pipe.step(to="e")
    async def d(state: dict[str, Any]) -> None:
        await release_branch_d.wait()
        state["d_done"] = True

    @pipe.step(barrier_type=BarrierType.ALL)
    async def e(state: dict[str, Any]) -> None:
        if not state.get("d_done"):
            state["error"] = "E ran before D!"
        if state.get("c_count", 0) != 1:
            state["error"] = f"C ran {state.get('c_count')} times!"
        state["e_done"] = True

    state: dict[str, Any] = {}
    async for _ in pipe.run(state, timeout=1.0):
        pass

    assert state.get("e_done") is True
    assert "error" not in state
