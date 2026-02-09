# Plan: Relocate Utility Logic and Decouple Data Types

This track relocates `_resolve_name` to `_utils.py` and removes logic from `types.py` to ensure a clean, one-way dependency graph.

## Phase 1: Preparation & Audit
- [x] Task: Audit Callers.
    - [x] List all modules importing `_resolve_name` from `justpipe.types`.
    - [x] Search for all occurrences of `.stage` on `_Next` objects.
- [x] Task: Establish Baseline.
    - [x] Run `uv run pytest` and `uv run mypy .` to ensure current state is healthy.

## Phase 2: Relocation & Refactoring (Implementation)
- [x] Task: Move `_resolve_name`.
    - [x] Remove `_resolve_name` from `justpipe/types.py`.
    - [x] Add `_resolve_name` to `justpipe/_utils.py`.
- [x] Task: PODO Transformation.
    - [x] Remove the `stage` property from `_Next` dataclass in `justpipe/types.py`.
- [x] Task: Update Callers & Imports.
    - [x] Update all internal modules to import `_resolve_name` from `justpipe._utils`.
    - [x] Replace any `.stage` calls with `_resolve_name(obj.target)`.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Relocation' (Protocol in workflow.md)

## Phase 3: Verification & Quality Assurance
- [x] Task: Quality Sweep.
    - [x] Run `uv run ruff check .` and `uv run ruff format .`.
    - [x] Run `uv run mypy .` to verify no type-hint regressions.
    - [x] Run `uv run pytest` to ensure all functionality is preserved.
- [x] Task: Documentation.
    - [x] Update `AGENTS.md` if any architectural descriptions of type resolution have changed.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Verification' (Protocol in workflow.md)
