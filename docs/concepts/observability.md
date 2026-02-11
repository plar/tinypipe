# Observability and Event System

justpipe is built with observability as a first-class citizen. Every transition, state change, and functional milestone in a pipeline execution emits a structured `Event` into an async stream.

## The Event Schema

The current authoritative schema version is `EVENT_SCHEMA_VERSION = "1.0"`.

### Event Fields

Each `Event` object contains the following fields:

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `EventType` | The category of the event (e.g., `START`, `STEP_START`, `TOKEN`). |
| `stage` | `str` | The logical name of the node that produced the event (or `"system"`). |
| `payload` | `Any` | Free-form data associated with the event (see below for `FINISH`). |
| `timestamp` | `float` | Wall-clock time (seconds since epoch) when the event was produced. |
| `run_id` | `str` | Stable ID for the root event stream (one `pipe.run()` call). |
| `origin_run_id` | `str` | ID of the specific run (potentially a sub-pipeline) where the event was born. |
| `parent_run_id` | `str \| None` | ID of the immediate parent run that forwarded this event. |
| `seq` | `int` | Monotonic sequence number within the current `run_id`. |
| `node_kind` | `NodeKind` | The runtime source type: `system`, `step`, `map`, `switch`, `sub`, or `barrier`. |
| `invocation_id` | `str` | Unique ID for a single functional execution attempt of a step. |
| `meta` | `dict \| None` | Optional extension bag for cross-cutting metadata. |

## Terminal Diagnostics (The FINISH Event)

The pipeline execution always concludes with exactly one `EventType.FINISH` event. Its `payload` is always a `PipelineEndData` object, providing exhaustive diagnostics for the run.

### PipelineEndData Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `PipelineTerminalStatus` | High-level outcome: `SUCCESS`, `FAILED`, `TIMEOUT`, `CANCELLED`, or `CLIENT_CLOSED`. |
| `duration_s` | `float` | Total execution time in seconds. |
| `failure_kind` | `FailureKind` | Lifecycle area of failure: `validation`, `startup`, `step`, `shutdown`, or `infra`. |
| `failure_source` | `FailureSource` | Attribution: `user_code`, `framework`, or `external_dep`. |
| `failed_step` | `str \| None` | The name of the step that caused the terminal failure, if any. |
| `errors` | `list[FailureRecord]` | Full chain of failures recorded during the run. |
| `metrics` | `RuntimeMetrics \| None` | Built-in performance counters (queue depth, task counts, step latencies). |

## Lineage Tracking

justpipe uses three distinct IDs to provide perfect traceability across nested pipelines and concurrent tasks:

1.  **`run_id`**: Identifies the overall stream. When you iterate over `pipe.run(...)`, every event yielded will share the same `run_id`.
2.  **`origin_run_id`**: When a sub-pipeline runs, it produces its own events. When these are forwarded to the parent stream, `origin_run_id` points to the sub-pipeline's specific run session.
3.  **`parent_run_id`**: Points to the immediate caller. In deep nesting, this allows you to reconstruct the full calling hierarchy.

## Using Observers

While you can consume events directly from the `pipe.run()` generator, the **Observer Pattern** is recommended for cross-cutting concerns like logging or persistent storage.

### Implementing an Observer

```python
from justpipe.observability import Observer
from justpipe.types import Event, EventType

class MyAnalyticsObserver(Observer):
    async def on_event(self, event: Event, state):
        if event.type == EventType.TOKEN:
            # Send tokens to an external monitor
            print(f"[{event.origin_run_id}] Streamed: {event.payload}")

pipe.add_observer(MyAnalyticsObserver())
```

### Observer Best Practices

- **Handle Unknown Types**: Observers should be resilient to new `EventType` values.
- **Prefer Structured Data**: Use the `status` enum in the `FINISH` payload rather than parsing error strings.
- **Check Version**: If your observer makes strict assumptions about event shapes, verify `EVENT_SCHEMA_VERSION`.