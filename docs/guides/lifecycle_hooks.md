# Lifecycle Hooks

Lifecycle hooks allow you to execute logic at specific points in the pipeline's runtime journey. They are essential for managing external resources like database connections, API clients, or temporary files.

## Available Hooks

### `@pipe.on_startup`
Runs **before** any functional steps are executed.
- **Purpose**: Initialize connections, load configuration, or prepare context.
- **Failures**: If a startup hook fails, the pipeline terminates immediately with a `FAILED` status and `failure_kind=startup`.

### `@pipe.on_shutdown`
Runs **after** the pipeline finishes, regardless of its outcome (success, failure, timeout, or cancellation).
- **Purpose**: Close connections, clean up resources, or log final metrics.
- **Failures**: If a shutdown hook fails, the error is recorded in the `FINISH` event's `errors` list, but it does not change the high-level status of the pipeline (to ensure the original error is preserved).

### `@pipe.on_error`
A global recovery handler.
- **Purpose**: Log errors, perform fallback logic, or decide whether to `Retry()`, `Skip()`, or `Raise()` an exception.

## Using Context for Resources

The `Context` object is the recommended place to store resources initialized in hooks.

```python
from dataclasses import dataclass, field
from justpipe import Pipe

@dataclass
class MyContext:
    db: dict = field(default_factory=dict)

pipe = Pipe(State, MyContext)

@pipe.on_startup
async def connect_db(ctx: MyContext):
    print("Connecting...")
    ctx.db["client"] = "connected"

@pipe.on_shutdown
async def disconnect_db(ctx: MyContext):
    print("Disconnecting...")
    ctx.db.clear()

@pipe.step()
async def fetch(ctx: MyContext):
    # Use the resource
    return ctx.db["client"]
```

## Execution Order

1.  **Event**: `START`
2.  **Hooks**: All `@pipe.on_startup` hooks (in order of registration).
3.  **Steps**: Functional pipeline execution.
4.  **Hooks**: All `@pipe.on_shutdown` hooks (in order of registration).
5.  **Event**: `FINISH`

For a full runnable example, see **[Example 10: Lifecycle Hooks](../../examples/10_lifecycle_hooks)**.
