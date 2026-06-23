"""監控 artifact repository。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MonitoringRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.artifacts_dir = project_root / "artifacts"

    @property
    def factor_report_path(self) -> Path:
        return self.artifacts_dir / "factor_monitor_report.json"

    def load_factor_report(self) -> dict[str, Any] | None:
        if not self.factor_report_path.exists():
            return None
        return json.loads(self.factor_report_path.read_text(encoding="utf-8"))

    def load_top10_harness_rollup(self, run_date: str | None = None, run_id: str | None = None) -> dict[str, Any] | None:
        path = self.top10_harness_rollup_path(run_date=run_date, run_id=run_id)
        if path is None or not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["_artifact_path"] = self.repo_path(path)
            return payload
        return None

    def top10_harness_rollup_path(self, run_date: str | None = None, run_id: str | None = None) -> Path | None:
        root = self.artifacts_dir / "harness_status"
        if run_date and run_id:
            return root / run_date / run_id / "rollup.json"
        if run_date:
            return root / run_date / "latest_rollup.json"
        if not root.exists():
            return None
        candidates = sorted(root.glob("*/latest_rollup.json"), reverse=True)
        return candidates[0] if candidates else None

    def repo_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root.resolve()))
        except ValueError:
            return str(path)

    def clear_cache(self) -> None:
        return None
