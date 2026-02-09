# Runtime Kernel Architecture

## High-Level Flow
1) Compile registry into an immutable `ExecutionPlan` (steps, topology, injection metadata, parents map).
2) Runner initializes:
   - `_RunStateMachine` (`INIT → STARTUP → EXECUTING → SHUTDOWN → TERMINAL`)
   - `_RunSession` (start time, terminal payload)
   - `_StreamPublisher` (notify observers + apply hooks)
   - Typed control channel queue (`RuntimeEvent`, `StepCompleted`).
3) Execution:
   - Startup hooks run; failures set terminal `FAILED` with `failure_kind=startup`.
   - Roots from plan (or `start` override) scheduled.
   - `_process_queue` dispatches envelopes to handlers.
   - Shutdown hooks always run; one terminal `FINISH` emitted with `PipelineEndData`.

## Components
- ExecutionPlan: immutable IR from registry; includes parents_map for barriers.
- Control channel: `RuntimeEvent` (Event) and `StepCompleted` (step result).
- State machine: guards phase transitions; terminal reason/status stored in session.
- Publisher: single path for observer notify + hook application.
- Managers: scheduler, barriers, failure handler, results — consume typed channel and plan.

## Semantics
- `Pipe.run(...) -> AsyncGenerator[Event, None]` remains.
- Terminal outcomes are evented (no default raises for runtime failures/timeout/cancel/client-close).
- FINISH payload: `PipelineEndData(status, duration_s, error, reason, failure_kind, failure_source, failed_step, errors, metrics)`.
- Optional `failure_classification` config can override source attribution via
  `source_classifier` and extend external dependency module prefixes via
  `external_dependency_prefixes`; classifier failures degrade gracefully to
  defaults and append an infra diagnostic record.
- Event schema version: `EVENT_SCHEMA_VERSION = "1.0"`.

## Invariants
- Exactly one terminal `FINISH` per run.
- No events yielded after terminal.
- Close/cancel/timeout map to terminal status.
