"""Unit tests for CancellationToken behavior."""

import pytest

from justpipe.types import CancellationToken, PipelineCancelled


def test_cancellation_token_is_cancelled() -> None:
    cancel = CancellationToken()

    assert not cancel.is_cancelled()

    cancel.cancel("Test cancellation")

    assert cancel.is_cancelled()
    assert cancel.reason == "Test cancellation"


@pytest.mark.asyncio
async def test_cancellation_token_checkpoint_before_cancel() -> None:
    cancel = CancellationToken()

    # Should not raise
    await cancel.checkpoint()


@pytest.mark.asyncio
async def test_cancellation_token_checkpoint_after_cancel() -> None:
    cancel = CancellationToken()
    cancel.cancel("Already cancelled")

    with pytest.raises(PipelineCancelled) as exc_info:
        await cancel.checkpoint()

    assert "Already cancelled" in str(exc_info.value)


def test_cancellation_token_default_reason() -> None:
    cancel = CancellationToken()
    cancel.cancel()  # No reason provided

    assert cancel.is_cancelled()
    assert cancel.reason == "Cancelled"


def test_cancellation_token_multiple_cancels() -> None:
    cancel = CancellationToken()
    cancel.cancel("First reason")
    cancel.cancel("Second reason")  # Should be ignored

    assert cancel.reason == "First reason"
