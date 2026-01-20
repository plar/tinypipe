# Implementation Plan: Exception Handling API (on_error)

This plan implements the `on_error` API, control primitives, and the integration with the pipeline runner.

## Phase 1: Control Primitives & Types
Goal: Define the new return types for error handling.

- [ ] Task: Define Primitives in `types.py`
    - [ ] Create `Retry`, `Skip`, `Raise` classes (dataclasses).
    - [ ] Ensure `Next` and `Stop` (existing) are compatible.
    - [ ] Update `DefinitionError` if needed.
- [ ] Task: Update `Pipe` and `Step` Types
    - [ ] Update `Pipe` class to store a global `_on_error` handler.
    - [ ] Update `step`, `map`, `switch` decorators to accept `on_error` parameter and store it in `_step_metadata`.

## Phase 2: Error Handler Registry & Decorators
Goal: Allow users to register handlers.

- [ ] Task: Implement `@pipe.on_error`
    - [ ] Add `on_error` method/decorator to `Pipe` class.
    - [ ] Ensure it supports dependency injection analysis (`_analyze_signature`).
- [ ] Task: Update Step Registration
    - [ ] Update `_analyze_signature` to support `error`/`exception` and `step_name` arguments (for handlers).
    - [ ] Ensure step-level `on_error` handlers are properly analyzed and stored.

## Phase 3: Runner Integration & Logic
Goal: Execute handlers when exceptions occur.

- [ ] Task: Implement `_execute_handler`
    - [ ] Create a helper method in `_PipelineRunner` to resolve arguments (inject error, state, etc.) and call the handler.
    - [ ] Implement the lookup logic: Step Handler -> Global Handler -> Default Logic.
- [ ] Task: Update `_worker` and `_wrapper`
    - [ ] Modify the `try/except` block in `_wrapper` (or `_worker`) to catch exceptions.
    - [ ] Instead of immediately reporting `ERROR`, pass exception to `_execute_handler`.
- [ ] Task: Handle Control Primitives
    - [ ] Implement logic to handle `Retry` (re-schedule step), `Skip` (mark done with no output), `Raise` (emit ERROR event), `Next` (schedule recovery), and Value (emit TOKEN/Result).

## Phase 4: Default System Handler
Goal: Better observability for unhandled errors.

- [ ] Task: Implement Default Handler
    - [ ] Create a default logging handler that prints/logs stack traces and context.
    - [ ] Wire this into the "fall-through" case of `_execute_handler`.

## Phase 5: Verification & Documentation
Goal: Verify all recovery modes.

- [ ] Task: Functional Tests
    - [ ] Test Step-level recovery (Retry, Substitute).
    - [ ] Test Global-level recovery.
    - [ ] Test bubbling (Step fails -> Global catches).
    - [ ] Test `Skip` (pruning).
    - [ ] Test Default logging (via capturing logs).
- [ ] Task: Documentation
    - [ ] Update `README.md` with the new Error Handling section.
