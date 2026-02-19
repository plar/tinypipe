"""Metrics and visualization demo for justpipe.

This example demonstrates:
1. RuntimeMetrics - Built-in performance metrics from FINISH event
2. TimelineVisualizer - Execution timeline visualization
3. StateDiffTracker - State change tracking and diffs
4. persist=True + CLI workflow
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from justpipe import Pipe, EventType
from justpipe.types import PipelineEndData
from justpipe.observability import (
    EventLogger,
    TimelineVisualizer,
    StateDiffTracker,
)
from justpipe.storage.sqlite import SQLiteBackend


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


# Example 1: RuntimeMetrics from FINISH event
async def example_runtime_metrics():
    """Access built-in runtime metrics from the FINISH event."""
    print("\n" + "=" * 60)
    print("Example 1: RuntimeMetrics from FINISH Event")
    print("=" * 60)

    pipe: Pipe[State, None] = Pipe(name="metrics_demo")

    @pipe.step("parse", to="count")
    async def parse(state: State):
        state.text = "hello world hello python python python"
        state.words = state.text.split()
        await asyncio.sleep(0.01)

    @pipe.step("count", to="finalize")
    async def count(state: State):
        for word in state.words:
            state.word_counts[word] = state.word_counts.get(word, 0) + 1
        await asyncio.sleep(0.05)

    @pipe.step("finalize")
    async def finalize(state: State):
        state.processed = True
        await asyncio.sleep(0.005)

    state = State()
    end_data: PipelineEndData | None = None
    async for event in pipe.run(state):
        if event.type == EventType.FINISH:
            end_data = event.payload

    if end_data and end_data.metrics:
        rm = end_data.metrics
        print(f"\nDuration: {end_data.duration_s:.3f}s")
        print(f"Steps: {list(rm.step_latency.keys())}")
        for name, timing in rm.step_latency.items():
            print(f"  {name}: {timing.total_s:.3f}s ({timing.count} invocations)")
        print(f"Tokens: {rm.tokens}")
        print(f"Events: {rm.events}")


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
    timeline = TimelineVisualizer()
    tracker = StateDiffTracker()
    logger = EventLogger(level="INFO", sink=EventLogger.stderr_sink())

    pipe: Pipe[State, None] = Pipe(name="comprehensive_demo")
    pipe.add_observer(logger)
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

    print("\n--- Timeline ---")
    print(timeline.render_ascii())

    print("\n--- State Changes ---")
    print(tracker.summary())


# Example 5: Storage + CLI workflow
async def example_storage_and_cli(tmp_dir: str):
    """Demonstrate persist=True and CLI workflow."""
    print("\n" + "=" * 60)
    print("Example 5: Storage + CLI Workflow")
    print("=" * 60)

    pipe: Pipe[State, None] = Pipe(name="cli_workflow_demo", persist=True)
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

    # Query the persisted data
    db_files = list(Path(tmp_dir).rglob("runs.db"))
    if db_files:
        backend = SQLiteBackend(db_files[0])
        runs = backend.list_runs()
        print(f"\nTotal runs in storage: {len(runs)}")

    print("\nYou can now use CLI tools:")
    print(f"  JUSTPIPE_STORAGE_PATH={tmp_dir} justpipe list")
    print(f"  JUSTPIPE_STORAGE_PATH={tmp_dir} justpipe stats")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("JUSTPIPE OBSERVABILITY DEMO - Metrics & Visualization")
    print("=" * 80)

    tmp_dir = "/tmp/justpipe_metrics_demo"
    os.environ["JUSTPIPE_STORAGE_PATH"] = tmp_dir

    await example_runtime_metrics()
    await example_timeline_visualizer()
    await example_state_diff_tracker()
    await example_all_together()
    await example_storage_and_cli(tmp_dir)

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nFeatures Demonstrated:")
    print("  RuntimeMetrics - Built-in performance analysis")
    print("  TimelineVisualizer - ASCII/HTML/Mermaid timelines")
    print("  StateDiffTracker - State change tracking")
    print("  Multiple observers working together")
    print("  persist=True + CLI workflow")
    print("\nCLI Commands Available:")
    print(f"  JUSTPIPE_STORAGE_PATH={tmp_dir} justpipe list")
    print(f"  JUSTPIPE_STORAGE_PATH={tmp_dir} justpipe stats")
    print()


if __name__ == "__main__":
    asyncio.run(main())
