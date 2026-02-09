from justpipe._internal.shared.execution_tracker import _ExecutionTracker


def test_tracker_initial_state() -> None:
    tracker = _ExecutionTracker()
    assert not tracker.is_active
    assert not tracker.stopping


def test_tracker_spawn_increments() -> None:
    tracker = _ExecutionTracker()
    tracker.record_spawn("owner1")
    assert tracker.is_active
    assert tracker.total_active_tasks == 1
    assert tracker.logical_active["owner1"] == 1


def test_tracker_completion_decrements() -> None:
    tracker = _ExecutionTracker()
    tracker.record_spawn("owner1")
    tracker.record_physical_completion()
    is_finished = tracker.record_logical_completion("owner1")

    assert is_finished
    assert not tracker.is_active
    assert tracker.total_active_tasks == 0
    assert tracker.logical_active["owner1"] == 0


def test_tracker_granular_completion() -> None:
    tracker = _ExecutionTracker()
    tracker.record_spawn("owner1")

    # Decrement physical only
    tracker.record_physical_completion()
    assert tracker.total_active_tasks == 0
    assert not tracker.is_active
    assert tracker.logical_active["owner1"] == 1  # Still logically active

    # Decrement logical
    is_finished = tracker.record_logical_completion("owner1")
    assert is_finished
    assert tracker.logical_active["owner1"] == 0


def test_tracker_multiple_logical_tasks() -> None:
    tracker = _ExecutionTracker()
    tracker.record_spawn("owner1")
    tracker.record_spawn("owner1")

    # First completion should NOT finish the logical step
    tracker.record_physical_completion()
    is_finished = tracker.record_logical_completion("owner1")
    assert not is_finished
    assert tracker.is_active
    assert tracker.total_active_tasks == 1
    assert tracker.logical_active["owner1"] == 1

    # Second completion SHOULD finish it
    tracker.record_physical_completion()
    is_finished = tracker.record_logical_completion("owner1")
    assert is_finished
    assert not tracker.is_active


def test_tracker_non_tracked_owner() -> None:
    tracker = _ExecutionTracker()
    # Barrier tasks are often not tracked as logical step owners
    tracker.record_spawn("barrier1", track_owner=False)

    assert tracker.is_active
    assert tracker.total_active_tasks == 1
    assert tracker.logical_active["barrier1"] == 0

    tracker.record_physical_completion()
    assert not tracker.is_active


def test_tracker_stop_request() -> None:
    tracker = _ExecutionTracker()
    tracker.request_stop()
    assert tracker.stopping


def test_tracker_skipping() -> None:
    tracker = _ExecutionTracker()
    tracker.mark_skipped("owner1")
    assert "owner1" in tracker.skipped_owners

    tracker.mark_skipped("owner2")
    assert tracker.is_skipped("owner2")
    assert not tracker.is_skipped("owner3")

    assert tracker.consume_skip("owner2")
    assert not tracker.is_skipped("owner2")
