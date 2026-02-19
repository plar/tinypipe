# Terminal Semantics

Every execution of a justpipe pipeline, regardless of its outcome, concludes with a single terminal event: `EventType.FINISH`. This event provides a structured, diagnostic-rich summary of the entire run.

## Terminal Statuses

The `PipelineTerminalStatus` classifies the high-level outcome of the run:

| Status | Meaning |
| :--- | :--- |
| `SUCCESS` | The pipeline reached all terminal nodes without unhandled errors. |
| `FAILED` | An error occurred in a step, hook, or the framework itself. |
| `TIMEOUT` | The execution exceeded the `timeout` parameter provided to `run()`. |
| `CANCELLED` | The `CancellationToken` was triggered during execution. |
| `CLIENT_CLOSED` | The consumer stopped iterating the async generator (e.g., via `break` or `aclose()`). |

## Failure Classification

When a pipeline fails (`status=FAILED`), justpipe automatically categorizes the failure to help you distinguish between your code, external dependencies, and framework issues.

### Failure Kind
Identifies **where** in the lifecycle the failure occurred:
- `validation`: Graph integrity issues found at startup.
- `startup`: An error in an `@pipe.on_startup` hook.
- `step`: An unhandled exception in a functional step.
- `shutdown`: An error in an `@pipe.on_shutdown` hook.
- `infra`: An internal framework error or state machine violation.

### Failure Source
Identifies **who** is likely responsible:
- `user_code`: Exceptions raised directly in your steps or hooks.
- `framework`: Logic errors within justpipe.
- `external_dep`: Errors from third-party libraries (e.g., `openai`, `httpx`).

### Customizing Attribution
You can customize how failures are classified by providing a `FailureClassificationConfig`:

```python
from justpipe import Pipe
from justpipe.types import FailureClassificationConfig, FailureSource

def my_classifier(ctx):
    if "DatabaseError" in str(ctx.error):
        return FailureSource.EXTERNAL_DEP
    return None # Fallback to framework defaults

pipe = Pipe(
    State,
    failure_classification=FailureClassificationConfig(
        source_classifier=my_classifier,
        external_dependency_prefixes=("my_custom_lib",)
    )
)
```

## The Termination Payload

The `FINISH` event carries a `PipelineEndData` payload with the following fields:

| Field | Description |
| :--- | :--- |
| `status` | The `PipelineTerminalStatus` (Success, Failed, etc.). |
| `duration_s` | Total wall-clock time of the run. |
| `failed_step` | The name of the step that caused the failure (if `failure_kind=step`). |
| `errors` | A list of `FailureRecord` objects containing the full exception chain. |
| `metrics` | A snapshot of performance data (task counts, queue depth, step latencies). |

Run-scope user metadata (from `ctx.meta.run`) is carried on the FINISH event's `meta` field, not the `PipelineEndData` payload. See the [Observability Guide](./observability.md) for details.

## Lifecycle Invariants

1.  **Single Finish**: Exactly one `FINISH` event is emitted per `run()`.
2.  **Order of Operations**:
    *   For timeouts: `TIMEOUT` event → `FINISH` event.
    *   For cancellation: `CANCELLED` event → `FINISH` event.
3.  **Guaranteed Shutdown**: Shutdown hooks (`@pipe.on_shutdown`) are guaranteed to run before the `FINISH` event is emitted, even if the pipeline failed or timed out.
4.  **Transport Abort**: If the client calls `aclose()` on the stream, shutdown hooks still run for cleanup, but the `FINISH` event is not emitted to the closed transport.

For a complete list of all events emitted during a run, see the [Observability Guide](./observability.md).