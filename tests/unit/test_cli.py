"""CLI command tests."""

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from justpipe._internal.shared.utils import resolve_storage_path
from justpipe.cli.main import cli


def test_resolve_storage_path_respects_env(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("JUSTPIPE_STORAGE_PATH", str(tmp_path))
    assert resolve_storage_path() == tmp_path


def test_resolve_storage_path_default(monkeypatch: Any) -> None:
    monkeypatch.delenv("JUSTPIPE_STORAGE_PATH", raising=False)
    assert resolve_storage_path() == Path.home() / ".justpipe"


def test_cli_help_smoke() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "justpipe" in result.output.lower()


def test_cli_pipelines_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["pipelines", "--help"])
    assert result.exit_code == 0
    assert "pipeline" in result.output.lower()
