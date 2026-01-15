from justpipe.core import Event, EventType, Next

def test_event_creation():
    event = Event(type=EventType.START, stage="system", data={"foo": "bar"})
    assert event.type == EventType.START
    assert event.stage == "system"
    assert event.data == {"foo": "bar"}

def test_next_creation_string():
    next_step = Next(target="step_b")
    assert next_step.target == "step_b"
    assert next_step.stage == "step_b"

def test_next_creation_callable():
    def my_step():
        pass

    next_step = Next(target=my_step)
    assert next_step.target == my_step
    assert next_step.stage == "my_step"

def test_next_creation_none():
    next_step = Next(target=None)
    assert next_step.target is None
    assert next_step.stage is None

def test_next_metadata():
    next_step = Next(target="a", metadata={"priority": 1})
    assert next_step.metadata == {"priority": 1}
