# Implementation Plan: Declarative API Refactoring

- [ ] **Phase 1: Core Framework Update**
    - [x] Update `justpipe/types.py`: Ensure `_resolve_name` is robust for Callables.
    - [x] Update `justpipe/core.py`: Implement `@pipe.map`.
    - [x] Update `justpipe/core.py`: Implement `@pipe.switch`.
    - [x] Update `justpipe/core.py`: Modify `_handle_task_result` to handle Switch logic and validation.
    - [x] Update `justpipe/core.py`: Ensure implicit topology handling respects Switch logic (i.e., don't run all `routes` values, only the selected one).

- [ ] **Phase 2: Visualization Update**
    - [x] Update `justpipe/visualization.py`: Render Diamond shapes for `switch` steps.
    - [x] Update `justpipe/visualization.py`: Render labeled edges for `switch` cases.
    - [x] Update `justpipe/visualization.py`: Render specific style for `map` targets.

- [ ] **Phase 3: Migration (Tests & Examples)**
    - [x] Migrate `examples/` to new API.
    - [x] Migrate `tests/` to new API.
    - [x] Verify `uv run pytest` passes.

- [ ] **Phase 4: Cleanup**
    - [x] Remove `Next` and `Map` from `justpipe/__init__.py`.
    - [x] Mark them internal in `types.py` (rename to `_Next`, `_Map` or keep as implementation details).
