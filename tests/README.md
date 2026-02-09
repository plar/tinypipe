# Test Architecture

This repository enforces four test layers:

- `tests/unit/`: isolated component behavior, mocks/fakes allowed.
- `tests/integration/`: interactions across internal modules and storage boundaries.
- `tests/functional/`: end-to-end pipeline behavior and user-facing contracts.
- `tests/fuzzing/`: property-based and randomized edge-case coverage.

## Domain Subfolders

To keep files maintainable, large domains should live in dedicated folders per layer:

- `tests/unit/definition/`
- `tests/unit/runtime/`
- `tests/unit/shared/`
- `tests/unit/storage/`
- `tests/unit/visualization/`
- `tests/unit/observability/`
- `tests/integration/observability/`
- `tests/integration/storage/`
- `tests/functional/concurrency/`
- `tests/functional/error_handling/`
- `tests/functional/observability/`

## Refactor Rules

- Prefer `pytest.mark.parametrize` when test logic differs only by input/expectation.
- Keep tests in Arrange-Act-Assert order.
- Use fixtures for shared setup instead of hardcoded repeated state.
- Keep slow tests focused on high-signal behavior; cap artificial waits where possible.
- Keep one behavioral concern per file and avoid copy-pasted variants.

## Naming Conventions

- Prefer `test_<domain>_<behavior>.py` for new files.
- Keep test names explicit about expected behavior, not implementation details.

## Scope Boundaries

- Performance benchmarks live in `benchmarks/` and are run separately.

## Canonical Suites

- `tests/functional/test_event_ordering.py` is the canonical source for event order
  and lifecycle invariants.
- `tests/functional/test_runtime_contracts.py` should only cover runtime contracts not
  already asserted in event-ordering canonicals.

## Local Mutation Checks

- Mutation testing is configured for local use (not CI-gated yet).
- Install dev dependencies first:
  - `uv sync --all-extras --dev`
- Run mutation checks for configured target modules:
  - `uv run mutmut run`
- Review results:
  - `uv run mutmut results`
  - `uv run mutmut show <mutant-id>`
