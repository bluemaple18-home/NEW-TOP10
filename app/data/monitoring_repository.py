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

    def clear_cache(self) -> None:
        return None
