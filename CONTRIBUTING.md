# Contributing to justpipe

First off, thanks for taking the time to contribute! 🎉

## Development Setup

**justpipe** uses `uv` for dependency management.

1.  **Clone the repo**:
    ```bash
    git clone https://github.com/plar/justpipe.git
    cd justpipe
    ```

2.  **Install dependencies**:
    ```bash
    uv sync --all-extras --dev
    ```

3.  **Run tests**:
    ```bash
    uv run pytest
    ```

## Quality Standards

Before submitting a Pull Request, please ensure:
- All tests pass (`uv run pytest`).
- Code is formatted and linted (`uv run ruff check .`).
- Types are valid (`uv run mypy justpipe`).
- You have added tests for any new functionality.

## Pull Request Process

1.  Fork the repository and create your branch from `main`.
2.  If you've added code that should be tested, add tests.
3.  If you've changed APIs, update the documentation.
4.  Ensure the CI/CD pipeline passes.
