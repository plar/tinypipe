# Agent's Guide to justpipe

This document is for LLM agents (like Gemini, Claude, or Cursor) working on or with the `justpipe` codebase. It provides the technical mental model, toolchain instructions, and coding patterns required to maintain and extend the library.

---

## 🧩 Architectural Mental Model

`justpipe` is a graph execution engine for async workflows.

1.  **`Pipe` (Public API)**: The user-facing class. It's a "blueprint".
    -   Instantiated with explicit types: `Pipe[StateT, ContextT](state_type, context_type)`.
    -   Delegates all registration and validation to `_PipelineRegistry`.

2.  **`_PipelineRegistry` (Internal)**: A thin facade coordinating pipeline definition.
    -   Delegates step registration, topology, and injection metadata to `_StepRegistry`.
    -   Delegates middleware and event hooks to `_MiddlewareCoordinator`.
    -   Directly owns lifecycle hooks (`startup_hooks`, `shutdown_hooks`, `error_hook`) and `observers`.
    -   `finalize()` validates pending checks via `_StepRegistry`, then applies middleware via `_MiddlewareCoordinator`.

    **`_StepRegistry`**: Owns `steps`, `topology`, `injection_metadata`, and `_pending_validations`.
    -   Implements `step()`, `map()`, `switch()`, `sub()` decorators and `_register_step()`.
    -   Delegates signature analysis to `_TypeResolver` and input validation to `_RegistryValidator`.

    **`_MiddlewareCoordinator`**: Owns `middleware` list and `event_hooks` list.
    -   Implements `add_middleware()`, `add_event_hook()`, and `apply_middleware(steps)`.

3.  **`_PipelineRunner` (Internal)**: Created for every `run()` call. Implements the `TaskOrchestrator` protocol.
    -   Delegates to specialized components via granular protocol ports defined in `orchestration/protocols.py`.
    -   Manages an `asyncio.TaskGroup` for concurrency and an `asyncio.Queue` for event streaming; compiled `ExecutionPlan` drives topology/DI.
    -   Tracks logical/physical tasks for barriers and emits built-in runtime metrics (queue depth, task counts, step latency, barrier waits/timeouts, map fan‑out, event/token/suspend counts) into the FINISH payload (`PipelineEndData.metrics`).

4.  **Orchestration Protocols** (`orchestration/protocols.py`): Granular protocol hierarchy defining boundaries between Runner and managers.
    -   Fine-grained ports: `SchedulePort`, `SpawnPort`, `QueueSubmitPort`, `EventEmitPort`, `StepCompletionPort`, `StepFailurePort`, `StepExecutionPort`, `StopPort`.
    -   Composite protocols: `CoordinatorOrchestrator`, `InvokerOrchestrator`, `FailureHandlingOrchestrator`, `BarrierOrchestrator`, `SchedulerOrchestrator`, `ResultOrchestrator`.
    -   `TaskOrchestrator` is the top-level composite that unifies all ports.
    -   Managers MUST depend on the narrowest Protocol they need, NOT the concrete Runner.

5.  **`_DependencyGraph` (Internal)**: Encapsulates the pipeline topology and dependency tracking.
    -   Implements **Barrier Logic** (`ANY`, `ALL`) via specialized private handlers: `_handle_any_barrier` and `_handle_all_barrier`.
    -   Manages node satisfaction state (`_satisfied_nodes`) and parent completion tracking (`_completed_parents`).
    -   `transition(node)` orchestrates the logic, determining which steps to start and which barriers to schedule/cancel.

6.  **`_StepInvoker` (Internal)**: Encapsulates step execution.
    -   Handles **Dependency Injection** by matching function signatures.
    -   Applies timeouts and handles `async` generators (streaming tokens).
    -   Supports cooperative cancellation via `CancellationToken`.

7.  **Dependency Injection**: Parameters are injected based on:
    -   **Type matching**: `StateT`, `ContextT`, `CancellationToken`.
    -   **Name matching**: `s`/`state`, `c`/`ctx`/`context`, `cancel`/`token`.
    -   **Special keys**: `error` (in `on_error` handlers), `step_name`.
    -   **Payload mapping**: In `Map` operations, the item is injected into the first "unknown" parameter.

8.  **`_FailureHandler` (Internal)** (`failure/failure_handler.py`): Determines if an error should be retried, swallowed, or propagated.

9.  **Telemetry** (`telemetry/`): Runtime observability internals.
    -   `execution_log.py`: Structured execution logging.
    -   `failure_journal.py`: Failure record collection.
    -   `runtime_metrics.py`: Built-in metric aggregation for the FINISH payload.

10. **Visualization** (`justpipe/visualization/`): Pipeline graph rendering.
    -   `ast.py`: Pipeline AST representation.
    -   `builder.py`: Builds visualization models from pipeline definitions.
    -   `mermaid.py`: Mermaid diagram generation.
    -   `renderer.py`: Generic rendering infrastructure.

11. **Event Stream**: Everything is an `Event`.
    -   Lifecycle: `START`, `FINISH`, `SUSPEND`, `TIMEOUT`, `CANCELLED` (FINISH carries `PipelineEndData` with `status`, `duration_s`, `reason`, optional error, and `RuntimeMetrics`).
    -   Step: `STEP_START`, `STEP_END`, `STEP_ERROR`, `TOKEN`.
    -   Parallel: `BARRIER_WAIT`, `BARRIER_RELEASE`, `MAP_START`, `MAP_WORKER`, `MAP_COMPLETE`.

---

## 📦 Public API

13 core exports from `justpipe`: `Pipe`, `Event`, `EventType`, `Meta`, `Stop`, `Suspend`, `Retry`, `Skip`, `Raise`, `DefinitionError`, `simple_logging_middleware`, `TestPipe`, `TestResult`

Failure types from `justpipe.failures`: `FailureRecord`, `FailureKind`, `FailureSource`, `FailureReason`, `FailureClassificationConfig`, `FailureClassificationContext`, `FailureSourceClassifier`

---

## 🛠 Tooling & Commands

Always run these commands from the project root using `uv`.

| Task | Command |
| :--- | :--- |
| **Install** | `uv sync --all-extras --dev` |
| **Test** | `uv run pytest` |
| **Lint** | `uv run ruff check .` |
| **Type Check** | `uv run mypy justpipe/` |
| **Format** | `uv run ruff format .` |
| **Python** | `uv run <relative path to python file>` |
| **CLI** | `uv run justpipe <command>` |
| **Coverage** | `uv run pytest tests --cov=justpipe --cov-report=term-missing` |
| **Benchmarks** | `uv run pytest benchmarks/ -q` |
| **Mutation (Local)** | `uv run mutmut run` |
| **Dashboard Dev** | `cd dashboard-ui && npm install && npm run dev` |
| **Dashboard Build** | `cd dashboard-ui && npm run build` |

### Testing Strategy
- **Unit Tests (`tests/unit`)**: Test individual components (`test_visualization_builder.py`, `test_storage.py`).
- **Integration Tests (`tests/integration`)**: Test real internal boundaries (e.g., SQLite/storage and observer-storage integration).
- **Functional Tests (`tests/functional`)**: Test full `Pipe.run()` cycles.
- **Fuzzing (`tests/fuzzing`)**: Use Hypothesis for edge-case discovery.
- **Benchmarks (`benchmarks/`)**: Performance tests only; not part of default correctness run.
- **Reproduction**: When fixing a bug, create a minimal reproduction in `tests/functional/test_<name>.py`.
- **Canonical Ownership**:
  - `tests/functional/test_event_ordering.py` is the canonical suite for event ordering + lifecycle invariants.
  - `tests/functional/test_runtime_contracts.py` should cover runtime contracts not already asserted by event-ordering canonicals.
- **Determinism Rule**: Prefer `asyncio.Event`/explicit coordination over sleep-driven timing in async tests.
- **Observability Test Rule**: Prefer structured-record assertions (sink outputs) over brittle raw string matching.
- **`asyncio_mode = "auto"`** in pytest config — do NOT add `@pytest.mark.asyncio` to tests.
- **583 tests** is the current baseline — all must pass before committing.
- **`examples/`** is excluded from both ruff and mypy.

### Local Mutation Testing Notes
- Configured in `pyproject.toml` `[tool.mutmut]`, scoped to high-value modules. Local-only, not CI-gated.
- Triage: `uv run mutmut results` / `uv run mutmut show <mutant-id>`

### Versioning Strategy
- **hatch-vcs**: Versions are automatically derived from git tags (e.g., `v0.3.0`). **Do NOT manually update the version in `pyproject.toml`.**

---

## 📝 Coding Patterns for Agents

### 1. Control Flow (Return Types)
Steps control the graph by returning specific primitives (import from `justpipe`):
- `str`: Jump to a specific step (shorthand for `_Next`).
- `Stop`: Terminate the pipeline immediately.
- `Suspend(reason=...)`: Pause the pipeline (for human-in-the-loop).
- `Retry()`: Re-run the current step (requires `tenacity` or custom middleware).
- `Skip()`: Skip the current step and its downstream children.
- `Raise(exception)`: Propagate an error manually.

### 2. Step Decorators
- `@pipe.step(to="next_step")`: Standard linear transition.
- `@pipe.map(each="worker_step")`: Fan-out items from an iterable to parallel workers.
- `@pipe.switch(to={True: "step_a", False: "step_b"})`: Conditional routing based on return value.
- `@pipe.sub(pipeline=other_pipe)`: Execute a sub-pipeline.

### 3. Error Handling
- Use `@pipe.on_error` for global recovery.
- Use `on_error` parameter in `@pipe.step(...)` for step-specific recovery.
- The `_FailureHandler` (internal) determines if an error should be retried, swallowed, or propagated.

### 4. Async Conventions
- Requires **Python 3.11+**.
- Always use `asyncio.TaskGroup` for managing concurrent tasks.
- Avoid manual `asyncio.create_task` inside the runner; use `self._spawn()`.

### 5. Import & Type Hinting Patterns
- **Modern Annotations:** Use `from __future__ import annotations` in all core engine files.
- **Modern Type Syntax (Required):** Use built-in generics and PEP 604 unions, e.g. `dict[str, Any]`, `list[str]`, `set[str]`, `tuple[int, str]`, `X | Y`, `type[MyClass]`.
- **Avoid Legacy Typing Aliases:** Do not introduce `typing.Dict`, `typing.List`, `typing.Set`, `typing.Tuple`, `typing.Union`, or `typing.Type` in new or modified code.
- **TYPE_CHECKING:** Wrap internal types used only for hints in `if TYPE_CHECKING:` guards to prevent circularities.
- **Runtime Integrity:** Keep classes that are instantiated, inherited from, or used in `isinstance()` checks at the top level.

### 6. Meta Protocol
- `Meta` is a Protocol (not ABC), detected via `get_type_hints()` on user's context type.
- Three scopes: `ctx.meta.step` (write, contextvar-scoped), `ctx.meta.run` (write, shared), `ctx.meta.pipeline` (read-only).
- Step meta appears on `Event.meta` of STEP_END/STEP_ERROR events; run meta on FINISH events.

### 7. Storage & Persistence
- `StorageBackend` is a sync Protocol; async wrapping via `asyncio.to_thread()` in the observer.
- Backends: `SQLiteBackend`, `InMemoryBackend` in `justpipe/storage/`.
- Storage DTOs use `datetime`/`timedelta` and justpipe enums; internal `Event.timestamp` stays `float`.

---

## 🚦 Common Pitfalls
- **Zero-dep Core**: `justpipe` has no runtime dependencies. `tenacity`, `click`, `rich`, `fastapi` are optional extras.
- **Persistence Off by Default**: `persist=False` — no surprise disk writes unless explicitly enabled.
- **Dashboard Frontend**: `dashboard-ui/` is a Vue 3 + Vite + Tailwind v4 + PixiJS + ELK + Pinia app; built assets go to `justpipe/dashboard/static/` via custom hatch build hook.
- **Type Erasure**: `justpipe` requires `state_type` and `context_type` in `Pipe()` constructor for runtime signature analysis.
- **Backpressure**: The event queue has a default size (`1000`). If many tokens are yielded without being consumed, the pipeline will block.
- **Mutable State**: State is shared across parallel steps. Use thread-safe patterns or `context` for read-only data.
- **Barrier Deadlocks**: Ensure that `BarrierType.ALL` steps can actually reach all their parent dependencies.
- **Event Hook Ordering**: Event hooks run before observers (so hook-enriched meta is visible to persistence).
- **No Backward Compat**: Project is WIP — no need for deprecation shims or re-exports of removed code.
