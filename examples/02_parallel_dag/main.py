import asyncio
from dataclasses import dataclass
from pathlib import Path
from justpipe import Pipe, EventType
from examples.utils import save_graph


@dataclass
class State:
    input_val: int = 10
    result_a: int = 0
    result_b: int = 0
    total: int = 0


pipe = Pipe[State, None]()


# 2. Fan-in (Implicit Barrier): 'combine' runs only after BOTH calc_a and calc_b complete
@pipe.step()
async def combine(state: State):
    state.total = state.result_a + state.result_b
    print(f"Combined result: {state.total}")
    yield f"Result: {state.total}"


@pipe.step(to=combine)
async def calc_a(state: State):
    """Parallel branch A"""
    await asyncio.sleep(0.1)  # Simulate work
    state.result_a = state.input_val * 2
    print(f"Branch A finished: {state.result_a}")


@pipe.step(to=combine)
async def calc_b(state: State):
    """Parallel branch B"""
    await asyncio.sleep(0.2)  # Simulate work
    state.result_b = state.input_val + 22
    print(f"Branch B finished: {state.result_b}")


# 1. Fan-out: 'start' step targets multiple steps simultaneously
@pipe.step(to=[calc_a, calc_b])
async def start(state: State):
    print(f"Starting parallel calculations for input: {state.input_val}")


async def main():
    state = State(input_val=10)

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            print(f">>> {event.data}")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
