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

pipe = Pipe()

@pipe.step(to="respond")
async def greet(state):
    state.message = "Hello"

@pipe.step()
async def respond(state):
    yield f"{state.message}, World!"

async def main():
    state = State()
    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            print(event.data)  # "Hello, World!"

asyncio.run(main())
```

## Features

- **Zero dependencies** - Core library has no required dependencies
- **Async-first** - Built on asyncio for non-blocking execution
- **Streaming** - Yield tokens from any step using async generators
- **Type-safe** - Full generic type support with `Pipe[StateT, ContextT]`
- **Smart injection** - Automatic state/context injection based on parameter names or types
- **Parallel execution** - Fan-out to multiple steps with implicit barrier synchronization
- **Dynamic routing** - Return `Next("step_name")` for runtime branching
- **Middleware** - Extensible with retry, logging, or custom middleware
- **Visualization** - Generate Mermaid diagrams with `pipe.graph()`

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

## Parallel Execution

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
    # Runs after BOTH fetch_a and fetch_b complete
    state.result = state.a + state.b
```

## Dynamic Routing

```python
from justpipe import Next

@pipe.step("decide")
async def decide(state):
    if state.value > 0:
        return Next("positive_handler")
    return Next("negative_handler")
```

## Streaming Tokens

```python
@pipe.step("stream")
async def stream(state):
    for chunk in generate_response():
        yield chunk  # Yields TOKEN events
```

## Retry with Tenacity

```bash
pip install "justpipe[retry]"
```

```python
@pipe.step("flaky_api", retries=3)
async def flaky_api(state):
    response = await unreliable_api_call()
    state.data = response
```

## Lifecycle Hooks

```python
@pipe.on_startup
async def setup(context):
    context.db = await connect_to_database()

@pipe.on_shutdown
async def cleanup(context):
    await context.db.close()
```

## Event Types

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
        case EventType.FINISH:
            print("Pipeline finished")
```

## Timeout Handling

justpipe doesn't include built-in timeout to keep the API simple. Use Python's `asyncio.timeout()` directly:

```python
import asyncio

@pipe.step("api_call")
async def api_call(state):
    try:
        async with asyncio.timeout(5.0):
            state.result = await slow_external_api()
    except TimeoutError:
        state.result = None
        state.error = "API timeout"
```

For streaming steps, wrap the slow operation:

```python
@pipe.step("stream_with_timeout")
async def stream_with_timeout(state):
    yield "Starting..."
    try:
        async with asyncio.timeout(10.0):
            result = await slow_operation()
        yield f"Result: {result}"
    except TimeoutError:
        yield "Operation timed out"
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

## Maintenance

This repository is configured with GitHub Actions to ensure high code quality:
- **CI**: Runs on every push/PR to `main`, executing Ruff, Mypy, and Pytest.
- **Coverage**: Reports are generated and tracked to maintain >80% coverage.

## License

MIT
