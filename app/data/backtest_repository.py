"""回測 artifact repository。

此 repository 只讀取既有 artifacts，不觸發回測或模型訓練。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.backtesting.artifacts import BACKTEST_CURVE_PATTERN, BACKTEST_REPORT_PATTERN


class BacktestRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.artifacts_dir = project_root / "artifacts"

    @lru_cache(maxsize=1)
    def list_report_files(self) -> tuple[Path, ...]:
        return self._list_artifacts(BACKTEST_REPORT_PATTERN)

    @lru_cache(maxsize=1)
    def list_curve_files(self) -> tuple[Path, ...]:
        return self._list_artifacts(BACKTEST_CURVE_PATTERN)

    def read_report_text(self, report_path: Path) -> str:
        resolved = report_path.resolve()
        artifacts_root = self.artifacts_dir.resolve()
        if not resolved.is_relative_to(artifacts_root):
            raise ValueError(f"回測報告路徑不在 artifacts 內：{report_path}")
        return resolved.read_text(encoding="utf-8")

    def clear_cache(self) -> None:
        self.list_report_files.cache_clear()
        self.list_curve_files.cache_clear()

    def _list_artifacts(self, pattern: str) -> tuple[Path, ...]:
        if not self.artifacts_dir.exists():
            return ()
        return tuple(
            sorted(
                self.artifacts_dir.glob(pattern),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
