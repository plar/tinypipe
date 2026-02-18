"""Dashboard command — starts the web UI server."""

from __future__ import annotations

import importlib.resources
import webbrowser
from pathlib import Path

from justpipe.cli.registry import PipelineRegistry


def dashboard_command(
    registry: PipelineRegistry,
    port: int = 8741,
    no_open: bool = False,
) -> None:
    """Start the dashboard HTTP server."""
    try:
        import uvicorn  # noqa: F401
        from fastapi import FastAPI  # noqa: F401
    except ImportError:
        print("Dashboard requires extra dependencies. Install with:")
        print("  pip install justpipe[dashboard]")
        return

    from justpipe.dashboard.server import create_app

    static_dir = Path(str(importlib.resources.files("justpipe.dashboard") / "static"))

    app = create_app(registry, static_dir)

    url = f"http://localhost:{port}"
    print(f"Dashboard running at {url}")
    print("Press Ctrl+C to stop.")

    if not no_open:
        webbrowser.open(url)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
