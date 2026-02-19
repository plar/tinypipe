"""Tests for CLI main.py dispatch — verifies Click handlers delegate correctly."""

from typing import Any
from unittest.mock import MagicMock

from click.testing import CliRunner

import justpipe.cli.main as cli_main


def test_click_commands_delegate_to_sync_functions(
    monkeypatch: Any,
) -> None:
    """Each Click command should call get_registry() and delegate to a sync command function."""
    calls: list[tuple[str, tuple[Any, ...]]] = []

    fake_registry = MagicMock()
    monkeypatch.setattr(cli_main, "get_registry", lambda: fake_registry)

    def make_fake(name: str) -> Any:
        def fake(*args: Any) -> None:
            calls.append((name, args))

        return fake

    monkeypatch.setattr("justpipe.cli.commands.list.list_command", make_fake("list"))
    monkeypatch.setattr("justpipe.cli.commands.show.show_command", make_fake("show"))
    monkeypatch.setattr(
        "justpipe.cli.commands.timeline.timeline_command", make_fake("timeline")
    )
    monkeypatch.setattr(
        "justpipe.cli.commands.compare.compare_command", make_fake("compare")
    )
    monkeypatch.setattr(
        "justpipe.cli.commands.export.export_command", make_fake("export")
    )
    monkeypatch.setattr(
        "justpipe.cli.commands.cleanup.cleanup_command", make_fake("cleanup")
    )
    monkeypatch.setattr("justpipe.cli.commands.stats.stats_command", make_fake("stats"))
    monkeypatch.setattr(
        "justpipe.cli.commands.pipelines.pipelines_command", make_fake("pipelines")
    )

    runner = CliRunner()

    cases = [
        (["list"], "list"),
        (["show", "abcd1234"], "show"),
        (["timeline", "abcd1234", "--format", "ascii"], "timeline"),
        (["compare", "run1", "run2"], "compare"),
        (["export", "abcd1234", "--format", "json"], "export"),
        (["cleanup", "--older-than", "7", "--dry-run"], "cleanup"),
        (["stats", "--days", "7"], "stats"),
        (["pipelines"], "pipelines"),
    ]

    for argv, expected_name in cases:
        calls.clear()
        result = runner.invoke(cli_main.cli, argv)
        assert result.exit_code == 0, f"{argv}: {result.output}"
        assert len(calls) == 1, f"{argv}: expected 1 call, got {len(calls)}"
        assert calls[0][0] == expected_name
        # First arg is always the registry
        assert calls[0][1][0] is fake_registry


def test_main_invokes_cli_entrypoint(monkeypatch: Any) -> None:
    called = {"value": False}

    def fake_cli() -> None:
        called["value"] = True

    monkeypatch.setattr(cli_main, "cli", fake_cli)
    cli_main.main()

    assert called["value"] is True


def test_get_registry_returns_pipeline_registry(
    monkeypatch: Any, tmp_path: Any
) -> None:
    from justpipe.cli.registry import PipelineRegistry

    monkeypatch.setattr(cli_main, "resolve_storage_path", lambda: tmp_path)

    registry = cli_main.get_registry()
    assert isinstance(registry, PipelineRegistry)
