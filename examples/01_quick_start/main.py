import asyncio
from dataclasses import dataclass
from pathlib import Path
from justpipe import Pipe, EventType
from examples.utils import save_graph


@dataclass
class State:
    message: str = ""


# 1. Define the Pipe with concrete State type (no context)
# This ensures type safety throughout the pipeline.
pipe = Pipe(State)


@pipe.step()
async def respond(state: State):
    """A streaming step that yields a token."""
    yield f"{state.message}, World!"


@pipe.step(to=respond)
async def greet(state: State):
    """A simple step that modifies the state."""
    state.message = "Hello"


async def main():
    # 2. Initialize the state
    state = State()

    print("Starting pipeline...")

    # 3. Run the pipeline
    # pipe.run() returns an async generator of events.
    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            # TOKEN events are yielded by async generator steps
            print(f"Received token: {event.payload}")
        elif event.type == EventType.STEP_ERROR:
            print(f"Error: {event.payload}")

    # 4. Save the visualization
    # We use our utility to save a Mermaid diagram of this pipe.
    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
