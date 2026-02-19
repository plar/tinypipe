import pytest

from justpipe._internal.runtime.engine.run_state import (
    _RunSession,
    _RunStateMachine,
    _RunPhase,
)
from justpipe.types import PipelineTerminalStatus


def test_single_terminal_transition() -> None:
    sm = _RunStateMachine()
    sm.start_startup()
    sm.start_execution()
    sm.start_shutdown()
    sm.finish_terminal()
    assert sm.phase is _RunPhase.TERMINAL
    with pytest.raises(RuntimeError):
        sm.finish_terminal()


def test_state_machine_invalid_transition() -> None:
    sm = _RunStateMachine()
    with pytest.raises(RuntimeError):
        sm.start_execution()


def test_session_records_terminal_once() -> None:
    session = _RunSession()
    end = session.close(PipelineTerminalStatus.SUCCESS)
    assert end.status == PipelineTerminalStatus.SUCCESS
    with pytest.raises(RuntimeError):
        session.close(PipelineTerminalStatus.SUCCESS)
