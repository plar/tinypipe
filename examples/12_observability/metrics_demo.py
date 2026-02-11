"""Metrics and visualization demo for justpipe.

This example demonstrates:
1. MetricsCollector - Performance metrics and bottleneck detection
2. TimelineVisualizer - Execution timeline visualization
3. StateDiffTracker - State change tracking and diffs
4. CLI tools - list, show, timeline commands
"""

import asyncio
import time
from dataclasses import dataclass

from justpipe import Pipe
from justpipe.observability import (
    EventLogger,
    MetricsCollector,
    TimelineVisualizer,
    StateDiffTracker,
    StorageObserver,
)
from justpipe.storage import SQLiteStorage


@dataclass
class State:
    """Example state for document processing pipeline."""

    text: str = ""
    words: list = None
    word_counts: dict = None
    processed: bool = False

    def __post_init__(self):
        if self.words is None:
            self.words = []
        if self.word_counts is None:
            self.word_counts = {}


# Example 1: MetricsCollector
async def example_metrics_collector():
    """Collect and analyze performance metrics."""
    print("\n" + "=" * 60)
    print("Example 1: MetricsCollector")
    print("=" * 60)

    metrics = MetricsCollector(clock=time.time)

    pipe: Pipe[State, None] = Pipe(name="metrics_demo")
    pipe.add_observer(metrics)

    @pipe.step("parse", to="count")
    async def parse(state: State):
        state.text = "hello world hello python python python"
        state.words = state.text.split()
        # Simulate some work
        await asyncio.sleep(0.01)

    @pipe.step("count", to="finalize")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1
        # This step is slower (bottleneck)
        await asyncio.sleep(0.05)

    @pipe.step("finalize")
    async def finalize(state: State):
        state.processed = True
        await asyncio.sleep(0.005)

    state = State()
    async for _ in pipe.run(state):
        pass

    # Print metrics summary
    print("\n" + metrics.summary())

    # Show bottleneck
    print(f"Identified bottleneck: {metrics.get_bottleneck()}")
    print(f"Bottleneck percentage: {metrics.get_bottleneck_percentage():.1f}%")

    # Export to dict
    data = metrics.to_dict()
    print(f"\nExported metrics keys: {list(data.keys())}")


# Example 2: TimelineVisualizer
async def example_timeline_visualizer():
    """Visualize execution timeline."""
    print("\n" + "=" * 60)
    print("Example 2: TimelineVisualizer")
    print("=" * 60)

    timeline = TimelineVisualizer()

    pipe: Pipe[State, None] = Pipe(name="timeline_demo")
    pipe.add_observer(timeline)

    @pipe.step("parse", to="count")
    async def parse(state: State):
        state.text = "hello world"
        state.words = state.text.split()
        await asyncio.sleep(0.01)

    @pipe.step("count", to="finalize")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1
        await asyncio.sleep(0.03)

    @pipe.step("finalize")
    async def finalize(state: State):
        state.processed = True
        await asyncio.sleep(0.005)

    state = State()
    async for _ in pipe.run(state):
        pass

    # Print ASCII timeline
    print(timeline.render_ascii())

    # Save HTML timeline
    html = timeline.render_html()
    html_file = "/tmp/timeline_demo.html"
    with open(html_file, "w") as f:
        f.write(html)
    print(f"HTML timeline saved to: {html_file}")

    # Save Mermaid diagram
    mermaid = timeline.render_mermaid()
    mermaid_file = "/tmp/timeline_demo.mmd"
    with open(mermaid_file, "w") as f:
        f.write(mermaid)
    print(f"Mermaid diagram saved to: {mermaid_file}")


# Example 3: StateDiffTracker
async def example_state_diff_tracker():
    """Track and compare state changes."""
    print("\n" + "=" * 60)
    print("Example 3: StateDiffTracker")
    print("=" * 60)

    tracker = StateDiffTracker()

    pipe: Pipe[State, None] = Pipe(name="statediff_demo")
    pipe.add_observer(tracker)

    @pipe.step("parse", to="count")
    async def parse(state: State):
        state.text = "hello world hello"
        state.words = state.text.split()

    @pipe.step("count", to="finalize")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1

    @pipe.step("finalize")
    async def finalize(state: State):
        state.processed = True

    state = State()
    async for _ in pipe.run(state):
        pass

    # Print summary of all changes
    print(tracker.summary())

    # Compare specific steps
    print(tracker.diff("__start__", "parse"))
    print(tracker.diff("parse", "count"))
    print(tracker.diff("count", "finalize"))

    # Export to JSON
    json_data = tracker.export_json()
    print(f"\nExported JSON length: {len(json_data)} characters")


# Example 4: All observers together
async def example_all_together():
    """Use all observers together."""
    print("\n" + "=" * 60)
    print("Example 4: All Observers Together")
    print("=" * 60)

    # Create all observers
    metrics = MetricsCollector(clock=time.time)
    timeline = TimelineVisualizer()
    tracker = StateDiffTracker()
    logger = EventLogger(level="INFO", sink=EventLogger.stderr_sink())

    pipe: Pipe[State, None] = Pipe(name="comprehensive_demo")
    pipe.add_observer(logger)
    pipe.add_observer(metrics)
    pipe.add_observer(timeline)
    pipe.add_observer(tracker)

    @pipe.step("parse", to="count")
    async def parse(state: State):
        state.text = "hello world hello python"
        state.words = state.text.split()

    @pipe.step("count", to="finalize")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1
        await asyncio.sleep(0.02)  # Bottleneck

    @pipe.step("finalize")
    async def finalize(state: State):
        state.processed = True

    state = State()
    async for _ in pipe.run(state):
        pass

    print("\n--- Metrics ---")
    print(metrics.summary())

    print("\n--- Timeline ---")
    print(timeline.render_ascii())

    print("\n--- State Changes ---")
    print(tracker.summary())


# Example 5: Storage + CLI workflow
async def example_storage_and_cli():
    """Demonstrate storage and CLI workflow."""
    print("\n" + "=" * 60)
    print("Example 5: Storage + CLI Workflow")
    print("=" * 60)

    storage = SQLiteStorage("/tmp/justpipe_phase2_demo")

    pipe: Pipe[State, None] = Pipe(name="cli_workflow_demo")
    storage_obs = StorageObserver(storage)
    pipe.add_observer(storage_obs)
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
    async for _ in pipe.run(state):
        pass

    run_id = storage_obs.get_run_id()
    print(f"\n✓ Run stored with ID: {run_id}")

    # list all runs
    runs = await storage.list_runs()
    print(f"\nTotal runs in storage: {len(runs)}")

    print("\nYou can now use CLI tools:")
    print("  justpipe list")
    print(f"  justpipe show {run_id}")
    print(f"  justpipe timeline {run_id}")
    print("\nStorage location: /tmp/justpipe_phase2_demo")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Metrics & Visualization")
    print("=" * 80)

    await example_metrics_collector()
    await example_timeline_visualizer()
    await example_state_diff_tracker()
    await example_all_together()
    await example_storage_and_cli()

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nFeatures Demonstrated:")
    print("  ✓ MetricsCollector - Performance analysis")
    print("  ✓ TimelineVisualizer - ASCII/HTML/Mermaid timelines")
    print("  ✓ StateDiffTracker - State change tracking")
    print("  ✓ Multiple observers working together")
    print("  ✓ Storage + CLI workflow")
    print("\nCLI Commands Available:")
    print("  export JUSTPIPE_STORAGE_DIR=/tmp/justpipe_phase2_demo")
    print("  justpipe list")
    print("  justpipe show <run-id>")
    print("  justpipe timeline <run-id> --format ascii")
    print()


if __name__ == "__main__":
    asyncio.run(main())
