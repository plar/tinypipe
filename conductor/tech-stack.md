# Technology Stack

## Core Development
- **Language:** Python 3.12+
- **Execution Model:** `asyncio` (TaskGroups, Queues)
- **Reliability:** Built-in backpressure and barrier synchronization.
- **Type Checking:** `mypy` (Strict mode)

## Tooling & Infrastructure
- **Dependency & Environment Management:** `uv`
- **Build System:** `hatch` with `hatch-vcs` for versioning
- **Linting & Formatting:** `ruff`

## Testing
- **Framework:** `pytest`
- **Plugins:**
    - `pytest-asyncio`: For async test support
    - `pytest-cov`: For coverage reporting
    - `pytest-repeat`: For stress-testing flaky async code

## Optional Integrations
- **Retries:** `tenacity`
- **Example Integrations:** `openai`, `google-genai`, `rich`
