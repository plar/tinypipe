"""Tests for CLI formatting utilities."""

from datetime import datetime

import pytest

from justpipe.cli.formatting import (
    format_duration,
    format_status,
    format_timestamp,
    short_id,
)
from justpipe.types import PipelineTerminalStatus


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        pytest.param(None, "-", id="none"),
        pytest.param(0.001, "1ms", id="1ms"),
        pytest.param(0.5, "500ms", id="500ms"),
        pytest.param(1.0, "1.0s", id="1s"),
        pytest.param(30.5, "30.5s", id="30s"),
        pytest.param(120.0, "2.0m", id="2m"),
        pytest.param(7200.0, "2.0h", id="2h"),
    ],
)
def test_format_duration(duration: float | None, expected: str) -> None:
    assert format_duration(duration) == expected


def test_format_timestamp() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45)
    assert format_timestamp(dt) == "2024-01-15 12:30:45"


def test_format_status_success() -> None:
    result = format_status(PipelineTerminalStatus.SUCCESS)
    assert "green" in result
    assert "success" in result


def test_format_status_failed() -> None:
    result = format_status(PipelineTerminalStatus.FAILED)
    assert "red" in result
    assert "failed" in result


def test_format_status_timeout() -> None:
    result = format_status(PipelineTerminalStatus.TIMEOUT)
    assert "yellow" in result
    assert "timeout" in result


def test_short_id_truncated() -> None:
    full = "a" * 32
    assert short_id(full) == "aaaaaaaaaaaa..."


def test_short_id_full() -> None:
    full = "a" * 32
    assert short_id(full, full=True) == full
