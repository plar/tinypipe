"""Observability example - Monitor, debug, and analyze pipeline execution.

This example demonstrates justpipe's comprehensive observability features:
1. Real-time logging with EventLogger
2. Automatic persistence with persist=True
3. Performance metrics with MetricsCollector
4. Timeline visualization
5. CLI tools for querying and analysis
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from justpipe import Pipe
from justpipe.observability import (
    EventLogger,
    MetricsCollector,
    TimelineVisualizer,
)


@dataclass
class DocumentState:
    """State for document processing pipeline."""

    raw: str = ""
    parsed: str = ""
    word_count: int = 0
    sentiment: str = ""


# Create pipeline with multiple observers and persistence enabled
pipe = Pipe(DocumentState, name="document_processor", persist=True)

# Real-time logging
pipe.add_observer(EventLogger(level="INFO", sink=EventLogger.stderr_sink()))

# Metrics collection
metrics = MetricsCollector(clock=time.time)
pipe.add_observer(metrics)

# Timeline visualization
timeline = TimelineVisualizer()
pipe.add_observer(timeline)


@pipe.step(to=["count_words", "analyze_sentiment"])
async def parse_input(state: DocumentState):
    """Parse and normalize the input text."""
    await asyncio.sleep(0.01)  # Simulate work
    state.parsed = state.raw.upper()


@pipe.step()
async def count_words(state: DocumentState):
    """Count words in the document."""
    await asyncio.sleep(0.02)  # Simulate work
    state.word_count = len(state.parsed.split())


@pipe.step()
async def analyze_sentiment(state: DocumentState):
    """Analyze document sentiment."""
    await asyncio.sleep(0.015)  # Simulate work
    # Simple sentiment analysis
    positive_words = ["good", "great", "excellent", "happy"]
    negative_words = ["bad", "terrible", "awful", "sad"]

    words = state.parsed.lower().split()
    pos_count = sum(1 for w in words if w in positive_words)
    neg_count = sum(1 for w in words if w in negative_words)

    if pos_count > neg_count:
        state.sentiment = "positive"
    elif neg_count > pos_count:
        state.sentiment = "negative"
    else:
        state.sentiment = "neutral"


async def main():
    """Run the observability demo."""
    print("=" * 70)
    print("JUSTPIPE OBSERVABILITY DEMO")
    print("=" * 70)
    print()

    # Initialize state
    state = DocumentState(raw="This is a great example of pipeline observability")

    print("Running pipeline with observability enabled...")
    print(f"Input: '{state.raw}'")
    print()

    # Run the pipeline
    async for event in pipe.run(state):
        pass

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    # Show final state
    print("Final State:")
    print(f"  Parsed: {state.parsed}")
    print(f"  Word Count: {state.word_count}")
    print(f"  Sentiment: {state.sentiment}")
    print()

    # Show performance metrics
    print("Performance Metrics:")
    bottleneck = metrics.get_bottleneck()
    bottleneck_pct = metrics.get_bottleneck_percentage()
    data = metrics.to_dict()
    print(f"  Total Duration: {data['total_duration']:.3f}s")
    print(f"  Steps Executed: {data['steps_executed']}")
    print(f"  Bottleneck: {bottleneck} ({bottleneck_pct:.1f}% of time)")
    print()

    # Save timeline visualization
    timeline_file = Path(__file__).parent / "timeline.txt"
    with open(timeline_file, "w") as f:
        f.write(timeline.render_ascii())
    print(f"Timeline saved to: {timeline_file}")
    print()

    # Save visualization
    from examples.utils import save_graph

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")

    # Show CLI commands
    print("=" * 70)
    print("CLI COMMANDS")
    print("=" * 70)
    print()
    print("Query runs with CLI commands:")
    print("  justpipe list")
    print("  justpipe list --pipeline document_processor")
    print("  justpipe list --status success")
    print()
    print("Compare runs:")
    print("  justpipe compare <run1> <run2>")
    print()

    # Show statistics
    print("Pipeline Statistics:")
    print("  justpipe stats --pipeline document_processor")
    print()

    print("=" * 70)
    print("For detailed examples, see:")
    print("  - observers_demo.py - Basic observability features")
    print("  - metrics_demo.py - Metrics and visualization")
    print("  - replay_demo.py - Replay and comparison")
    print("  - cli_workflow_demo.py - Generate test data for CLI")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
