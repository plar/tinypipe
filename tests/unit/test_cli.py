"""CLI command tests."""

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from justpipe.cli.main import cli, get_storage_dir


def test_get_storage_dir_respects_env(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("JUSTPIPE_STORAGE_PATH", str(tmp_path))
    assert get_storage_dir() == tmp_path


def test_get_storage_dir_default(monkeypatch: Any) -> None:
    monkeypatch.delenv("JUSTPIPE_STORAGE_PATH", raising=False)
    assert get_storage_dir() == Path.home() / ".justpipe"


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
