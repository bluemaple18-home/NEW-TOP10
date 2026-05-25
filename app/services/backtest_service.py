"""回測資料 service。

這層只把既有回測 artifacts 組成 API-friendly contract，不執行回測。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.backtesting.report_parser import parse_backtest_report_metrics
from app.contracts.backtest import BacktestArtifact, BacktestReportSummary, BacktestSummaryResponse
from app.data.backtest_repository import BacktestRepository


class BacktestService:
    def __init__(self, repository: BacktestRepository):
        self.repository = repository

    def summary(self) -> BacktestSummaryResponse:
        curves = [
            self._artifact(curve_path, "curve")
            for curve_path in self.repository.list_curve_files()
        ]
        curve_by_suffix = {
            self._artifact_suffix(curve.path, "backtest_curve"): curve.path
            for curve in curves
        }

        reports = [
            self._report_summary(report_path, curve_by_suffix)
            for report_path in self.repository.list_report_files()
        ]
        return BacktestSummaryResponse(reports=reports, curves=curves)

    def clear_cache(self) -> None:
        self.repository.clear_cache()

    def _report_summary(self, report_path: Path, curve_by_suffix: dict[str, str]) -> BacktestReportSummary:
        text = self.repository.read_report_text(report_path)
        artifact = self._artifact(report_path, "report")
        suffix = self._artifact_suffix(artifact.path, "backtest_report")
        return BacktestReportSummary(
            name=artifact.name,
            path=artifact.path,
            title=self._extract_title(text),
            excerpt=self._extract_excerpt(text),
            curve_path=curve_by_suffix.get(suffix),
            **parse_backtest_report_metrics(text, report_path),
            size_bytes=artifact.size_bytes,
            modified_at=artifact.modified_at,
        )

    def _artifact(self, path: Path, kind: str) -> BacktestArtifact:
        stat = path.stat()
        return BacktestArtifact(
            name=path.name,
            path=self._relative_path(path),
            kind=kind,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )

    def _relative_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.repository.project_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _artifact_suffix(self, artifact_path: str, prefix: str) -> str:
        stem = Path(artifact_path).stem
        return stem.removeprefix(prefix)

    def _extract_title(self, text: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or None
        return None

    def _extract_excerpt(self, text: str, max_chars: int = 240) -> str | None:
        paragraphs = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not paragraphs:
            return None

        excerpt = " ".join(paragraphs)
        if len(excerpt) <= max_chars:
            return excerpt
        return f"{excerpt[: max_chars - 1].rstrip()}..."
