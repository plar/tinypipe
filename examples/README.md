# justpipe Examples Gallery

This directory contains a curated set of examples designed to take you from a "Hello World" pipeline to production-grade AI agents.

## 🎨 Visual Guide

Each example includes a Mermaid diagram to help you visualize the pipeline topology. We use a consistent color language across the gallery:

| Component | Style | Description |
|:---:|:---:|:---|
| **Step** | Blue | A standard functional unit of work. |
| **Streaming** | Orange + ⚡ | An async generator yielding tokens in real-time. |
| **Map** | Green | A fan-out node that spawns multiple concurrent workers. |
| **Switch** | Purple | A conditional router for dynamic branching. |
| **Sub-pipe** | Light Green | A nested pipeline running as a single step. |
| **Isolated** | Dotted Pink | Utility steps or observers running outside the main flow. |
| **Start/End** | Bold Green | Entry and exit points of the execution. |

---

## 🚀 Getting Started

If you're new to `justpipe`, start here to understand the core mental model.

| Example | Focus |
|:---|:---|
| **[01 Quick Start](./01_quick_start)** | Basic step registration, state mutation, and execution. |
| **[11 Visualization](./11_visualization)** | Generating Mermaid diagrams to see your code as a graph. |
| **[14 Testing Harness](./14_testing_harness)** | How to write unit tests for your pipelines using `TestPipe`. |

## 🏗️ Orchestration Patterns

Master the "Your Code is the Graph" philosophy with these structural patterns.

| Example | Focus |
|:---|:---|
| **[02 Parallel DAG](./02_parallel_dag)** | Static fan-out/fan-in using implicit barriers. |
| **[03 Dynamic Map](./03_dynamic_map)** | Parallelizing workloads across dynamic lists (e.g., batch processing). |
| **[04 Dynamic Routing](./04_dynamic_routing)** | Conditional branching using `@pipe.switch`. |
| **[13 Barrier Types](./13_barrier_types)** | Controlling execution with `ANY` (race) vs `ALL` (sync) joins. |
| **[06 Sub-pipelines](./06_subpipelines)** | Composition and modularity by nesting pipelines. |

## 🤖 AI & Streaming

Patterns specifically designed for building LLM-powered applications.

| Example | Focus |
|:---|:---|
| **[07 Streaming](./07_streaming)** | Real-time token streaming for chat interfaces. |
| **[05 Suspension](./05_suspension_resume)** | Human-in-the-loop: pausing execution to wait for user input. |

## 🛠️ Production Reliability

Tools for monitoring, debugging, and hardening your pipelines.

| Example | Focus |
|:---|:---|
| **[12 Observability](./12_observability)** | Logging, storage, metrics, and timeline visualization. |
| **[08 Reliability](./08_reliability_retry)** | Automatic retries and exponential backoff using `tenacity`. |
| **[09 Middleware](./09_middleware)** | Cross-cutting concerns like global timing or custom logging. |
| **[10 Lifecycle Hooks](./10_lifecycle_hooks)** | Resource management (DB connections, API clients) via `on_startup`/`on_shutdown`. |

---

## Running Examples

All examples are designed to be run from the **project root** using `uv`:

```bash
# Run a specific example
uv run python examples/01_quick_start/main.py

# Some examples (03, 07) support optional API keys
export GEMINI_API_KEY="..."
uv run python examples/03_dynamic_map/main.py
```

## Creating Your Own

1. Use a `dataclass` for your `State`.
2. Define a `Pipe(State)`.
3. Use `@pipe.step(to=...)` to wire your logic.
4. Run with `async for event in pipe.run(state):`.

Happy Piping! 🚀
