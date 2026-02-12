"""Consolidated tests for CLI commands."""

import json
import time
from pathlib import Path
from typing import Any
import pytest
from click.testing import CliRunner
from justpipe.storage import InMemoryStorage
from justpipe.cli.commands.cleanup import cleanup_command
from justpipe.cli.commands.compare import compare_command
from justpipe.cli.commands.export import export_command
from justpipe.cli.commands.list import list_command
from justpipe.cli.commands.show import show_command
from justpipe.cli.commands.stats import stats_command
from justpipe.cli.commands.timeline import timeline_command
from justpipe.cli.main import cli, get_storage_dir
from justpipe.types import Event, EventType


@pytest.fixture
async def storage_with_runs() -> InMemoryStorage:
    """Create storage with test runs."""
    storage = InMemoryStorage()

    # Create runs with different statuses and ages
    now = time.time()
    seven_days_ago = now - (7 * 86400)
    thirty_days_ago = now - (30 * 86400)

    # Recent successful runs
    for i in range(5):
        run_id = await storage.create_run(f"pipeline_{i % 2}", {})
        await storage.update_run(run_id, status="success", duration=0.1)

    # Old successful run - modify the storage directly
    run_id = await storage.create_run("old_pipeline", {})
    # Access internal storage to modify start_time
    storage.runs[run_id].start_time = thirty_days_ago
    await storage.update_run(run_id, status="success", duration=0.1)

    # Recent error run
    run_id = await storage.create_run("error_pipeline", {})
    await storage.update_run(run_id, status="error", error_message="Test error")

    # Old error run - modify the storage directly
    run_id = await storage.create_run("old_error", {})
    storage.runs[run_id].start_time = seven_days_ago
    await storage.update_run(run_id, status="error", error_message="Old error")

    return storage


@pytest.fixture
async def storage_with_comparable_runs() -> tuple[InMemoryStorage, str, str]:
    """Create two runs with deterministic events for compare/show/export/timeline."""
    storage = InMemoryStorage()
    now = time.time()

    run1 = await storage.create_run("pipeline_compare", {"version": "v1"})
    storage.runs[run1].start_time = now - 20.0
    await storage.update_run(
        run1,
        status="success",
        end_time=(now - 19.2),
        duration=0.8,
    )
    await storage.add_event(
        run1,
        Event(EventType.STEP_START, "step_a", None, timestamp=now - 19.95),
    )
    await storage.add_event(
        run1,
        Event(EventType.STEP_END, "step_a", None, timestamp=now - 19.55),
    )

    run2 = await storage.create_run("pipeline_compare", {"version": "v2"})
    storage.runs[run2].start_time = now - 10.0
    await storage.update_run(
        run2,
        status="success",
        end_time=(now - 8.8),
        duration=1.2,
    )
    await storage.add_event(
        run2,
        Event(EventType.STEP_START, "step_a", None, timestamp=now - 9.95),
    )
    await storage.add_event(
        run2,
        Event(EventType.STEP_END, "step_a", None, timestamp=now - 9.2),
    )
    await storage.add_event(
        run2,
        Event(EventType.STEP_START, "step_b", None, timestamp=now - 9.1),
    )
    await storage.add_event(
        run2,
        Event(EventType.STEP_END, "step_b", None, timestamp=now - 8.9),
    )

    return storage, run1, run2


async def test_cleanup_dry_run(storage_with_runs: InMemoryStorage, capsys: Any) -> None:
    """Test cleanup with dry run mode."""
    # Cleanup runs older than 25 days (should find 1)
    # Use keep=0 to allow deletion of old runs
    await cleanup_command(
        storage_with_runs,
        older_than_days=25,
        keep=0,
        dry_run=True,
    )

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "1 run(s) to clean up" in captured.out
    assert "old_pipeline" in captured.out

    # Verify nothing was actually deleted
    all_runs = await storage_with_runs.list_runs(limit=100)
    assert len(all_runs) == 8  # All runs still there


async def test_cleanup_status_filter(
    storage_with_runs: InMemoryStorage, capsys: Any
) -> None:
    """Test cleanup with status filter."""
    # Cleanup only error runs (should find 2)
    await cleanup_command(
        storage_with_runs,
        status="error",
        keep=0,
        dry_run=True,
    )

    captured = capsys.readouterr()
    assert "2 run(s) to clean up" in captured.out
    assert "error" in captured.out.lower()


async def test_cleanup_keep_recent(
    storage_with_runs: InMemoryStorage, capsys: Any
) -> None:
    """Test cleanup keeps N most recent runs."""
    # Keep only 3 most recent runs
    await cleanup_command(
        storage_with_runs,
        keep=3,
        dry_run=True,
    )

    captured = capsys.readouterr()
    # Should try to delete 5 runs (8 total - 3 kept)
    assert "5 run(s) to clean up" in captured.out


async def test_stats_basic(storage_with_runs: InMemoryStorage, capsys: Any) -> None:
    """Test basic stats command."""
    await stats_command(storage_with_runs, days=30)

    captured = capsys.readouterr()
    assert "Total Runs:" in captured.out
    assert "Status Breakdown:" in captured.out
    assert "Success" in captured.out
    assert "Error" in captured.out
    assert "Duration Statistics:" in captured.out


async def test_stats_pipeline_filter(
    storage_with_runs: InMemoryStorage, capsys: Any
) -> None:
    """Test stats with pipeline filter."""
    await stats_command(storage_with_runs, pipeline="pipeline_0", days=7)

    captured = capsys.readouterr()
    assert "pipeline_0" in captured.out
    # Should show fewer runs than total
    assert "Total Runs:" in captured.out


async def test_stats_shows_recent_errors(
    storage_with_runs: InMemoryStorage, capsys: Any
) -> None:
    """Test that stats shows recent errors."""
    await stats_command(storage_with_runs, days=30)

    captured = capsys.readouterr()
    assert "Recent Errors:" in captured.out
    assert "Most Recent Errors:" in captured.out
    assert "error" in captured.out.lower()


async def test_stats_no_runs() -> None:
    """Test stats with no runs."""
    storage = InMemoryStorage()

    # Should handle gracefully
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        await stats_command(storage, days=7)

    output = f.getvalue()
    assert "No runs found" in output


async def test_cleanup_no_runs() -> None:
    """Test cleanup with no runs."""
    storage = InMemoryStorage()

    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        await cleanup_command(storage, dry_run=True)

    output = f.getvalue()
    assert "No runs found" in output


async def test_list_command_basic_output(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str], capsys: Any
) -> None:
    storage, _, _ = storage_with_comparable_runs
    await list_command(storage, pipeline="pipeline_compare", limit=10, full_ids=False)

    out = capsys.readouterr().out
    assert "pipeline_compare" in out
    assert "Showing 2 run(s)" in out


async def test_show_command_with_prefix(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str], capsys: Any
) -> None:
    storage, run1, _ = storage_with_comparable_runs
    await show_command(storage, run1[:8])

    out = capsys.readouterr().out
    assert f"Run: {run1}" in out
    assert "Event Breakdown:" in out
    assert "Step Sequence:" in out


async def test_export_command_writes_json(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str],
    capsys: Any,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    storage, run1, _ = storage_with_comparable_runs
    monkeypatch.chdir(tmp_path)

    await export_command(storage, run1[:8], format="json")

    out = capsys.readouterr().out
    expected_file = tmp_path / f"run_{run1[:8]}.json"
    assert expected_file.exists()
    assert "Run exported to" in out

    payload = json.loads(expected_file.read_text())
    assert payload["run"]["id"] == run1
    assert payload["event_count"] >= 1


async def test_compare_command_outputs_report(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str], capsys: Any
) -> None:
    storage, run1, run2 = storage_with_comparable_runs
    await compare_command(storage, run1[:8], run2[:8])

    out = capsys.readouterr().out
    assert "Run Comparison" in out
    assert "Duration:" in out


async def test_timeline_command_ascii_output(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str], capsys: Any
) -> None:
    storage, run1, _ = storage_with_comparable_runs
    await timeline_command(storage, run1[:8], format="ascii")

    out = capsys.readouterr().out
    assert "Execution Timeline" in out
    assert "pipeline_compare" in out


async def test_timeline_command_writes_mermaid_file(
    storage_with_comparable_runs: tuple[InMemoryStorage, str, str],
    capsys: Any,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    storage, run1, _ = storage_with_comparable_runs
    monkeypatch.chdir(tmp_path)
    await timeline_command(storage, run1[:8], format="mermaid")

    out = capsys.readouterr().out
    expected_file = tmp_path / f"timeline_{run1[:8]}.mmd"
    assert expected_file.exists()
    assert "Mermaid diagram saved to" in out
    assert "gantt" in expected_file.read_text()


def test_get_storage_dir_respects_env(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("JUSTPIPE_STORAGE_DIR", str(tmp_path))
    assert get_storage_dir() == tmp_path


def test_cli_help_smoke() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "justpipe" in result.output.lower()
