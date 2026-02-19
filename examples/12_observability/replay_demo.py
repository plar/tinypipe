"""Replay & Compare Demo.

Demonstrates:
- compare_runs() - comparing two pipeline executions programmatically
- format_comparison() - human-readable comparison output
- Querying persisted runs via SQLiteBackend
"""

import asyncio
import os
from pathlib import Path

from justpipe import Pipe, EventType
from justpipe.observability import compare_runs, format_comparison
from justpipe.storage.sqlite import SQLiteBackend


async def main():
    print("=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Compare Runs")
    print("=" * 80)
    print()

    tmp_dir = "/tmp/justpipe_replay_demo"
    os.environ["JUSTPIPE_STORAGE_PATH"] = tmp_dir

    # ==================== Run 1: Short input ====================
    print("Run 1: Short input")
    pipe1: Pipe[dict, None] = Pipe(name="process_data", persist=True)

    @pipe1.step("parse", to="count")
    async def parse1(state: dict):
        state["parsed"] = state.get("raw", "").upper()

    @pipe1.step("count")
    async def count1(state: dict):
        state["word_count"] = len(state.get("parsed", "").split())

    run1_id: str | None = None
    async for event in pipe1.run({"raw": "hello world"}):
        if event.type == EventType.FINISH:
            run1_id = event.run_id
    print(f"  Run ID: {run1_id}")
    print()

    # ==================== Run 2: Longer input ====================
    print("Run 2: Longer input")
    pipe2: Pipe[dict, None] = Pipe(name="process_data", persist=True)

    @pipe2.step("parse", to="count")
    async def parse2(state: dict):
        state["parsed"] = state.get("raw", "").upper()
        await asyncio.sleep(0.01)  # Slightly slower

    @pipe2.step("count")
    async def count2(state: dict):
        state["word_count"] = len(state.get("parsed", "").split())

    run2_id: str | None = None
    async for event in pipe2.run(
        {"raw": "the quick brown fox jumps over the lazy dog"}
    ):
        if event.type == EventType.FINISH:
            run2_id = event.run_id
    print(f"  Run ID: {run2_id}")
    print()

    # ==================== Compare runs ====================
    if run1_id and run2_id:
        # Find the backend for the persisted pipeline
        db_files = list(Path(tmp_dir).rglob("runs.db"))
        if db_files:
            backend = SQLiteBackend(db_files[0])

            print("=" * 60)
            print("Comparing Run 1 vs Run 2")
            print("=" * 60)
            print()

            # Load run records and events for comparison
            rec1 = backend.get_run(run1_id)
            rec2 = backend.get_run(run2_id)
            ev1 = backend.get_events(run1_id)
            ev2 = backend.get_events(run2_id)

            if rec1 and rec2:
                comparison = compare_runs(
                    rec1, ev1, rec2, ev2,
                    pipeline1_name="process_data",
                    pipeline2_name="process_data",
                )
                output = format_comparison(comparison)
                print(output)
                print()

            # Show all stored runs
            runs = backend.list_runs()
            print(f"Total runs stored: {len(runs)}")
            for run in runs:
                print(
                    f"  {run.run_id[:12]}  "
                    f"status={run.status.value:<10}  "
                    f"duration={run.duration.total_seconds():.3f}s"
                )
            print()

    # ==================== Summary ====================
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print("  compare_runs() - Programmatic run comparison")
    print("  format_comparison() - Human-readable comparison output")
    print("  persist=True - Automatic SQLite persistence")
    print()
    print("These features enable:")
    print("  Performance regression detection")
    print("  A/B testing different pipeline versions")
    print("  Run data querying for external analysis")
    print()


if __name__ == "__main__":
    asyncio.run(main())
