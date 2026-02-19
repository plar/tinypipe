# [12 Observability](../README.md#production-reliability)

Monitor, debug, and analyze pipeline execution with justpipe's comprehensive observability features.

## Key Concepts

1. **Real-time Logging**: EventLogger for colored console output with configurable log levels
2. **Persistent Storage**: `persist=True` writes runs to SQLite automatically
3. **Performance Metrics**: Built-in `RuntimeMetrics` on the FINISH event for step latencies, queue depth, and task counts
4. **Timeline Visualization**: ASCII, HTML, and Mermaid timeline diagrams
5. **CLI Tools**: Query and analyze runs from the command line
6. **Compare**: Compare performance differences between runs

## Quick Start

From the project root:

```bash
uv run python examples/12_observability/main.py
```

This runs a comprehensive demo showing all observability features in action.

## Examples

- **main.py** - Comprehensive overview of all observability features (start here!)
- **observers_demo.py** - Basic observability (debug=True, EventLogger, BarrierDebugger, persist=True)
- **metrics_demo.py** - Metrics and visualization (RuntimeMetrics, TimelineVisualizer, StateDiffTracker)
- **replay_demo.py** - Run comparison (compare_runs, format_comparison)
- **cli_workflow_demo.py** - Generate test data for CLI commands

## Key Features Demonstrated

### Basic Observability (observers_demo.py)
- **debug=True Parameter**: Simplest way to enable observability
- **EventLogger**: Real-time colored console output
- **persist=True**: Automatic SQLite persistence via internal observer
- **BarrierDebugger**: Detect hanging parallel execution
- **Multiple Observers**: Combine different observers together

### Metrics & Visualization (metrics_demo.py)
- **RuntimeMetrics**: Built-in step latencies, queue depth, and task counts from the FINISH event
- **TimelineVisualizer**: Generate ASCII, HTML, and Mermaid diagrams
- **StateDiffTracker**: Track state changes across pipeline steps
- **CLI Integration**: Query runs with `justpipe list`, `show`, `timeline`

### Compare (replay_demo.py)
- **compare_runs()**: Compare two runs to identify timing differences
- **format_comparison()**: Human-readable comparison output
- **SQLiteBackend**: Query persisted runs for analysis
- **CLI Compare**: Use `justpipe compare` to find performance regressions

## API Reference

### Observer Pattern

```python
from justpipe.observability import Observer

class MyObserver(Observer):
    async def on_pipeline_start(self, state, context, meta):
        """Called before pipeline execution starts."""
        pass

    async def on_event(self, state, context, meta, event):
        """Called for each event during execution."""
        pass

    async def on_pipeline_end(self, state, context, meta, duration_s):
        """Called after pipeline completes successfully."""
        pass

    async def on_pipeline_error(self, state, context, meta, error):
        """Called when pipeline fails."""
        pass
```

### EventLogger

```python
from justpipe.observability import EventLogger

# Configure log level
logger = EventLogger(
    level="INFO",                         # DEBUG, INFO, WARNING, ERROR
    sink=EventLogger.stderr_sink()        # Output sink
)

pipe.add_observer(logger)
```

### Persistence

```python
from justpipe import Pipe
from justpipe.storage.sqlite import SQLiteBackend

# persist=True enables automatic SQLite storage
pipe = Pipe(name="my_pipeline", persist=True)

# Query persisted data via SQLiteBackend
backend = SQLiteBackend("/path/to/runs.db")

runs = backend.list_runs()
events = backend.get_events(run_id)
run = backend.get_run(run_id)
```

### BarrierDebugger

```python
import time
from justpipe.observability import BarrierDebugger

debugger = BarrierDebugger(
    warn_after=10.0,   # Warning threshold in seconds
    clock=time.time     # Clock function
)

pipe.add_observer(debugger)
```

### Run Comparison

```python
from justpipe.observability import compare_runs, format_comparison
from justpipe.storage.sqlite import SQLiteBackend

backend = SQLiteBackend("/path/to/runs.db")

run1 = backend.get_run(run1_id)
run2 = backend.get_run(run2_id)
events1 = backend.get_events(run1_id)
events2 = backend.get_events(run2_id)

comparison = compare_runs(run1, events1, run2, events2)
print(format_comparison(comparison))
```

## Event Types

The observability system tracks the following event types:

- **Pipeline Lifecycle**: `START`, `FINISH`, `SUSPEND` (FINISH carries structured status; schema version in `EVENT_SCHEMA_VERSION`)
- **Step Execution**: `STEP_START`, `STEP_END`, `STEP_ERROR`, `TOKEN`
- **Parallel Execution**: `BARRIER_WAIT`, `BARRIER_RELEASE`, `MAP_START`, `MAP_WORKER`, `MAP_COMPLETE`
- **State Tracking**: `STATE_CHANGE`

## Event.meta

`Event.meta` carries scope-appropriate metadata:

- **STEP_END / STEP_ERROR**: Step-scoped meta (user data + `framework` timing)
- **FINISH**: Run-scoped meta from `ctx.meta.run`

Step meta `framework` key includes `duration_s`, `attempt`, and `status`.

## Storage Structure

When using `persist=True`, data is stored under `JUSTPIPE_STORAGE_PATH` (default `~/.justpipe`):

```
~/.justpipe/
└── <pipeline_name>/
    └── runs.db              # SQLite database
        ├── runs table       # Pipeline run metadata
        └── events table     # Event stream
```

## Performance Impact

With all observers enabled:
- **EventLogger**: ~1-2% overhead
- **persist=True**: ~3-5% overhead
- **BarrierDebugger**: <1% overhead

**Total**: <10% overhead

Observers are optional and have zero overhead when not used.

## See Also

- **Tests**: `tests/unit/observability/` - Observer test suite
- **CLI README**: `justpipe/cli/README.md` - CLI commands documentation

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    subgraph parallel_n2[Parallel]
        direction LR
        n0["Analyze Sentiment"]
        n1["Count Words"]
    end

    n2["Parse Input"]
    End(["■ End"])
    n0 --> End
    n1 --> End

    Start --> n2
    n2 --> n0
    n2 --> n1
    class n0,n1,n2 step;
    class Start,End startEnd;

    %% Styling
    classDef default fill:#f8f9fa,stroke:#dee2e6,stroke-width:1px;
    classDef step fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1;
    classDef streaming fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef map fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef switch fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef sub fill:#f1f8e9,stroke:#558b2f,stroke-width:2px,color:#33691e;
    classDef isolated fill:#fce4ec,stroke:#c2185b,stroke-width:2px,stroke-dasharray: 5 5,color:#880e4f;
    classDef startEnd fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20;
```

## See Also

- **[14 Testing Harness](../14_testing_harness)**: Use observability concepts in your unit tests.
- **[09 Middleware](../09_middleware)**: Build custom loggers.
