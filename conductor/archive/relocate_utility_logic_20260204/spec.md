# Spec: Relocate Utility Logic and Decouple Data Types

## Overview
To align with the Single Responsibility Principle (SRP) and maintain a clean dependency graph, we will relocate execution logic from the public `justpipe/types.py` to the internal `justpipe/_utils.py`. We will also transform the `_Next` type into a pure data carrier by removing its logical property.

## Functional Requirements
- **Relocate `_resolve_name`:**
    - Move the `_resolve_name` function from `justpipe/types.py` to `justpipe/_utils.py`.
    - Ensure it is exported/available for internal use by other modules.
- **Transform `_Next` to PODO:**
    - Remove the `stage` property from the `_Next` dataclass in `justpipe/types.py`.
- **Update Internal Callers:**
    - Update all modules that previously imported `_resolve_name` from `types.py` to import it from `_utils.py`.
    - Identify and update any callers of `_Next.stage` to use `_resolve_name(_Next.target)` explicitly.

## Non-Functional Requirements
- **Dependency Isolation:** `justpipe/types.py` must NOT import from `justpipe/_utils.py`.
- **Zero Behavioral Impact:** The name resolution logic itself remains unchanged.
- **Maintainability:** Clear separation between "Data Definitions" (`types.py`) and "Logical Operations" (`_utils.py`).

## Acceptance Criteria
- [ ] `justpipe/types.py` contains only definitions (dataclasses, enums, exceptions) and no processing functions.
- [ ] All occurrences of `_resolve_name` in the codebase correctly import from `_utils.py`.
- [ ] `uv run ruff check .` and `uv run ruff format .` pass.
- [ ] `uv run mypy .` and `uv run pytest` pass without errors.
- [ ] Any internal documentation (e.g., `AGENTS.md`) is updated if it references the location of name resolution logic.

## Out of Scope
- Refactoring `CancellationToken` (kept in `types.py` for API consistency).
- Renaming or changing the behavior of `_resolve_name`.
