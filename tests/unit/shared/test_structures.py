from justpipe.types import Event, EventType, _Next
from justpipe._internal.shared.utils import _resolve_name


def test_event_creation() -> None:
    event = Event(type=EventType.START, stage="system", payload={"foo": "bar"})
    assert event.type == EventType.START
    assert event.stage == "system"
    assert event.payload == {"foo": "bar"}


def test_next_creation_string() -> None:
    next_step = _Next(target="step_b")
    assert next_step.target == "step_b"
    assert _resolve_name(next_step.target) == "step_b"


def test_next_creation_callable() -> None:
    def my_step() -> None:
        pass

    next_step = _Next(target=my_step)
    assert next_step.target == my_step
    assert _resolve_name(next_step.target) == "my_step"


def test_next_creation_none() -> None:
    next_step = _Next(target=None)
    assert next_step.target is None
    # Cannot call _resolve_name on None as per its type hints and implementation


def test_next_metadata() -> None:
    next_step = _Next(target="a")
    assert next_step.target == "a"
