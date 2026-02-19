"""CLI Workflow Demo - Generate test data for CLI commands.

This demo generates pipeline runs with persist=True so you can test CLI commands:
- justpipe list
- justpipe show <run-id>
- justpipe timeline <run-id>
- justpipe compare <run-id-1> <run-id-2>
- justpipe export <run-id>
"""

import asyncio
import os
from pathlib import Path

from justpipe import Pipe, EventType
from justpipe.storage.sqlite import SQLiteBackend


async def main():
    print("Generating test data for CLI commands...")
    print()

    tmp_dir = "/tmp/justpipe_cli_demo"
    os.environ["JUSTPIPE_STORAGE_PATH"] = tmp_dir

    # Run 1: Fast pipeline
    print("Run 1: Fast pipeline (2 words)")
    pipe1: Pipe[dict, None] = Pipe(name="cli_workflow_demo", persist=True)

    @pipe1.step("parse", to="count")
    async def parse1(state: dict):
        await asyncio.sleep(0.005)
        state["text"] = state.get("input", "").lower()

    @pipe1.step("count")
    async def count1(state: dict):
        await asyncio.sleep(0.003)
        state["word_count"] = len(state.get("text", "").split())

    run1_id: str | None = None
    async for event in pipe1.run({"input": "Hello World"}):
        if event.type == EventType.FINISH:
            run1_id = event.run_id

    print(f"  Run ID: {run1_id}")
    print()

    # Run 2: Slower pipeline (more data)
    print("Run 2: Slower pipeline (9 words)")
    pipe2: Pipe[dict, None] = Pipe(name="cli_workflow_demo", persist=True)

    @pipe2.step("parse", to="count")
    async def parse2(state: dict):
        await asyncio.sleep(0.010)
        state["text"] = state.get("input", "").lower()

    @pipe2.step("count")
    async def count2(state: dict):
        await asyncio.sleep(0.008)
        state["word_count"] = len(state.get("text", "").split())

    run2_id: str | None = None
    async for event in pipe2.run(
        {"input": "The quick brown fox jumps over the lazy dog"}
    ):
        if event.type == EventType.FINISH:
            run2_id = event.run_id

    print(f"  Run ID: {run2_id}")
    print()

    # Run 3: Failed pipeline
    print("Run 3: Failed pipeline (with error)")
    pipe3: Pipe[dict, None] = Pipe(name="cli_workflow_demo", persist=True)

    @pipe3.step("parse", to="fail")
    async def parse3(state: dict):
        state["text"] = state.get("input", "").lower()

    @pipe3.step("fail")
    async def fail(state: dict):
        raise ValueError("Simulated error for testing")

    run3_id: str | None = None
    async for event in pipe3.run({"input": "Error test"}):
        if event.type == EventType.FINISH:
            run3_id = event.run_id

    print(f"  Run ID: {run3_id}")
    print()

    # Show summary
    db_files = list(Path(tmp_dir).rglob("runs.db"))
    total_runs = 0
    for db in db_files:
        backend = SQLiteBackend(db)
        total_runs += len(backend.list_runs())
    print(f"Total persisted runs: {total_runs}")
    print()

    print("=" * 60)
    print("Test data generated! Try these CLI commands:")
    print("=" * 60)
    print()
    env_prefix = f"JUSTPIPE_STORAGE_PATH={tmp_dir}"
    print("# List all runs")
    print(f"{env_prefix} uv run justpipe list")
    print()
    if run1_id:
        print("# Show run details")
        print(f"{env_prefix} uv run justpipe show {run1_id[:12]}")
        print()
        print("# View timeline")
        print(f"{env_prefix} uv run justpipe timeline {run1_id[:12]}")
        print()
    if run1_id and run2_id:
        print("# Compare two runs")
        print(f"{env_prefix} uv run justpipe compare {run1_id[:12]} {run2_id[:12]}")
        print()
    if run1_id:
        print("# Export run data")
        print(f"{env_prefix} uv run justpipe export {run1_id[:12]}")
        print()
    print("# Filter by status")
    print(f"{env_prefix} uv run justpipe list --status failed")
    print()


if __name__ == "__main__":
    asyncio.run(main())
