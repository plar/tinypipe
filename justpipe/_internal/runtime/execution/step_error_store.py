from __future__ import annotations


class _StepErrorStore:
    """Encapsulates the error correlation between fail_step() and the queue loop."""

    def __init__(self) -> None:
        self._errors: dict[str, list[Exception]] = {}

    def record(self, name: str, error: Exception) -> None:
        self._errors.setdefault(name, []).append(error)

    def consume(self, name: str) -> Exception | None:
        errors = self._errors.get(name)
        if not errors:
            return None
        error = errors.pop(0)
        if not errors:
            del self._errors[name]
        return error
