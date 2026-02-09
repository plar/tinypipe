"""Unit tests for name resolution utilities."""

from collections.abc import Callable

import pytest
from justpipe._internal.shared.utils import _resolve_name


def sample_step() -> None:
    pass


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("foo", "foo"),
        (sample_step, "sample_step"),
    ],
)
def test_resolve_name_valid(value: str | Callable[..., object], expected: str) -> None:
    assert _resolve_name(value) == expected


def test_resolve_name_invalid() -> None:
    with pytest.raises(ValueError):
        _resolve_name(123)  # type: ignore[arg-type]
