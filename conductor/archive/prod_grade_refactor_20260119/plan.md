# Implementation Plan: Production-Grade Core Refactoring

This plan outlines the steps to refactor the `justpipe` core to address scalability, reliability, and developer experience concerns, specifically focusing on backpressure, strict topology, and validated injection.

## Phase 1: Robust Topology & Dry Run Validation
Goal: Move away from "stringly-typed" topology and provide early validation of the pipeline graph.

- [ ] Task: Refactor `_resolve_name` and Decorators
    - [ ] Update `@pipe.step`, `@pipe.map`, and `@pipe.switch` to accept callables for the `to` and `using` parameters.
    - [ ] Implement a `DeprecationWarning` when string names are used in routing parameters.
- [ ] Task: Implement `Pipe.validate()` (Dry Run)
    - [ ] Implement logic to traverse the graph and detect unresolvable string references.
    - [ ] Add detection for disconnected nodes (steps that are neither roots nor targets).
    - [ ] Add a basic cycle detection check.
- [ ] Task: Verification
    - [ ] Write functional tests verifying that callable-based routing works correctly.
    - [ ] Write tests ensuring `validate()` catches broken string references and disconnected nodes.

## Phase 2: Bounded Queues & Backpressure
Goal: Prevent OOM crashes by limiting queue size and implementing producer blocking.

- [ ] Task: Update `_PipelineRunner` Queue Management
    - [ ] Modify `_PipelineRunner.__init__` to accept a `queue_size` parameter.
    - [ ] Update `asyncio.Queue` initialization with the specified `maxsize`.
- [ ] Task: Implement Producer Blocking Logic
    - [ ] Ensure `_schedule` and worker dispatch logic properly awaits queue availability when the queue is full.
    - [ ] Verify that backpressure correctly halts upstream production without deadlocking the event loop.
- [ ] Task: Verification
    - [ ] Create a stress-test example with a fast producer and slow consumer to verify memory stability and backpressure.

## Phase 3: Strict Injection Validation
Goal: Remove "magic" confusion by validating step function signatures at definition time.

- [ ] Task: Enhance `_analyze_signature`
    - [ ] Update the logic to raise a `DefinitionError` if a parameter is not typed as `State`, `Context`, or named with a recognized alias.
    - [ ] Ensure this validation runs during the decorator execution (definition time), not runtime.
- [ ] Task: Verification
    - [ ] Write unit tests that attempt to define "illegal" steps and verify that the correct `DefinitionError` is raised with helpful messages.

## Phase 4: Barrier Timeouts & Observability Hooks
Goal: Prevent "zombie" pipelines and provide hooks for external tracing/logging.

- [ ] Task: Implement Barrier Timeouts
    - [ ] Add a `barrier_timeout` parameter to `@pipe.step`.
    - [ ] Modify the fan-in logic in `_PipelineRunner` to start a timer when the first parent completes.
    - [ ] Raise `TimeoutError` if the barrier is not cleared within the specified window.
- [ ] Task: Granular Hook System
    - [ ] Expose new event types or hook points for `BACKPRESSURE_START` and `BACKPRESSURE_END`.
    - [ ] Ensure middleware can easily access timing data for every step.
- [ ] Task: Example Middleware
    - [ ] Implement a `LoggingMiddleware` or `StructuredLogMiddleware` that demonstrates capturing step latency and errors.
- [ ] Task: Verification
    - [ ] Write a test for a barrier timeout where one branch is intentionally delayed.
    - [ ] Verify middleware correctly receives all lifecycle events.

## Phase 5: Finalization & Documentation
- [ ] Task: Update Examples
    - [ ] Refactor existing examples to use callable-based routing (`to=my_func`).
- [ ] Task: Documentation Update
    - [ ] Update `README.md` to document the new safety features, backpressure configuration, and the importance of callable routing.
