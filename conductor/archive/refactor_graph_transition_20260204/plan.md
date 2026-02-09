# Plan: Refactor Graph Transition Logic

This plan follows the "Functional Orchestrator" pattern to decompose the complex `transition` method in `justpipe/_graph.py`.

## Phase 1: Preparation & Baseline
- [x] Task: Create a baseline test suite for current graph behavior.
    - [x] Run `uv run pytest tests/unit/test_barriers.py` and `tests/functional/test_barrier_types.py` to ensure all tests pass.
    - [x] Create a temporary stress test for large DAGs to verify performance before changes.
- [x] Task: Document current cyclomatic complexity of `transition`.
    - [x] Use a tool or manual count to establish a baseline.

## Phase 2: Refactoring (Implementation)
- [x] Task: Implement internal state encapsulation helpers.
    - [x] Create `_update_node_progress(node: str)` to centralize `_completed_parents` updates.
    - [x] Create `_is_barrier_satisfied(node: str) -> bool` to encapsulate the satisfaction threshold logic.
- [x] Task: Extract Specialized Barrier Handlers.
    - [x] Implement `_handle_any_barrier(node: str) -> bool`.
    - [x] Implement `_handle_all_barrier(node: str) -> bool`.
- [x] Task: Refactor `transition` method.
    - [x] Rewrite the main loop in `transition` to use the new handlers.
    - [x] Ensure `TransitionResult` is populated based on handler returns.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Refactoring' (Protocol in workflow.md)

## Phase 3: Verification & Quality Assurance
- [x] Task: Functional Verification.
    - [x] Run full test suite: `uv run pytest`.
    - [x] Run performance stress tests to ensure no regression.
- [x] Task: Code Quality & Standards.
    - [x] Run linting: `uv run ruff check .`.
    - [x] Run type checking: `uv run mypy .`.
    - [x] Verify cyclomatic complexity reduction (target < 10).
- [x] Task: Documentation & Cleanup.
    - [x] Update `AGENTS.md` architectural model for `_Graph`.
    - [x] Ensure docstrings for new private methods are comprehensive.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Verification' (Protocol in workflow.md)
