# Product Definition

## Initial Concept
`justpipe` is an async, streaming pipeline library for AI where the code structure defines the execution graph. It aims to provide a lightweight, type-safe, and developer-friendly way to orchestrate complex workflows, particularly suited for LLM chains and data processing tasks.

## Target Audience
- **AI Engineers & Data Scientists:** Building complex, streaming interaction flows for LLMs and agents.
- **Backend Developers:** Needing a robust, type-safe way to manage async workflows and business logic pipelines.
- **Library Authors:** Seeking a minimal, embeddable execution engine for their own frameworks.

## Core Value Proposition
- **Code-as-Graph:** Define pipelines using standard Python functions and decorators. No YAML, no separate DSL.
- **Type Safety:** Leveraged Python's type system to ensure data compatibility between pipeline steps.
- **Backpressure:** Built-in support for bounded queues to ensure reliability under heavy load and prevent OOM crashes.
- **Declarative Routing:** Dedicated decorators (@pipe.map, @pipe.switch) separate business logic from flow control.
- **Refactoring Safety:** Support for passing function references directly as targets ensures IDE-friendly refactoring.
- **Async & Streaming:** Built from the ground up for `asyncio` and streaming response patterns, critical for modern AI apps.
- **Lightweight:** Zero-dependency core, with optional extensions for specific needs (e.g., retries).

## Key Features
- **DAG Execution:** Parallel and sequential execution of steps based on dependencies.
- **Map-Reduce Pattern:** Simple declarative fan-out using @pipe.map.
- **Conditional Branching:** Type-safe, declarative switch logic using @pipe.switch.
- **Streaming:** First-class support for yielding partial results (tokens) from any step.
- **Dry Run Validation:** Validate graph integrity, references, and detect cycles before execution.
- **Middleware:** Extensible hook system for logging, tracing, and error handling.
- **Lifecycle Management:** Hooks for setup, teardown, and error recovery.
- **Dynamic Routing:** Conditional execution paths based on runtime state.
- **Reliability:** Per-step timeouts and barrier timeouts for parallel execution.
- **Error Handling API:** Hybrid (global/step) handlers with control primitives (Retry, Skip, Stop, Next) and rich default logging.
