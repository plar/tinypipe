# Specification: Production-Grade Core Refactoring

## Overview
This track addresses critical architectural feedback to transform `justpipe` from a "cute DSL" into a robust, production-ready pipeline library. The focus is on safety, reliability, and explicit design patterns. We will refactor the core execution engine to support backpressure, enforce stricter topology definitions, improve the safety of dependency injection, and enhance error handling for parallel execution.

## Functional Requirements

### 1. Robust Topology Definition
- **Callable References:** Update `@pipe.step`, `@pipe.map`, and `@pipe.switch` to accept direct function references in `to=...` parameters.
- **Deprecation Warning:** Maintain backward compatibility for string-based topology (`to="step_name"`) but emit a `RuntimeWarning` or `DeprecationWarning` when used.
- **Validation:** Implement a `pipe.validate()` method (Dry Run) that checks for:
    - Unresolvable string references.
    - Disconnected nodes.
    - (Optional) Cyclic dependencies.

### 2. Backpressure & Flow Control
- **Bounded Queues:** Replace the unbounded `asyncio.Queue` with a configurable bounded queue (default `maxsize=0` for unconstrained, but allow setting a safe default like `100` or `1000`).
- **Producer Blocking:** Ensure that upstream steps await/block when the downstream queue is full, effectively propagating backpressure up the chain.

### 3. Validated Dependency Injection (Smart Injection)
- **Strict Validation:** Retain the current type-based injection flexibility but implement rigorous validation at **definition time** (when `@pipe.step` is called).
- **Error Handling:** If a step function parameter cannot be resolved (i.e., it is not `state`, `context`, or a known injectable type), raise a clear and immediate `DefinitionError`.
- **Clarity:** The error message must explain *why* the parameter is invalid and what types are allowed.

### 4. Reliability & Error Handling
- **Barrier Timeouts:** Implement a specific timeout mechanism for Fan-In/Combine steps. If dependencies don't resolve within the limit, the barrier should fail gracefully (raise `TimeoutError`) rather than hanging indefinitely.
- **Observability Hooks:** Ensure the middleware/hook system is granular enough to intercept:
    - Step Start/End/Error
    - Pipeline Start/End
    - Queue Backpressure events (optional but good for debugging)
- **Middleware Example:** Provide a reference implementation of a simple logging middleware that demonstrates how to use these hooks (serving as a blueprint for future OTel integration).

## Non-Functional Requirements
- **Type Safety:** The topology definition and validation logic must be strictly typed.
- **Performance:** Backpressure overhead should be minimal.
- **DX:** Error messages for invalid topology or injection issues must be verbose, helpful, and appear as early as possible (definition time).

## Out of Scope
- Full OpenTelemetry integration (hooks only).
- Persistent Checkpointing/State recovery (future track).
- Global Pipeline Timeouts (due to interactive/suspension requirements).
