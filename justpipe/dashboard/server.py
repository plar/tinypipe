"""FastAPI application factory for the justpipe dashboard."""

# mypy: ignore-errors
# FastAPI is an optional dependency — stubs unavailable, decorators untyped.

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from justpipe.cli.registry import PipelineRegistry
from justpipe.dashboard.api import DashboardAPI


def create_app(registry: PipelineRegistry, static_dir: Path) -> FastAPI:
    """Build the FastAPI app with API routes and static file serving."""
    app = FastAPI(title="justpipe Dashboard")
    api = DashboardAPI(registry)

    @app.get("/api/pipelines")
    def list_pipelines() -> list[dict]:
        return api.list_pipelines()

    @app.get("/api/pipelines/{pipeline_hash}")
    def get_pipeline(pipeline_hash: str) -> dict:
        result = api.get_pipeline(pipeline_hash)
        if result is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return result

    @app.get("/api/pipelines/{pipeline_hash}/runs")
    def list_runs(
        pipeline_hash: str,
        status: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict]:
        result = api.list_runs(pipeline_hash, status, limit, offset)
        if result is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return result

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        result = api.get_run(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @app.get("/api/runs/{run_id}/events")
    def get_events(
        run_id: str,
        type: str | None = Query(default=None),
    ) -> list[dict]:
        result = api.get_events(run_id, event_type=type)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @app.get("/api/runs/{run_id}/timeline")
    def get_timeline(run_id: str) -> list[dict]:
        result = api.get_timeline(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result

    @app.get("/api/compare")
    def compare(
        run1: str = Query(...),
        run2: str = Query(...),
    ) -> dict:
        result = api.compare(run1, run2)
        if result is None:
            raise HTTPException(status_code=404, detail="One or both runs not found")
        return result

    @app.get("/api/stats/{pipeline_hash}")
    def get_stats(
        pipeline_hash: str,
        days: int = Query(default=7, ge=1, le=365),
    ) -> dict:
        result = api.get_stats(pipeline_hash, days)
        if result is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return result

    # Static files — only mount if built assets exist
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)))

    index_html = static_dir / "index.html"

    resolved_static = static_dir.resolve()

    @app.get("/{path:path}")
    def spa_fallback(path: str) -> FileResponse:
        # Serve specific static files if they exist
        file_path = (static_dir / path).resolve()
        if path and file_path.is_file() and str(file_path).startswith(str(resolved_static)):
            return FileResponse(str(file_path))
        # SPA fallback
        if index_html.is_file():
            return FileResponse(str(index_html))
        raise HTTPException(
            status_code=404,
            detail="Dashboard UI not built. Run 'npm run build' in dashboard-ui/",
        )

    return app
