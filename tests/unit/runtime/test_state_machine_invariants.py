import pytest

from justpipe._internal.runtime.engine.run_state import _RunStateMachine, _RunPhase


def test_single_terminal_transition() -> None:
    sm = _RunStateMachine()
    sm.start_startup()
    sm.start_execution()
    sm.start_shutdown()
    sm.finish_terminal()
    assert sm.phase is _RunPhase.TERMINAL
    with pytest.raises(RuntimeError):
        sm.finish_terminal()
