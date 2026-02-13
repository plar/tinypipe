"""Shared fixtures and helpers for runtime unit tests."""

from typing import Any

from justpipe._internal.definition.steps import _StandardStep
from justpipe._internal.runtime.engine.composition import RunnerConfig


async def _noop_step() -> None:
    return None


def single_step_config() -> RunnerConfig[Any, Any]:
    """Create a minimal RunnerConfig with a single no-op step named 'entry'."""
    return RunnerConfig(
        steps={"entry": _StandardStep(name="entry", func=_noop_step)},
        topology={},
        injection_metadata={},
        startup_hooks=[],
        shutdown_hooks=[],
    )
