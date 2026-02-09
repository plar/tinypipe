"""CLI Workflow Demo - Generate test data for CLI commands.

This demo generates pipeline runs in SQLiteStorage so you can test CLI commands:
- justpipe list
- justpipe show <run-id>
- justpipe timeline <run-id>
- justpipe compare <run-id-1> <run-id-2>
- justpipe export <run-id>
"""

import asyncio
from justpipe import Pipe
from justpipe.observability import StorageObserver
from justpipe.storage import SQLiteStorage


async def main():
    print("Generating test data for CLI commands...")
    print()

    # Use SQLite storage (persistent)
    storage = SQLiteStorage("~/.justpipe")

    # Run 1: Fast pipeline
    print("Run 1: Fast pipeline (2 words)")
    pipe1 = Pipe(name="cli_workflow_demo")

    @pipe1.step()
    async def parse(state):
        await asyncio.sleep(0.005)
        state["text"] = state.get("input", "").lower()
        return state

    @pipe1.step()
    async def count(state):
        await asyncio.sleep(0.003)
        state["word_count"] = len(state.get("text", "").split())
        return state

    obs1 = StorageObserver(storage)
    pipe1.add_observer(obs1)

    async for event in pipe1.run({"input": "Hello World"}):
        pass

    run1_id = obs1.get_run_id()
    print(f"  Run ID: {run1_id}")
    print()

    # Run 2: Slower pipeline (more data)
    print("Run 2: Slower pipeline (9 words)")
    pipe2 = Pipe(name="cli_workflow_demo")

    @pipe2.step()
    async def parse(state):
        await asyncio.sleep(0.010)
        state["text"] = state.get("input", "").lower()
        return state

    @pipe2.step()
    async def count(state):
        await asyncio.sleep(0.008)
        state["word_count"] = len(state.get("text", "").split())
        return state

    obs2 = StorageObserver(storage)
    pipe2.add_observer(obs2)

    async for event in pipe2.run(
        {"input": "The quick brown fox jumps over the lazy dog"}
    ):
        pass

    run2_id = obs2.get_run_id()
    print(f"  Run ID: {run2_id}")
    print()

    # Run 3: Failed pipeline
    print("Run 3: Failed pipeline (with error)")
    pipe3 = Pipe(name="cli_workflow_demo")

    @pipe3.step()
    async def parse(state):
        state["text"] = state.get("input", "").lower()
        return state

    @pipe3.step()
    async def fail(state):
        raise ValueError("Simulated error for testing")

    obs3 = StorageObserver(storage)
    pipe3.add_observer(obs3)

    try:
        async for event in pipe3.run({"input": "Error test"}):
            pass
    except ValueError:
        pass  # Expected

    run3_id = obs3.get_run_id()
    print(f"  Run ID: {run3_id}")
    print()

    print("=" * 60)
    print("Test data generated! Try these CLI commands:")
    print("=" * 60)
    print()
    print("# list all runs")
    print("uv run justpipe list")
    print()
    print("# Show run details")
    print(f"uv run justpipe show {run1_id[:16]}")
    print()
    print("# View timeline")
    print(f"uv run justpipe timeline {run1_id[:16]}")
    print()
    print("# Compare two runs")
    print(f"uv run justpipe compare {run1_id[:16]} {run2_id[:16]}")
    print()
    print("# Export run data")
    print(f"uv run justpipe export {run1_id[:16]}")
    print()
    print("# Filter by status")
    print("uv run justpipe list --status error")
    print()


if __name__ == "__main__":
    asyncio.run(main())
