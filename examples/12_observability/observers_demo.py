"""Basic observability features demo for justpipe.

This example demonstrates:
1. debug=True convenience parameter
2. EventLogger observer
3. BarrierDebugger observer
4. StorageObserver with SQLite backend
5. Multiple observers working together
"""

import asyncio
import time
from dataclasses import dataclass

from justpipe import Pipe
from justpipe.observability import EventLogger, BarrierDebugger, StorageObserver
from justpipe.storage import SQLiteStorage


@dataclass
class State:
    """Example state for document processing pipeline."""
    text: str = ""
    words: list = None
    word_counts: dict = None

    def __post_init__(self):
        if self.words is None:
            self.words = []
        if self.word_counts is None:
            self.word_counts = {}


# Example 1: Simple debug mode
async def example_simple_debug():
    """Simplest observability: just add debug=True."""
    print("\n" + "=" * 60)
    print("Example 1: Simple Debug Mode")
    print("=" * 60)

    pipe: Pipe[State, None] = Pipe(name="simple_pipeline", debug=True)

    @pipe.step("parse")
    async def parse(state: State):
        state.text = "hello world hello"
        state.words = state.text.split()

    @pipe.step("count")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1

    state = State()
    async for event in pipe.run(state):
        pass  # Events are logged by EventLogger

    print(f"\nResult: {state.word_counts}")


# Example 2: Custom EventLogger configuration
async def example_custom_logger():
    """Configure EventLogger with custom log level."""
    print("\n" + "=" * 60)
    print("Example 2: Custom EventLogger")
    print("=" * 60)

    pipe: Pipe[State, None] = Pipe(name="custom_logger_pipeline")

    # Add EventLogger with DEBUG level
    pipe.add_observer(EventLogger(level="DEBUG", sink=EventLogger.stderr_sink()))

    @pipe.step("parse")
    async def parse(state: State):
        state.text = "hello world"
        state.words = state.text.split()

    @pipe.step("process")
    async def process(state: State):
        # This will show in DEBUG mode
        pass

    state = State()
    async for event in pipe.run(state):
        pass


# Example 3: Storage with SQLite
async def example_storage():
    """Store pipeline runs for later analysis."""
    print("\n" + "=" * 60)
    print("Example 3: SQLite Storage")
    print("=" * 60)

    # Create storage backend
    storage = SQLiteStorage("/tmp/justpipe_demo")

    pipe: Pipe[State, None] = Pipe(name="stored_pipeline")

    # Add storage observer
    storage_obs = StorageObserver(storage, save_initial_state=True)
    pipe.add_observer(storage_obs)

    # Also add logger for real-time feedback
    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))

    @pipe.step("parse")
    async def parse(state: State):
        state.text = "hello world hello"
        state.words = state.text.split()

    @pipe.step("count")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1

    state = State()
    async for event in pipe.run(state):
        pass

    # Get run ID and query storage
    run_id = storage_obs.get_run_id()
    print(f"\n✓ Run stored with ID: {run_id}")

    # Query stored run
    run = await storage.get_run(run_id)
    print(f"  Status: {run.status}")
    print(f"  Duration: {run.duration:.3f}s")

    # Query stored events
    events = await storage.get_events(run_id)
    print(f"  Events: {len(events)} total")

    # list all runs
    all_runs = await storage.list_runs()
    print(f"\n✓ Total runs in storage: {len(all_runs)}")


# Example 4: Multiple observers
async def example_multiple_observers():
    """Use multiple observers together."""
    print("\n" + "=" * 60)
    print("Example 4: Multiple Observers")
    print("=" * 60)

    storage = SQLiteStorage("/tmp/justpipe_demo")

    pipe: Pipe[State, None] = Pipe(name="multi_observer_pipeline")

    # Add multiple observers
    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))
    pipe.add_observer(BarrierDebugger(warn_after=5.0, clock=time.time))
    pipe.add_observer(StorageObserver(storage))

    @pipe.step("parse")
    async def parse(state: State):
        state.text = "hello world hello python python python"
        state.words = state.text.split()

    @pipe.step("count")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1

    state = State()
    async for event in pipe.run(state):
        pass

    print(f"\nResult: {state.word_counts}")


# Example 5: Error handling with observers
async def example_error_handling():
    """Observers continue working even when steps fail."""
    print("\n" + "=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)

    storage = SQLiteStorage("/tmp/justpipe_demo")

    pipe: Pipe[State, None] = Pipe(name="error_pipeline")

    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))
    storage_obs = StorageObserver(storage)
    pipe.add_observer(storage_obs)

    @pipe.step("parse")
    async def parse(state: State):
        state.text = "hello world"
        state.words = state.text.split()

    @pipe.step("fail")
    async def fail(state: State):
        raise ValueError("Intentional error for demo")

    state = State()
    async for event in pipe.run(state):
        pass

    # Check that error was recorded
    run_id = storage_obs.get_run_id()
    events = await storage.get_events(run_id)
    error_events = [e for e in events if e.event_type == "error"]
    print(f"\n✓ Recorded {len(error_events)} error event(s)")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Basic Features")
    print("=" * 80)

    await example_simple_debug()
    await example_custom_logger()
    await example_storage()
    await example_multiple_observers()
    await example_error_handling()

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("  ✓ debug=True convenience parameter")
    print("  ✓ EventLogger with configurable log levels")
    print("  ✓ SQLite storage backend for persistence")
    print("  ✓ StorageObserver for automatic run tracking")
    print("  ✓ BarrierDebugger for hang detection")
    print("  ✓ Multiple observers working together")
    print("  ✓ Error handling and recording")
    print("\nNext Steps:")
    print("  • Check stored runs: SQLiteStorage('/tmp/justpipe_demo')")
    print("  • Query events: storage.get_events(run_id)")
    print("  • list all runs: storage.list_runs()")
    print()


if __name__ == "__main__":
    asyncio.run(main())
