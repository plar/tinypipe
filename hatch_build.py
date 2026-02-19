"""Hatch custom build hook — runs Vite build for dashboard UI."""

from __future__ import annotations

import os
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:  # type: ignore[override]
        if os.environ.get("SKIP_DASHBOARD_BUILD"):
            return
        dashboard_dir = os.path.join(self.root, "dashboard-ui")
        if os.path.exists(os.path.join(dashboard_dir, "package.json")):
            subprocess.run(["npm", "ci"], cwd=dashboard_dir, check=True)
            subprocess.run(
                ["npm", "run", "build"], cwd=dashboard_dir, check=True
            )
