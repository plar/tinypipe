# tinypipe

Your code is the graph. Async, streaming pipelines for AI.

## Installation

```bash
pip install tinypipe

# With retry support (tenacity)
pip install "tinypipe[retry]"
```

## Quick Start

```python
import asyncio
from dataclasses import dataclass
from tinypipe import Pipe, EventType

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
from tinypipe import Next

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
pip install "tinypipe[retry]"
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

tinypipe doesn't include built-in timeout to keep the API simple. Use Python's `asyncio.timeout()` directly:

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

## License

MIT
