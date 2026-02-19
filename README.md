# justpipe

[![CI](https://github.com/plar/justpipe/actions/workflows/ci.yml/badge.svg)](https://github.com/plar/justpipe/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/plar/justpipe/badges/coverage.svg)](https://github.com/plar/justpipe/actions)
[![PyPI](https://img.shields.io/pypi/v/justpipe.svg)](https://pypi.org/project/justpipe/)
[![License](https://img.shields.io/github/license/plar/justpipe)](LICENSE)

**Your code is the graph.** A zero-dependency, async orchestration library for building event-driven AI pipelines.

---

## Why justpipe?

Building production AI agents often leads to a mess of nested `asyncio` loops, manual state management, and brittle error handling. **justpipe** provides a lightweight, Pythonic abstraction that lets you focus on logic while it handles the orchestration.

- **Zero Dependencies**: Pure Python. No transitive deps in the core library.
- **Async-First**: Built from the ground up for modern Python concurrency.
- **Developer Experience**: "The code is the graph." No complex YAML or UI builders -- your decorators define the topology.
- **Battle-Tested**: 560+ tests across unit, integration, functional, and fuzzing layers. Built-in retries, backpressure, and structured observability.

---

## Installation

```bash
pip install justpipe              # Core (zero dependencies)
pip install "justpipe[cli]"       # With CLI tools (click, rich)
pip install "justpipe[retry]"     # With retry support (tenacity)
```

---

## Quickstart: AI Search Pipeline

Define a type-safe pipeline that fetches search results, generates a prompt, and streams an LLM response. Steps execute top-to-bottom -- `to=` wires the flow.

```python
import asyncio
from dataclasses import dataclass, field
from justpipe import Pipe, EventType

@dataclass
class AIState:
    query: str
    context: list[str] = field(default_factory=list)
    response: str = ""

pipe = Pipe(AIState)

@pipe.step(to="generate_prompt")
async def search_vectors(state: AIState):
    """Simulate a RAG vector search."""
    state.context.append("Vector DB result: Python is fun.")

@pipe.step(to="call_llm")
async def generate_prompt(state: AIState):
    """Format the prompt using gathered context."""
    state.response = f"Context: {state.context}\nQuery: {state.query}"

@pipe.step()
async def call_llm(state: AIState):
    """A streaming step yielding tokens from an LLM."""
    for chunk in ["Based ", "on ", "your ", "data..."]:
        yield chunk

async def main():
    state = AIState(query="Tell me about Python")

    async for event in pipe.run(state):
        if event.type == EventType.TOKEN:
            print(event.payload, end="", flush=True)

    print("\nPipeline Complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## The Imports You Need

```python
from justpipe import Pipe, EventType     # Core
from justpipe import TestPipe            # Testing
from justpipe import Skip, Retry, Raise  # Error control
from justpipe.types import StepContext   # Advanced: middleware
from justpipe.failures import FailureKind  # Advanced: failure classification
```

---

## Built-in Testing Harness

`TestPipe` is a first-class testing tool that ships with the library. Mock steps, capture events, and make precise assertions -- no external test utilities required.

```python
from justpipe import TestPipe

async def test_my_workflow():
    with TestPipe(pipe) as tester:
        # Mock a streaming LLM call
        async def mock_llm(state):
            yield "Mocked answer"

        tester.mock("call_llm", side_effect=mock_llm)

        # Execute the pipeline
        result = await tester.run(AIState(query="test"))

        # Precise assertions
        assert result.was_called("search_vectors")
        assert "Mocked answer" in result.tokens
```

---

## Your Code is the Graph

In **justpipe**, decorators do the heavy lifting. They register your functions into a Directed Acyclic Graph (DAG) during import time. The `to=` parameter wires the flow.

```python
@pipe.step(to="respond")  # Forward reference via string
async def greet(state):
    state.message = "Hello"

@pipe.step()
async def respond(state):
    yield f"{state.message}, World!"
```

- **Type-Safe DI**: Automatically injects `state`, `context`, or even specific items from map workers based on type hints or parameter names.
- **Mutable State**: Designed around Python `dataclasses`. No complex state reduction -- just mutate your state object directly.
- **Context-Aware Routing**: Use `@pipe.switch` for dynamic branching or `@pipe.map` for massive fan-out parallelism.

---

## Common Patterns

### Parallel Execution
[View Example](examples/02_parallel_dag)

Run steps concurrently by linking a single step to multiple targets. `barrier_timeout` prevents hangs if a branch fails.

```python
@pipe.step(barrier_timeout=5.0)
async def combine(state):
    # Runs only after BOTH fetch_a and fetch_b complete
    state.result = state.a + state.b

@pipe.step(to=combine)
async def fetch_a(state):
    state.a = await fetch_api_a()

@pipe.step(to=combine)
async def fetch_b(state):
    state.b = await fetch_api_b()
```

### Dynamic Mapping (Fan-Out)
[View Example](examples/03_dynamic_map)

Process lists in parallel. `justpipe` manages the workers and results for you.

```python
@pipe.step("worker")
async def process_item(item: int, state):
    # 'item' is automatically injected from the list below
    print(f"Processing {item}")

@pipe.map(each="worker", max_concurrency=5)
async def create_batch(state):
    # Spawns a 'worker' step for every item returned
    return [1, 2, 3, 4, 5]
```

### Conditional Logic (Switch)
[View Example](examples/04_dynamic_routing)

Route execution dynamically based on return values.

```python
@pipe.switch(to={
    "ok": "process_success",
    "error": "handle_failure"
})
async def validate(state) -> str:
    return "ok" if state.is_valid else "error"
```

### Sub-pipelines & Composition
[View Example](examples/06_subpipelines)

Compose complex workflows by nesting pipelines as single steps, allowing for modular and reusable logic.

### Suspension & Human-in-the-Loop
[View Example](examples/05_suspension_resume)

Pause execution to wait for external input or human approval, then resume exactly where it left off.

---

## Command Line Interface (CLI)

**justpipe** ships with a CLI for debugging and performance analysis. Install it with `pip install "justpipe[cli]"`.

```bash
# List recent pipeline runs
justpipe list

# Show detailed events for a specific run
justpipe show <run-id>

# Generate an interactive HTML timeline
justpipe timeline <run-id> --format html

# Compare two runs to detect performance regressions
justpipe compare <run-id-1> <run-id-2>
```

---

## Comparison

| Feature | justpipe | LangGraph | Prefect | Hamilton | Raw asyncio |
|---------|----------|-----------|---------|----------|-------------|
| Zero dependencies | Yes | No | No | No | Yes |
| Async-native | Yes | Partial | Yes | No | Yes |
| Token streaming | Built-in | Manual | No | No | Manual |
| Graph-from-code | Decorators | State machine | Decorators | Functions | N/A |
| Built-in test harness | `TestPipe` | No | No | No | No |
| Backpressure | Built-in | No | No | No | Manual |
| Human-in-the-loop | `Suspend` | `interrupt` | `pause` | No | Manual |

---

## Production-Grade Reliability

A workflow engine is only as good as its test suite. **justpipe** is built with a rigorous testing philosophy, ensuring your pipelines behave predictably under load and failure.

### Multi-Layer Testing
Our suite follows a strict separation of concerns:
- **Unit Tests**: Isolated testing of internal components using mocks and fakes.
- **Integration Tests**: Verification of interactions across storage boundaries and module interfaces.
- **Functional Tests**: End-to-end validation of pipeline contracts, event ordering, and concurrency.
- **Fuzzing**: Randomized property-based testing to uncover edge cases in graph execution.

---

## Visualization

See your logic come to life. Generate beautiful Mermaid diagrams directly from your pipe instance.

```python
print(pipe.graph())
```

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
    n4 --> End

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

    subgraph utilities[Utilities]
        direction TB
        n0(["Analytics Logger ⚡"]):::isolated
        n2["Cache Manager"]:::isolated
    end
    class n1,n3,n6,n7,n8 step;
    class n10,n4,n5,n9 streaming;
    class n0,n2 isolated;
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

---

## Development

**justpipe** uses `uv` for dependency management.

```bash
# Install development dependencies
uv sync --all-extras --dev

# Run full suite
uv run pytest
```

---

## License

MIT
