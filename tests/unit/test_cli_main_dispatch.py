from typing import Any

import pytest
from click.testing import CliRunner

import justpipe.cli.main as cli_main


@pytest.mark.parametrize(
    "argv",
    [
        ["list"],
        ["show", "abcd1234"],
        ["timeline", "abcd1234", "--format", "ascii"],
        ["compare", "run1", "run2"],
        ["export", "abcd1234", "--format", "json"],
        ["cleanup", "--older-than", "7", "--dry-run"],
        ["stats", "--days", "7"],
    ],
)
def test_click_command_wrappers_delegate_to_asyncio_run(
    monkeypatch: Any, argv: list[str]
) -> None:
    calls: list[Any] = []

    def fake_run(coro: Any) -> None:
        calls.append(coro)
        coro.close()

    monkeypatch.setattr("justpipe.cli.main.asyncio.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli_main.cli, argv)

    assert result.exit_code == 0
    assert len(calls) == 1


def test_main_invokes_cli_entrypoint(monkeypatch: Any) -> None:
    called = {"value": False}

    def fake_cli() -> None:
        called["value"] = True

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    cli_main.main()

    assert called["value"] is True


def test_get_storage_builds_sqlite_storage(monkeypatch: Any, tmp_path: Any) -> None:
    class DummyStorage:
        def __init__(self, path: str):
            self.path = path

    monkeypatch.setattr(cli_main, "get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr("justpipe.storage.SQLiteStorage", DummyStorage)

    storage = cli_main.get_storage()
    assert isinstance(storage, DummyStorage)
    assert storage.path == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("func_name", "command_path", "args"),
    [
        (
            "list_runs",
            "justpipe.cli.commands.list.list_command",
            ("p", "success", 5, True),
        ),
        ("show_run", "justpipe.cli.commands.show.show_command", ("run-1",)),
        (
            "timeline_run",
            "justpipe.cli.commands.timeline.timeline_command",
            ("run-1", "ascii"),
        ),
        (
            "compare_runs_cli",
            "justpipe.cli.commands.compare.compare_command",
            ("run-1", "run-2"),
        ),
        (
            "export_run",
            "justpipe.cli.commands.export.export_command",
            ("run-1", "out.json", "json"),
        ),
        (
            "cleanup_runs",
            "justpipe.cli.commands.cleanup.cleanup_command",
            (7, "error", 3, True),
        ),
        ("show_stats", "justpipe.cli.commands.stats.stats_command", ("p", 14)),
    ],
)
async def test_async_cli_helpers_delegate_to_command_functions(
    monkeypatch: Any,
    func_name: str,
    command_path: str,
    args: tuple[Any, ...],
) -> None:
    storage = object()
    calls: list[tuple[Any, ...]] = []

    async def fake_command(*inner_args: Any) -> None:
        calls.append(inner_args)

    monkeypatch.setattr(cli_main, "get_storage", lambda: storage)
    monkeypatch.setattr(command_path, fake_command)

    target = getattr(cli_main, func_name)
    await target(*args)

    assert len(calls) == 1
    assert calls[0][0] is storage
