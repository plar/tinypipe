# Product Guidelines

## Tone and Style
- **Technical & Precise:** Documentation and examples should prioritize accuracy, type safety, and correctness.
- **Developer-Centric:** Focus on "how-to" and "why" with clear, runnable code snippets. Avoid marketing fluff.
- **Idiomatic Python:** Emphasize modern Python features (type hints, `async/await`, dataclasses).

## Architectural Principles
1.  **Code-as-Graph:** The graph structure is defined by the code logic, not external configuration.
2.  **Stateless Blueprints:** The `Pipe` object is a stateless definition. State is local to a specific execution run (`_PipelineRunner`).
3.  **Event-Driven:** The execution model is fundamentally event-based, emitting start, end, token, and error events.
4.  **Type Safety:** Leverage Python's type system to prevent runtime errors and ensure data compatibility.

## Coding Standards (Internal)
- **Dependency Injection:** Use type matching and name conventions (`state`, `ctx`) for step arguments.
- **Control Flow:** Use explicit return types (`Next`, `Map`, `Run`, `Suspend`) to direct the graph.
- **Concurrency:** Use `asyncio.TaskGroup` for managing parallel tasks and `asyncio.Queue` for event coordination.
- **Error Handling:** Catch exceptions at the worker level and convert them to `EventType.ERROR` events.

## Contribution Guidelines
- **Testing:**
    - Unit tests (`tests/unit`) for individual components.
    - Functional tests (`tests/functional`) for full pipeline execution.
    - Reproduction scripts for bug reports.
- **Tooling:** Use `uv` for dependency management and running the project's standard toolchain (`pytest`, `ruff`, `mypy`).
- **Versioning:** Do not manually edit versions in `pyproject.toml`; use git tags (`vX.Y.Z`).
