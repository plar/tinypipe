# Plan: Standardize Type Import Guards and Modern Annotations

This track implements consistent `TYPE_CHECKING` guards and `from __future__ import annotations` across the core engine to prevent circularities and align with modern Python standards.

## Phase 1: Preparation & Baseline
- [x] Task: Establish baseline for static analysis and tests.
    - [x] Run `uv run ruff check .` and `uv run ruff format .` to ensure a clean starting point.
    - [x] Run `uv run mypy .` and `uv run pytest` to verify current state.
- [x] Task: Identify specific "Hint-Only" vs "Runtime" dependencies for each target file.

## Phase 2: Refactoring (Implementation)
- [x] Task: Implement standardized imports in `_steps.py` and `_validator.py`.
    - [x] Add `from __future__ import annotations`.
    - [x] Wrap non-runtime internal dependencies in `if TYPE_CHECKING:`.
- [x] Task: Implement standardized imports in `_graph.py` and `_registry.py`.
    - [x] Add `from __future__ import annotations`.
    - [x] Wrap internal collaborators (Resolvers, Validators, Registries) in guards.
- [x] Task: Implement standardized imports in `_invoker.py`, `_runner.py`, and `pipe.py`.
    - [x] Add `from __future__ import annotations`.
    - [x] Clean up existing guards and move relevant top-level imports into them.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Refactoring' (Protocol in workflow.md)

## Phase 3: Verification & Quality Assurance
- [x] Task: Functional and Static Verification.
    - [x] Run `uv run ruff check .` and `uv run ruff format .`.
    - [x] Run `uv run mypy .` (Strict Mode) to ensure types are correctly resolved through guards.
    - [x] Run `uv run pytest` to ensure no runtime regressions (import errors).
- [x] Task: Documentation Update.
    - [x] Update `AGENTS.md` "Coding Patterns for Agents" section with the new import standards.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Verification' (Protocol in workflow.md)
