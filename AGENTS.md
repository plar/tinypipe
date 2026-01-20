# Agent's Guide to justpipe

This document is for LLM agents (like Gemini, Claude, or Cursor) working on or with the `justpipe` codebase. It provides the technical mental model, toolchain instructions, and coding patterns required to maintain and extend the library.

---

## 🧩 Architectural Mental Model

`justpipe` is a graph execution engine for async workflows.

1.  **`Pipe` (Public API)**: The user-facing class. It's a "blueprint". It stores steps, topology, and hooks but does *not* hold execution state.
2.  **`_PipelineRunner` (Internal)**: Created for every `run()` call. It manages the `asyncio.Queue`, `asyncio.TaskGroup`, and the execution state (`self._state`, `self._context`).
3.  **Dependency Injection**: Steps receive arguments based on:
    - **Type matching**: If a parameter type matches `StateT` or `ContextT`.
    - **Name matching**: Parameters named `s`/`state` or `c`/`ctx`/`context`.
    - **Payload mapping**: For `Map` operations, "unknown" parameters receive the item.
4.  **Event Stream**: Everything is an `Event`. The runner yields events for starts, ends, tokens (from generators), errors, and suspension.

---

## 🛠 Tooling & Commands

Always run these commands from the project root using `uv`.

| Task | Command |
| :--- | :--- |
| **Install** | `uv sync --all-extras --dev` |
| **Test** | `uv run pytest` |
| **Lint** | `uv run ruff check .` |
| **Type Check** | `uv run mypy justpipe` |
| **Format** | `uv run ruff format .` |

### Testing Strategy
- **Unit Tests (`tests/unit`)**: Test individual structures (like `Next`, `Map`) and utility functions.
- **Functional Tests (`tests/functional`)**: Test the full `Pipe.run()` loop. Use these to verify execution flow, barrier synchronization, and error handling.
- **Reproduction**: When fixing a bug, always create a minimal reproduction script in `tests/repro_<name>.py` first.

### Versioning Strategy
- **hatch-vcs**: This project uses `hatch-vcs` for version management. **Do NOT manually update the version in `pyproject.toml`.**
- **Git Tags**: Versions are automatically derived from git tags (e.g., `v0.3.0`). To release a new version, create a git tag and push it.

---

## 📝 Coding Patterns for Agents

### 1. Adding a new Step Logic
When modifying how steps are executed, look at `_PipelineRunner._worker`.
- It handles both regular `async` functions and `async generators`.
- Generators yield `TOKEN` events for non-control values.

### 2. Control Flow (Return Types)
`justpipe` uses specific return types to control the graph:
- `Next("step_name")`: Jump to a specific step.
- `Map(items=[...], target="step")`: Fan-out parallel tasks.
- `Run(pipe=sub_pipe, state=...)`: Execute a sub-pipeline.
- `Suspend(reason=...)`: Pause the pipeline.

### 3. Error Handling
- Do not let exceptions escape the `_worker`. The `_wrapper` catches them and converts them into `EventType.ERROR` events.
- Shutdown hooks must run even if startup fails (the "emergency shutdown" pattern).

### 4. Async Conventions
- Always use `asyncio.TaskGroup` for managing concurrent tasks (Python 3.11+).
- Use `asyncio.Queue` for event collection to ensure thread-safety and ordering.

---

## 🚦 Common Pitfalls
- **Circular Dependencies**: The library doesn't currently detect them during registration, only during execution (infinite loop/deadlock).
- **Type Erasure**: `justpipe` uses `get_args` on `__orig_class__` to find `StateT` and `ContextT` at runtime. This requires the `Pipe` to be instantiated with concrete types (e.g., `Pipe[MyState, MyContext]()`).
- **Tenacity**: It's an optional dependency. Always check `HAS_TENACITY` before using it.
