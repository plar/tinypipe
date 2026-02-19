import asyncio


from justpipe._internal.runtime.orchestration.runtime_kernel import _RuntimeKernel
from justpipe._internal.shared.execution_tracker import _ExecutionTracker


async def test_submit_records_queue_depth() -> None:
    tracker = _ExecutionTracker()
    queue: asyncio.Queue[object] = asyncio.Queue(maxsize=2)
    kernel = _RuntimeKernel(tracker, queue)

    queue_depths: list[int] = []
    kernel.set_hooks(on_submit_queue_depth=queue_depths.append)

    await kernel.submit(object())
    assert queue_depths == [1]


async def test_spawn_returns_none_without_task_group() -> None:
    tracker = _ExecutionTracker()
    queue: asyncio.Queue[object] = asyncio.Queue()
    kernel = _RuntimeKernel(tracker, queue)

    async def work() -> None:
        return None

    task = kernel.spawn(work(), "owner")
    assert task is None
    assert tracker.total_active_tasks == 0


async def test_spawn_uses_task_group_and_records_active_tasks() -> None:
    tracker = _ExecutionTracker()
    queue: asyncio.Queue[object] = asyncio.Queue()
    kernel = _RuntimeKernel(tracker, queue)

    spawn_counts: list[int] = []
    kernel.set_hooks(on_spawn=spawn_counts.append)

    did_run = asyncio.Event()

    async def work() -> None:
        did_run.set()

    async with asyncio.TaskGroup() as tg:
        kernel.attach_task_group(tg)
        task = kernel.spawn(work(), "owner")
        assert task is not None

    assert did_run.is_set()
    assert spawn_counts == [1]
    assert tracker.total_active_tasks == 1
