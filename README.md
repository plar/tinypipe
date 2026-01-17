# justpipe

[![CI](https://github.com/plar/justpipe/actions/workflows/ci.yml/badge.svg)](https://github.com/plar/justpipe/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/plar/justpipe/badges/coverage.svg)](https://github.com/plar/justpipe/actions)
[![PyPI](https://img.shields.io/pypi/v/justpipe.svg)](https://pypi.org/project/justpipe/)

Your code is the graph. Async, streaming pipelines for AI.

## Installation

```bash
pip install justpipe

# With retry support (tenacity)
pip install "justpipe[retry]"
```

## Quick Start

```python
import asyncio
from dataclasses import dataclass
from justpipe import Pipe, EventType

@dataclass
class State:
    message: str = ""

# Type-safe pipeline definition
pipe = Pipe[State, None]()

@pipe.step(to="respond")
async def greet(state: State):
    state.message = "Hello"

@pipe.step()
async def respond(state: State):
    yield f"{state.message}, World!"

async def main():
    state = State()
    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            print(event.data)  # "Hello, World!"

asyncio.run(main())
```

## Features

- **Python 3.12+** - Leveraging modern `asyncio.TaskGroup` and generics.
- **Zero dependencies** - Core library has no required dependencies.
- **Async-first** - Built on `asyncio` for non-blocking execution.
- **Streaming** - Yield tokens from any step using async generators.
- **Type-safe** - Full generic type support with `Pipe[StateT, ContextT]`.
- **Smart injection** - Automatic state/context injection based on parameter names (`state`, `ctx`) or types.
- **Parallel execution** - Fan-out to multiple steps with implicit barrier synchronization.
- **Dynamic routing** - Return `Next("step_name")` for runtime branching.
- **Dynamic Parallelism** - Return `Map(items=[...], target="step")` to spawn dynamic workers.
- **Composition** - Return `Run(pipe=sub, state=...)` to execute sub-pipelines.
- **Suspension** - Return `Suspend(reason=...)` to pause execution mid-flow.
- **Middleware** - Extensible with retry, logging, or custom middleware.
- **Visualization** - Generate Mermaid diagrams with `pipe.graph()`.

```mermaid
graph TD
    Start(["▶ Start"])

    subgraph parallel_n3[Parallel]
        direction LR
        n8["Search Knowledge Graph"]
        n9(["Search Vectors ⚡"])
        n10(["Search Web ⚡"])
    end

    n1["Build Context"]
    n3["Embed Query"]
    n4(["Format Output ⚡"])
    n5(["Generate Response ⚡"])
    n6["Parse Query"]
    n7["Rank Results"]
    End(["■ End"])

    Start --> n6
    n1 --> n5
    n3 --> n8
    n3 --> n9
    n3 --> n10
    n5 --> n4
    n6 --> n3
    n7 --> n1
    n8 --> n7
    n9 --> n7
    n10 --> n7
    n4 --> End

    subgraph utilities[Utilities]
        direction TB
        n0(["Analytics Logger ⚡"]):::isolated
        n2["Cache Manager"]:::isolated
    end

    %% Styling
    classDef default fill:#f8f9fa,stroke:#dee2e6,stroke-width:1px;
    classDef step fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1;
    classDef streaming fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef isolated fill:#fce4ec,stroke:#c2185b,stroke-width:2px,stroke-dasharray: 5 5,color:#880e4f;
    classDef startEnd fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20;
    class n1,n3,n6,n7,n8 step;
    class n10,n4,n5,n9 streaming;
    class n0,n2 isolated;
    class Start,End startEnd;
```

## Parallel Execution (DAG)

Static parallelism is defined by linking one step to multiple targets.

```python
@pipe.step("start", to=["fetch_a", "fetch_b"])
async def start(state):
    pass

@pipe.step("fetch_a", to="combine")
async def fetch_a(state):
    state.a = await fetch_from_api_a()

@pipe.step("fetch_b", to="combine")
async def fetch_b(state):
    state.b = await fetch_from_api_b()

@pipe.step("combine")
async def combine(state):
    # Implicit Barrier: Runs only after BOTH fetch_a and fetch_b complete
    state.result = state.a + state.b
```

## Dynamic Parallelism (Map)

Use `Map` to process a list of items in parallel.

```python
from justpipe import Map

@pipe.step("process_batch")
async def process_batch(state):
    # Spawns 'worker' step for each item in the list
    # 'target' must be a registered step name
    return Map(items=[1, 2, 3], target="worker")

@pipe.step("worker")
async def worker(item: int, state):
    # 'item' is injected automatically because it's not a state/context arg
    print(f"Processing {item}")
```

## Dynamic Routing

Use `Next` to change flow at runtime.

```python
from justpipe import Next

@pipe.step("decide")
async def decide(state):
    if state.value > 0:
        return Next("positive_handler")
    return Next("negative_handler")
```

## Suspension

Use `Suspend` to pause execution. The event stream will yield a `SUSPEND` event and then finish.

```python
from justpipe import Suspend

@pipe.step("validate")
async def validate(state):
    if not state.is_ready:
        return Suspend(reason="wait_for_human")
```

## Sub-pipelines

Compose complex workflows by running other pipelines.

```python
from justpipe import Run

sub_pipe = Pipe()
# ... define sub_pipe steps ...

@pipe.step("execute_sub")
async def execute_sub(state):
    # Executes the sub-pipeline with the current state (or a new one)
    # Events from sub_pipe are namespaced (e.g., "execute_sub:step_name")
    return Run(pipe=sub_pipe, state=state)
```

## Streaming Tokens

```python
@pipe.step("stream")
async def stream(state):
    for chunk in generate_response():
        yield chunk  # Yields TOKEN events
```

## Retry with Tenacity

justpipe has built-in support for `tenacity` if installed.

```bash
pip install "justpipe[retry]"
```

```python
@pipe.step("flaky_api", retries=3, retry_wait_min=0.1)
async def flaky_api(state):
    # Will automatically retry on exception
    response = await unreliable_api_call()
```

## Middleware

Middleware wraps every step execution. Useful for logging, tracing, or error handling.

```python
def logging_middleware(func, kwargs):
    async def wrapped(*args, **kw):
        print(f"Starting {func.__name__}")
        try:
            return await func(*args, **kw)
        finally:
            print(f"Finished {func.__name__}")
    return wrapped

pipe.add_middleware(logging_middleware)
```

## Lifecycle Hooks

Hooks are useful for managing external resources like database connections or API clients.

```python
@pipe.on_startup
async def setup(context):
    context.db = await connect_to_database()

@pipe.on_shutdown
async def cleanup(context):
    await context.db.close()
```

## Timeout Handling

You can specify a `timeout` (in seconds) for any step.

```python
@pipe.step("api_call", timeout=5.0)
async def api_call(state):
    # Raises TimeoutError if it takes longer than 5 seconds
    await slow_external_api()
```

## Event Types

The event stream allows you to monitor and react to the pipeline execution.

```python
async for event in pipe.run(state, context):
    match event.type:
        case EventType.START:
            print("Pipeline started")
        case EventType.STEP_START:
            print(f"Step {event.stage} starting")
        case EventType.TOKEN:
            print(f"Token: {event.data}")
        case EventType.STEP_END:
            print(f"Step {event.stage} finished")
        case EventType.ERROR:
            print(f"Error: {event.data}")
        case EventType.SUSPEND:
             print(f"Suspended: {event.data}")
        case EventType.FINISH:
            print("Pipeline finished")
```

## Development

**justpipe** uses `uv` for dependency management.

```bash
# Install development dependencies
uv sync --all-extras --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checks
uv run mypy justpipe
```

## License

MIT