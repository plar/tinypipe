import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any
from justpipe import Pipe, EventType
from examples.utils import save_graph


@dataclass
class State:
    data: str = ""


@dataclass
class Context:
    # Context is a great place for resources like DB connections or API clients
    db: Dict[str, Any] = field(default_factory=dict)


pipe = Pipe[State, Context]()


# 1. Register a startup hook
@pipe.on_startup
async def setup_db(ctx: Context):
    print("Connecting to mock database...")
    await asyncio.sleep(0.1)  # Simulate network latency
    ctx.db["status"] = "connected"
    ctx.db["data"] = {"user:1": "some_value"}


# 2. Register a shutdown hook
@pipe.on_shutdown
async def teardown_db(ctx: Context):
    print("Disconnecting from mock database...")
    await asyncio.sleep(0.1)
    ctx.db.clear()


@pipe.step("fetch")
async def fetch_data(state: State, ctx: Context):
    print("Fetching data from DB...")
    if ctx.db.get("status") == "connected":
        state.data = ctx.db["data"].get("user:1", "not_found")
        print(f"Data fetched from DB: {state.data}")


async def main():
    state = State()
    context = Context()

    async for event in pipe.run(state, context):
        if event.type == EventType.FINISH:
            print("Pipeline finished.")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
