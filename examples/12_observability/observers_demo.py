"""Basic observability features demo for justpipe.

This example demonstrates:
1. debug=True convenience parameter
2. EventLogger observer
3. BarrierDebugger observer
4. persist=True for automatic SQLite persistence
5. Multiple observers working together
"""

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

from justpipe import Pipe
from justpipe.observability import EventLogger, BarrierDebugger
from justpipe.storage.sqlite import SQLiteBackend


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

    @pipe.step("parse", to="count")
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

    @pipe.step("parse", to="process")
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


# Example 3: Persistence with persist=True
async def example_persistence(tmp_dir: str):
    """Store pipeline runs using persist=True."""
    print("\n" + "=" * 60)
    print("Example 3: Persistence (persist=True)")
    print("=" * 60)

    # persist=True writes runs to SQLite under JUSTPIPE_STORAGE_PATH
    pipe: Pipe[State, None] = Pipe(name="stored_pipeline", persist=True)
    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))

    @pipe.step("parse", to="count")
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

    # Query the persisted runs
    db_files = list(Path(tmp_dir).rglob("runs.db"))
    if db_files:
        backend = SQLiteBackend(db_files[0])
        runs = backend.list_runs()
        print(f"\n  Runs in storage: {len(runs)}")
        if runs:
            print(f"  Latest status: {runs[0].status.value}")
            print(f"  Duration: {runs[0].duration.total_seconds():.3f}s")


# Example 4: Multiple observers
async def example_multiple_observers():
    """Use multiple observers together."""
    print("\n" + "=" * 60)
    print("Example 4: Multiple Observers")
    print("=" * 60)

    pipe: Pipe[State, None] = Pipe(name="multi_observer_pipeline", persist=True)

    # Add multiple observers
    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))
    pipe.add_observer(BarrierDebugger(warn_after=5.0, clock=time.time))

    @pipe.step("parse", to="count")
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

    pipe: Pipe[State, None] = Pipe(name="error_pipeline", persist=True)
    pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))

    @pipe.step("parse", to="fail")
    async def parse(state: State):
        state.text = "hello world"
        state.words = state.text.split()

    @pipe.step("fail")
    async def fail(state: State):
        raise ValueError("Intentional error for demo")

    state = State()
    async for event in pipe.run(state):
        pass

    print("\n  Pipeline completed (errors are captured in FINISH event)")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Basic Features")
    print("=" * 80)

    # Use a temp dir for persistence so we don't pollute ~/.justpipe
    tmp_dir = "/tmp/justpipe_observers_demo"
    os.environ["JUSTPIPE_STORAGE_PATH"] = tmp_dir

    await example_simple_debug()
    await example_custom_logger()
    await example_persistence(tmp_dir)
    await example_multiple_observers()
    await example_error_handling()

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("  debug=True convenience parameter")
    print("  EventLogger with configurable log levels")
    print("  persist=True for automatic SQLite persistence")
    print("  BarrierDebugger for hang detection")
    print("  Multiple observers working together")
    print("  Error handling and recording")
    print(f"\nPersisted runs stored in: {tmp_dir}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
