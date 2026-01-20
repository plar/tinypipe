import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from justpipe import Pipe, EventType
from examples.utils import save_graph


class NumberType(Enum):
    EVEN = "even"
    ODD = "odd"


@dataclass
class State:
    value: int = 0
    message: str = ""


pipe = Pipe[State, None]()


@pipe.step("even_handler")
async def even_handler(state: State):
    state.value *= 2
    state.message = "Value was even, so we doubled it."


@pipe.step("odd_handler")
async def odd_handler(state: State):
    state.value += 1
    state.message = "Value was odd, so we incremented it."


@pipe.switch(
    routes={
        NumberType.EVEN: even_handler,
        NumberType.ODD: "odd_handler",  # str step name works too
    },
)
async def number_detector(state: State):
    print(f"Checking value: {state.value}")
    is_even = state.value % 2 == 0
    if is_even:
        print("Routing to: even_handler")
        return NumberType.EVEN
    else:
        print("Routing to: odd_handler")
        return NumberType.ODD


@pipe.step(to=number_detector)
async def start():
    print("Start number detector pipeline...")


async def main():
    # Example 1: Even value
    state_even = State(value=10)
    print("--- Running with Even Value (10) ---")
    async for event in pipe.run(state_even, start=start):
        if event.type == EventType.FINISH:
            print(f"Final Value: {state_even.value}")
            print(f"Message: {state_even.message}")

    # Example 2: Odd value
    state_odd = State(value=7)
    print("\n--- Running with Odd Value (7) ---")
    async for event in pipe.run(state_odd, start="start"):
        if event.type == EventType.FINISH:
            print(f"Final Value: {state_odd.value}")
            print(f"Message: {state_odd.message}")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
