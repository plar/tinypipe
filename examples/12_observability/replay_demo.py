"""Replay & Compare Demo.

Demonstrates:
- ReplayObserver - replaying pipelines with stored initial state
- compare_runs() - comparing two pipeline executions
- CLI export command - exporting run data to JSON
"""

import asyncio
from justpipe import Pipe
from justpipe.observability import (
    StorageObserver,
    ReplayObserver,
    compare_runs,
    format_comparison,
)
from justpipe.storage import InMemoryStorage


async def main():
    print("=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Replay & Compare")
    print("=" * 80)
    print()

    # ==================== Example 1: ReplayObserver ====================
    print("=" * 60)
    print("Example 1: ReplayObserver - Replay with Stored State")
    print("=" * 60)
    print()

    # Create storage
    storage = InMemoryStorage()

    # Create a simple pipeline
    pipe = Pipe(name="process_data")

    @pipe.step()
    async def parse(state):
        """Parse input data."""
        state["parsed"] = state.get("raw", "").upper()
        return state

    @pipe.step()
    async def count(state):
        """Count words."""
        state["word_count"] = len(state.get("parsed", "").split())
        return state

    # Add storage observer
    storage_obs = StorageObserver(storage)
    pipe.add_observer(storage_obs)

    # Run 1: Original execution with initial state
    print("Running pipeline with initial state: {'raw': 'hello world'}")
    initial_state = {"raw": "hello world"}
    async for event in pipe.run(initial_state):
        pass

    # Get the run ID
    runs = await storage.list_runs()
    source_run_id = runs[0].id
    print(f"Run ID: {source_run_id[:16]}...")
    print(f"Final state: {initial_state}")  # State is mutated
    print()

    # Run 2: Replay with stored initial state (different current state)
    print("Replaying with stored initial state (ignoring current state)...")

    # Create a new pipeline instance to simulate a different run
    pipe2 = Pipe(name="process_data")

    @pipe2.step()
    async def parse(state):
        state["parsed"] = state.get("raw", "").upper()
        return state

    @pipe2.step()
    async def count(state):
        state["word_count"] = len(state.get("parsed", "").split())
        return state

    # Add replay observer
    replay_obs = ReplayObserver(storage, source_run_id)
    pipe2.add_observer(replay_obs)

    # Also add storage observer to save the replay run
    storage_obs2 = StorageObserver(storage)
    pipe2.add_observer(storage_obs2)

    # Initialize replay observer (loads stored state)
    await replay_obs.on_pipeline_start({}, {})

    # Get the loaded initial state and use it for replay
    replayed_initial_state = replay_obs.get_initial_state()
    print(f"Loaded initial state: {replayed_initial_state}")

    # Run with the replayed state
    async for event in pipe2.run(replayed_initial_state):
        pass

    print(f"Replay final state: {replayed_initial_state}")
    print()
    print("✓ Replay successful - same initial state reproduced the execution")
    print()

    # ==================== Example 2: compare_runs() ====================
    print("=" * 60)
    print("Example 2: compare_runs() - Comparing Two Runs")
    print("=" * 60)
    print()

    # Create a third run with different initial state
    pipe3 = Pipe(name="process_data")

    @pipe3.step()
    async def parse(state):
        state["parsed"] = state.get("raw", "").upper()
        return state

    @pipe3.step()
    async def count(state):
        state["word_count"] = len(state.get("parsed", "").split())
        return state

    storage_obs3 = StorageObserver(storage)
    pipe3.add_observer(storage_obs3)

    # Run with more data
    different_state = {"raw": "the quick brown fox jumps over the lazy dog"}
    async for event in pipe3.run(different_state):
        pass

    # Get all runs
    all_runs = await storage.list_runs()
    print(f"Total runs stored: {len(all_runs)}")
    print()

    # Compare first two runs (same initial state)
    run1_id = all_runs[2].id  # Original run
    run2_id = all_runs[1].id  # Replay run

    print("Comparing Run 1 (original) vs Run 2 (replay):")
    comparison1 = await compare_runs(storage, run1_id, run2_id)
    output1 = format_comparison(comparison1)
    print(output1)
    print()

    # Compare first and third runs (different initial states)
    run3_id = all_runs[0].id  # Latest run

    print("Comparing Run 1 vs Run 3 (different data):")
    comparison2 = await compare_runs(storage, run1_id, run3_id)
    output2 = format_comparison(comparison2)
    print(output2)
    print()

    # ==================== Example 3: CLI Export (Programmatic) ====================
    print("=" * 60)
    print("Example 3: Export Run Data to JSON")
    print("=" * 60)
    print()

    from justpipe.cli.commands.export import export_command

    print(f"Exporting run {run1_id[:16]}...")
    await export_command(storage, run1_id, output_file="/tmp/run_export.json")
    print()

    # Read and display excerpt
    import json

    with open("/tmp/run_export.json") as f:
        export_data = json.load(f)

    print("Export data structure:")
    print(f"  - Run ID: {export_data['run']['id'][:16]}...")
    print(f"  - Pipeline: {export_data['run']['pipeline_name']}")
    print(f"  - Status: {export_data['run']['status']}")
    print(f"  - Event count: {export_data['event_count']}")
    print()

    # ==================== Example 4: CLI Compare (Programmatic) ====================
    print("=" * 60)
    print("Example 4: CLI Compare Command")
    print("=" * 60)
    print()

    from justpipe.cli.commands.compare import compare_command

    print("Using CLI compare command:")
    await compare_command(storage, run1_id, run3_id)
    print()

    # ==================== Summary ====================
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print("✓ ReplayObserver - Load and replay with stored initial state")
    print("✓ compare_runs() - Programmatic run comparison")
    print("✓ format_comparison() - Human-readable comparison output")
    print("✓ CLI export command - Export run data to JSON")
    print("✓ CLI compare command - Compare runs from command line")
    print()
    print("These features enable:")
    print("  • Bug reproduction with exact same inputs")
    print("  • Performance regression detection")
    print("  • A/B testing different pipeline versions")
    print("  • Run data export for external analysis")
    print()


if __name__ == "__main__":
    asyncio.run(main())
