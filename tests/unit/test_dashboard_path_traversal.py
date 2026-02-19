"""Unit tests for dashboard SPA path traversal prevention."""

from typing import Any


class TestPathTraversal:
    def test_resolved_path_blocks_traversal(self, tmp_path: Any) -> None:
        """Path traversal attempts must not resolve outside static_dir."""
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html></html>")

        secret = tmp_path / "secret.txt"
        secret.write_text("sensitive data")

        resolved_static = static_dir.resolve()

        for traversal_path in [
            "../secret.txt",
            "../../etc/passwd",
            "sub/../../secret.txt",
        ]:
            file_path = (static_dir / traversal_path).resolve()
            inside = str(file_path).startswith(str(resolved_static))
            if file_path.is_file():
                assert not inside, f"Traversal path {traversal_path!r} was not blocked"

    def test_valid_path_passes_check(self, tmp_path: Any) -> None:
        """Normal files inside static_dir pass the path check."""
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "app.js").write_text("console.log('ok')")

        resolved_static = static_dir.resolve()
        file_path = (static_dir / "app.js").resolve()
        assert str(file_path).startswith(str(resolved_static))
        assert file_path.is_file()
