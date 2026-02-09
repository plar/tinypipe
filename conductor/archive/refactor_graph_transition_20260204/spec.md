# Spec: Refactor Graph Transition Logic (Cyclomatic Complexity)

## Overview
The current `transition` method in `justpipe/_graph.py` (lines 62-118) has high cyclomatic complexity (57 lines of nested conditionals). It handles multiple barrier types (`ANY`, `ALL`) and state updates within a single loop, making it hard to maintain and prone to regressions. This track will refactor the logic using a "Functional Orchestrator" pattern.

## Functional Requirements
- **Specialized Barrier Handlers:** Extract logic for `BarrierType.ANY` and `BarrierType.ALL` into dedicated private methods:
    - `_handle_any_barrier(self, node: str) -> bool`
    - `_handle_all_barrier(self, node: str) -> bool`
- **Functional Orchestration:** The `transition` method will act as a high-level orchestrator, iterating through successors and aggregating satisfied nodes into the `TransitionResult`.
- **Semantic Satisfaction Checks:** Replace raw counter comparisons (e.g., `>= parents_needed`) with a semantic method `_is_barrier_satisfied(self, node: str) -> bool`.
- **State Encapsulation:** Centralize updates to internal tracking state (`_completed_parents`, `_satisfied_nodes`) to ensure consistency.

## Non-Functional Requirements
- **No Behavioral Changes:** The refactoring must be functionally identical to the current implementation. All existing tests must pass.
- **Maintainability:** Improve readability by reducing nesting levels and using clear, descriptive method names.
- **Documentation:** Provide detailed docstrings for the new private methods explaining the exact conditions for "satisfaction" for each barrier type.

## Acceptance Criteria
- [ ] `justpipe/_graph.py` passes linting (Ruff) and type checking (Mypy).
- [ ] Cyclomatic complexity of the `transition` method is significantly reduced (target < 10).
- [ ] All functional tests in `tests/functional/` and unit tests in `tests/unit/test_barriers.py` pass.
- [ ] `AGENTS.md` and any other architectural documentation are updated to reflect the new internal graph structure.
- [ ] Verification tests are added/updated if the refactoring exposes new internal methods for better unit testing.

## Out of Scope
- Adding new `BarrierType` variants.
- Modifying the public `TransitionResult` API.
- Refactoring other methods in `_graph.py` unless directly required by the `transition` logic.
