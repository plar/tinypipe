# Runtime Kernel Architecture

This document describes the internal execution engine of justpipe. The kernel is designed to be a high-performance, asynchronous, and observable event-driven system.

## Core Execution Flow

The journey from a defined `Pipe` to a running stream follows three distinct phases:

1.  **Compilation**: The `_PipelineRegistry` is compiled into an immutable `ExecutionPlan`. This Intermediate Representation (IR) contains the frozen steps, topology, dependency injection metadata, and a `parents_map` used for barrier synchronization.
2.  **Initialization**: For every `pipe.run()` call, a `_PipelineRunner` is instantiated. It initializes:
    *   **`_RunStateMachine`**: Guards phase transitions (`INIT → STARTUP → EXECUTING → SHUTDOWN → TERMINAL`).
    *   **`_RunContext`**: Holds the mutable state, context, and run-specific session data.
    *   **`_Orchestrator`**: The central coordinator that bridges the runner with its specialized managers.
3.  **Execution Loop**: The runner enters an async loop that processes a typed control channel. This channel carries both `RuntimeEvent` (external events) and `StepCompleted` (internal functional results).

## Key Components

| Component | Responsibility |
| :--- | :--- |
| **`ExecutionPlan`** | The immutable blueprint. Includes the topology and DI requirements. |
| **`_PipelineRunner`** | Owns the top-level lifecycle (startup, main loop, shutdown). |
| **`_Orchestrator`** | Provides the `schedule()`, `emit()`, and `complete_step()` primitives used by managers. |
| **`_Kernel`** | Manages the `asyncio.TaskGroup` and low-level task spawning. |
| **`_BarrierManager`** | Implements `ANY` and `ALL` join logic by tracking parent completion states. |
| **`_Scheduler`** | Determines which nodes to trigger based on the topology and current results. |
| **`event_publisher`** | A unified path for notifying observers, applying event hooks, and recording metrics. |

## Runtime Semantics

### The Control Channel
The runner's core is an `asyncio.Queue` that acts as a control plane. Unlike simple DAG executors, justpipe is reactive: steps don't just "trigger children"; they submit results back to the orchestrator, which then consults the `ExecutionPlan` and `_BarrierManager` to decide the next move.

### Terminal Invariants
- **Single Terminal Event**: Exactly one `EventType.FINISH` is guaranteed to be emitted per run.
- **Evented Failures**: Runtime failures (timeouts, step errors, startup hook crashes) are emitted as events rather than raised as exceptions from the generator.
- **Graceful Shutdown**: Shutdown hooks are guaranteed to run regardless of the run's outcome, provided the event loop is still active.

### Failure Classification
The kernel includes a `_FailureJournal` that classifies terminal outcomes. It identifies the `failure_kind` (e.g., `step` vs `startup`) and uses heuristics (or user-provided classifiers) to attribute the `failure_source` (e.g., `user_code` vs `external_dep`).

## Lineage and Correlation
As events flow through the publisher, they are enriched with:
- **`run_id`**: The ID of the root stream.
- **`seq`**: A monotonic sequence number for authoritative ordering.
- **`origin_run_id`**: Preserves the identity of the producing sub-pipeline.
- **`invocation_id`**: Correlates a `STEP_START` with its corresponding `STEP_END` or `STEP_ERROR`.