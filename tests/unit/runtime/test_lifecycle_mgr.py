import pytest
from unittest.mock import MagicMock
from justpipe.types import EventType, HookSpec, InjectionSource
from justpipe._internal.runtime.orchestration.lifecycle_manager import _LifecycleManager


@pytest.mark.asyncio
async def test_lifecycle_manager_startup_success() -> None:
    hook = MagicMock()
    hook_spec = HookSpec(func=hook, injection_metadata={"s": InjectionSource.STATE})

    manager = _LifecycleManager(startup_hooks=[hook_spec], shutdown_hooks=[])
    res = await manager.execute_startup(state="foo", context="bar")

    assert res is None
    hook.assert_called_once_with(s="foo")


@pytest.mark.asyncio
async def test_lifecycle_manager_startup_failure() -> None:
    hook = MagicMock(side_effect=RuntimeError("Fail"))
    hook_spec = HookSpec(func=hook, injection_metadata={})

    manager = _LifecycleManager(startup_hooks=[hook_spec], shutdown_hooks=[])
    res = await manager.execute_startup(state="foo", context="bar")

    assert res is not None
    assert res.type == EventType.STEP_ERROR
    assert res.stage == "startup"
    assert "Fail" in (res.payload if isinstance(res.payload, str) else "")


@pytest.mark.asyncio
async def test_lifecycle_manager_shutdown() -> None:
    hook = MagicMock()
    hook_spec = HookSpec(func=hook, injection_metadata={"c": InjectionSource.CONTEXT})

    manager = _LifecycleManager(startup_hooks=[], shutdown_hooks=[hook_spec])
    events = []
    async for ev in manager.execute_shutdown(state="foo", context="bar"):
        events.append(ev)

    assert len(events) == 0
    hook.assert_called_once_with(c="bar")


@pytest.mark.asyncio
async def test_lifecycle_manager_startup_stops_on_first_failure() -> None:
    first = MagicMock(side_effect=RuntimeError("first failed"))
    second = MagicMock()
    first_spec = HookSpec(func=first, injection_metadata={})
    second_spec = HookSpec(func=second, injection_metadata={})

    manager = _LifecycleManager(
        startup_hooks=[first_spec, second_spec], shutdown_hooks=[]
    )
    res = await manager.execute_startup(state="foo", context="bar")

    assert res is not None
    assert res.type == EventType.STEP_ERROR
    assert res.stage == "startup"
    assert "first failed" in (res.payload if isinstance(res.payload, str) else "")
    second.assert_not_called()


@pytest.mark.asyncio
async def test_lifecycle_manager_shutdown_yields_all_failures() -> None:
    first = MagicMock(side_effect=RuntimeError("first failed"))
    second = MagicMock(side_effect=RuntimeError("second failed"))
    first_spec = HookSpec(func=first, injection_metadata={})
    second_spec = HookSpec(func=second, injection_metadata={})

    manager = _LifecycleManager(
        startup_hooks=[], shutdown_hooks=[first_spec, second_spec]
    )
    events = [ev async for ev in manager.execute_shutdown(state="foo", context="bar")]

    assert len(events) == 2
    assert all(ev.type == EventType.STEP_ERROR for ev in events)
    assert all(ev.stage == "shutdown" for ev in events)
    assert "first failed" in str(events[0].payload)
    assert "second failed" in str(events[1].payload)
