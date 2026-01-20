from justpipe.types import Event, EventType, _Next


def test_event_creation() -> None:
    event = Event(type=EventType.START, stage="system", data={"foo": "bar"})
    assert event.type == EventType.START
    assert event.stage == "system"
    assert event.data == {"foo": "bar"}


def test_next_creation_string() -> None:
    next_step = _Next(target="step_b")
    assert next_step.target == "step_b"
    assert next_step.stage == "step_b"


def test_next_creation_callable() -> None:
    def my_step() -> None:
        pass

    next_step = _Next(target=my_step)
    assert next_step.target == my_step
    assert next_step.stage == "my_step"


def test_next_creation_none() -> None:
    next_step = _Next(target=None)
    assert next_step.target is None
    assert next_step.stage is None


def test_next_metadata() -> None:
    next_step = _Next(target="a", metadata={"priority": 1})
    assert next_step.metadata == {"priority": 1}
