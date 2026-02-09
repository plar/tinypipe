import os
import sys
from typing import Any
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path to allow importing examples
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from examples import utils
except ImportError:
    utils = None  # type: ignore


def test_utils_importable() -> None:
    assert utils is not None, "examples.utils should be importable"


def test_get_api_key_present() -> None:
    with patch.dict(os.environ, {"TEST_KEY": "secret-123"}):
        key = utils.get_api_key("TEST_KEY")
        assert key == "secret-123"


def test_get_api_key_missing(capsys: Any) -> None:
    with patch.dict(os.environ, {}, clear=True):
        key = utils.get_api_key("MISSING_KEY")
        assert key is None
        captured = capsys.readouterr()
        # Verify it printed a warning
        assert (
            "Warning: MISSING_KEY environment variable not set" in captured.out
            or "Warning: MISSING_KEY environment variable not set" in captured.err
        )


def test_save_graph(tmp_path: Path) -> None:
    pipe_mock: Any = MagicMock()
    pipe_mock.graph.return_value = "graph TD; A-->B;"

    filename = tmp_path / "test.mmd"
    utils.save_graph(pipe_mock, filename)

    assert filename.exists()
    assert filename.read_text(encoding="utf-8") == "graph TD; A-->B;"
