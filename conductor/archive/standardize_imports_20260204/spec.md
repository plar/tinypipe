# Spec: Standardize Type Import Guards and Modern Annotations

## Overview
To improve codebase maintainability, prevent circular dependencies, and optimize runtime performance, we will standardize the use of `TYPE_CHECKING` guards and PEP 563 (Postponed Evaluation of Annotations) across the core `justpipe` engine.

## Functional Requirements
- **Modern Annotations:** Add `from __future__ import annotations` to the top of all core engine files.
- **Import Guarding:** Implement `TYPE_CHECKING` guards for all internal types that are used exclusively for type hinting (e.g., `_BaseStep`, `_RegistryValidator`, `_StepInvoker`).
- **Standardized Runtime Imports:** Maintain top-level imports for types required at runtime, such as:
    - Base classes for inheritance.
    - Types used in `isinstance()` or `issubclass()` checks.
    - Enums and Constants (e.g., `BarrierType`).
- **Core Sweep:** Apply these standards to:
    - `justpipe/pipe.py`
    - `justpipe/_registry.py`
    - `justpipe/_graph.py`
    - `justpipe/_steps.py`
    - `justpipe/_invoker.py`
    - `justpipe/_runner.py`
    - `justpipe/_validator.py`

## Non-Functional Requirements
- **Zero Behavioral Impact:** This is a refactoring track. Logic and execution flow must remain identical.
- **Improved Tooling Performance:** The change should reduce potential static analysis bottlenecks.

## Acceptance Criteria
- [ ] Every file in the core sweep contains `from __future__ import annotations`.
- [ ] No circular import errors are present.
- [ ] `uv run ruff check .` and `uv run ruff format .` pass.
- [ ] `uv run mypy .` passes with zero errors (strict mode).
- [ ] `uv run pytest` passes all tests.
- [ ] `AGENTS.md` or other developer documentation is updated if the recommended coding patterns for imports change.

## Out of Scope
- Refactoring internal logic or renaming variables.
- Modifying third-party library imports unless they cause circularity.
