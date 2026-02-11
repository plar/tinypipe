import asyncio
from dataclasses import dataclass
from pathlib import Path
from justpipe import Pipe, EventType
from examples.utils import save_graph


@dataclass
class State:
    attempts: int = 0
    success: bool = False


pipe = Pipe(State)

# Simulated flaky API state
_api_calls = 0


@pipe.step("flaky_call", retries=3, retry_wait_min=0.1)
async def flaky_call(state: State):
    global _api_calls
    _api_calls += 1
    state.attempts = _api_calls

    print(f"Attempt {_api_calls}: Calling flaky API...")

    if _api_calls < 3:
        print(f"Attempt {_api_calls}: FAILED (simulated)")
        raise RuntimeWarning("API is currently unavailable")

    print(f"Attempt {_api_calls}: SUCCESS!")
    state.success = True


async def main():
    state = State()

    print("Running pipeline with automatic retries...")
    async for event in pipe.run(state):
        if event.type == EventType.STEP_ERROR:
            print(f"Pipeline Error: {event.payload}")

    if state.success:
        print(f"\nSuccessfully called flaky API after {state.attempts} attempts.")
    else:
        print("\nFailed to call flaky API.")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
