from collections import defaultdict


class _ExecutionTracker:
    """Internal component for tracking execution state and task accounting."""

    def __init__(self) -> None:
        self.total_active_tasks: int = 0
        self.logical_active: dict[str, int] = defaultdict(int)
        self.skipped_owners: set[str] = set()
        self.stopping: bool = False

    @property
    def is_active(self) -> bool:
        """Return True if there are any physical tasks remaining."""
        return self.total_active_tasks > 0

    def record_spawn(self, owner: str, track_owner: bool = True) -> None:
        """Record that a new physical task has been spawned."""
        if track_owner:
            self.logical_active[owner] += 1
        self.total_active_tasks += 1

    def record_physical_completion(self) -> None:
        """Record that a physical task has finished."""
        self.total_active_tasks -= 1

    def record_logical_completion(self, owner: str) -> bool:
        """
        Record that a logical step task has finished.

        Returns:
            True if this was the last task for the logical owner.
        """
        self.logical_active[owner] -= 1
        return self.logical_active[owner] == 0

    def request_stop(self) -> None:
        """Mark the run as stopping (e.g. on SUSPEND or Stop)."""
        self.stopping = True

    def mark_skipped(self, owner: str) -> None:
        """Record that a step owner has been skipped (e.g. dynamic routing)."""
        self.skipped_owners.add(owner)

    def is_skipped(self, owner: str) -> bool:
        """Check if an owner was marked as skipped."""
        return owner in self.skipped_owners

    def consume_skip(self, owner: str) -> bool:
        """Check if an owner was skipped and remove it from the skip set if it was."""
        if owner in self.skipped_owners:
            self.skipped_owners.discard(owner)
            return True
        return False
