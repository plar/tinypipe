"""Unit tests for Pipe constructor and configuration properties."""

from typing import Any

from justpipe import Pipe
from justpipe.types import CancellationToken


def test_queue_size_default_is_bounded() -> None:
    pipe: Pipe[Any, Any] = Pipe()
    assert pipe.queue_size == 1000


def test_queue_size_can_be_set_to_unbounded() -> None:
    pipe: Pipe[Any, Any] = Pipe(queue_size=0)
    assert pipe.queue_size == 0


def test_cancellation_token_per_pipeline() -> None:
    cancel1 = CancellationToken()
    cancel2 = CancellationToken()

    pipe1: Pipe[Any, Any] = Pipe(cancellation_token=cancel1)
    pipe2: Pipe[Any, Any] = Pipe(cancellation_token=cancel2)

    assert pipe1.cancellation_token is cancel1
    assert pipe2.cancellation_token is cancel2
    assert cancel1 is not cancel2


def test_default_cancellation_token_created() -> None:
    pipe: Pipe[Any, Any] = Pipe()

    assert pipe.cancellation_token is not None
    assert isinstance(pipe.cancellation_token, CancellationToken)
    assert not pipe.cancellation_token.is_cancelled()
