"""Factor IC / coverage / turnover 監控。

這層只產生研究證據，不直接調整排名權重。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from app.labels import LabelGenerator


@dataclass(frozen=True)
class FactorMetric:
    factor: str
    coverage: float
    latest_coverage: float
    ic: float | None
    ic_median: float | None
    ic_tstat: float | None
    ic_days: int
    recent_ic: float | None
    turnover: float | None
    observations: int
    status: str
    notes: str


@dataclass(frozen=True)
class FactorMonitorReport:
    status: str
    generated_at: str
    horizon_days: int
    factors: list[FactorMetric]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "horizon_days": self.horizon_days,
            "summary": self.summary,
            "factors": [asdict(factor) for factor in self.factors],
        }


class FactorMonitor:
    def __init__(
        self,
        data_dir: str | Path = "data/clean",
        artifacts_dir: str | Path = "artifacts",
        config_path: str | Path = "config/signals.yaml",
        horizon: int = 10,
        min_observations: int = 100,
        min_ic_days: int = 5,
    ):
        self.data_dir = Path(data_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.config_path = Path(config_path)
        self.horizon = horizon
        self.min_observations = min_observations
        self.min_ic_days = min_ic_days

    def run(self, recent_days: int = 60) -> FactorMonitorReport:
        df = self._load_model_frame()
        factors = self._select_factors(df)
        metrics = [self._metric_for_factor(df, factor, recent_days=recent_days) for factor in factors]
        status = "OK" if not any(metric.status == "WARN" for metric in metrics) else "WARN"
        report = FactorMonitorReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            horizon_days=self.horizon,
            factors=metrics,
            summary=self._summary(metrics),
        )
        self._write_report(report)
        return report

    def _load_model_frame(self) -> pd.DataFrame:
        features_path = self.data_dir / "features.parquet"
        if not features_path.exists():
            raise FileNotFoundError(f"找不到 features：{features_path}")

        features = pd.read_parquet(features_path)
        features["date"] = pd.to_datetime(features["date"])
        features["trade_date"] = features["date"].dt.normalize()
        features["stock_id"] = features["stock_id"].astype(str).str.strip()
        _ensure_unique_trade_keys(features, "features.parquet")

        events_path = self.data_dir / "events.parquet"
        if events_path.exists():
            events = pd.read_parquet(events_path)
            events["date"] = pd.to_datetime(events["date"])
            events["trade_date"] = events["date"].dt.normalize()
            events["stock_id"] = events["stock_id"].astype(str).str.strip()
            _ensure_unique_trade_keys(events, "events.parquet")
            event_cols = [col for col in events.columns if col not in {"date", "trade_date", "stock_id"} and col not in features.columns]
            if event_cols:
                features = features.merge(events[["trade_date", "stock_id"] + event_cols], on=["trade_date", "stock_id"], how="left")

        # LabelGenerator 是日頻邏輯；統一 date 為交易日，避免 timestamp 影響 shift 順序。
        features["date"] = features["trade_date"]
        labeled = LabelGenerator(horizon=self.horizon).generate_labels(features)
        labeled = labeled.dropna(subset=["future_return"]).copy()
        return labeled.sort_values(["trade_date", "stock_id"])

    def _select_factors(self, df: pd.DataFrame) -> list[str]:
        config_factors = self._config_weight_factors()
        numeric_cols = df.select_dtypes(include=[np.number, bool]).columns.tolist()
        excluded = {
            "open",
            "high",
            "low",
            "close",
            "volume",
            "entry_price",
            "exit_price",
            "future_close",
            "future_return",
            "return_long",
            "return_5d",
            "target",
        }
        candidates = [factor for factor in config_factors if factor in df.columns]
        candidates.extend(col for col in numeric_cols if col not in excluded and col not in candidates)
        return candidates[:60]

    def _config_weight_factors(self) -> list[str]:
        if not self.config_path.exists():
            return []
        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        weights = config.get("scoring", {}).get("weights", {})
        return list(weights.keys())

    def _metric_for_factor(self, df: pd.DataFrame, factor: str, recent_days: int) -> FactorMetric:
        values = pd.to_numeric(df[factor], errors="coerce")
        returns = pd.to_numeric(df["future_return"], errors="coerce")
        valid = pd.DataFrame({"factor": values, "future_return": returns, "trade_date": df["trade_date"], "stock_id": df["stock_id"]}).dropna()
        latest_date = df["trade_date"].max()
        latest_coverage = float(values[df["trade_date"] == latest_date].notna().mean())
        coverage = float(values.notna().mean())
        daily_ic = _daily_cross_sectional_ic(valid)
        ic = float(daily_ic.mean()) if len(valid) >= self.min_observations and not daily_ic.empty else None
        ic_median = float(daily_ic.median()) if not daily_ic.empty else None
        ic_tstat = _t_stat(daily_ic)

        recent_cutoff = latest_date - pd.Timedelta(days=recent_days)
        recent = valid[valid["trade_date"] >= recent_cutoff]
        recent_daily_ic = _daily_cross_sectional_ic(recent)
        recent_ic = float(recent_daily_ic.mean()) if len(recent) >= max(30, self.min_observations // 2) and not recent_daily_ic.empty else None
        turnover = _factor_turnover(valid)

        status, notes = self._status_for(
            coverage=coverage,
            latest_coverage=latest_coverage,
            ic=ic,
            ic_days=len(daily_ic),
            observations=len(valid),
        )
        return FactorMetric(
            factor=factor,
            coverage=round(coverage, 4),
            latest_coverage=round(latest_coverage, 4),
            ic=round(ic, 4) if ic is not None else None,
            ic_median=round(ic_median, 4) if ic_median is not None else None,
            ic_tstat=round(ic_tstat, 4) if ic_tstat is not None else None,
            ic_days=int(len(daily_ic)),
            recent_ic=round(recent_ic, 4) if recent_ic is not None else None,
            turnover=round(turnover, 4) if turnover is not None else None,
            observations=len(valid),
            status=status,
            notes=notes,
        )

    def _status_for(self, coverage: float, latest_coverage: float, ic: float | None, ic_days: int, observations: int) -> tuple[str, str]:
        if observations < self.min_observations:
            return "WARN", "有效樣本不足"
        if latest_coverage < 0.8:
            return "WARN", "最新交易日覆蓋率偏低"
        if coverage < 0.6:
            return "WARN", "整體覆蓋率偏低"
        if ic is None or ic_days < self.min_ic_days:
            return "WARN", "可計算 IC 的交易日不足，無法驗證訊號價值"
        if ic is not None and abs(ic) < 0.005:
            return "WARN", "IC 接近 0，需觀察是否仍有訊號價值"
        return "OK", "可進一步評估"

    def _summary(self, metrics: list[FactorMetric]) -> dict[str, Any]:
        ok_count = sum(metric.status == "OK" for metric in metrics)
        warn_count = len(metrics) - ok_count
        ranked_ic = sorted(
            [metric for metric in metrics if metric.ic is not None],
            key=lambda metric: abs(metric.ic or 0),
            reverse=True,
        )
        return {
            "factor_count": len(metrics),
            "ok_count": ok_count,
            "warn_count": warn_count,
            "top_abs_ic": [{"factor": metric.factor, "ic": metric.ic} for metric in ranked_ic[:10]],
        }

    def _write_report(self, report: FactorMonitorReport) -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifacts_dir / "factor_monitor_report.json"
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    value = left.corr(right, method="spearman")
    if pd.isna(value):
        return None
    return float(value)


def _daily_cross_sectional_ic(valid: pd.DataFrame) -> pd.Series:
    """每日橫斷面 Spearman IC，避免 pooled IC 混入市場 regime。"""
    if valid.empty:
        return pd.Series(dtype=float)
    values: list[float] = []
    for _, group in valid.groupby("trade_date"):
        if len(group) < 3:
            continue
        value = _spearman(group["factor"], group["future_return"])
        if value is not None:
            values.append(value)
    return pd.Series(values, dtype=float)


def _t_stat(values: pd.Series) -> float | None:
    if len(values) < 2:
        return None
    std = values.std(ddof=1)
    if pd.isna(std) or std == 0:
        return None
    return float(values.mean() / (std / np.sqrt(len(values))))


def _ensure_unique_trade_keys(df: pd.DataFrame, dataset_name: str) -> None:
    """確認日頻監控資料不含同股同交易日多筆資料。"""
    required = {"trade_date", "stock_id"}
    if df.empty or not required.issubset(df.columns):
        return
    duplicate_mask = df.duplicated(["trade_date", "stock_id"], keep=False)
    if not duplicate_mask.any():
        return
    sample = (
        df.loc[duplicate_mask, ["trade_date", "stock_id"]]
        .drop_duplicates()
        .head(5)
        .assign(trade_date=lambda x: x["trade_date"].dt.strftime("%Y-%m-%d"))
        .to_dict("records")
    )
    raise ValueError(f"{dataset_name} 含同股同交易日多筆資料，請先聚合成日頻資料: {sample}")


def _factor_turnover(valid: pd.DataFrame) -> float | None:
    if valid.empty or valid["trade_date"].nunique() < 2:
        return None
    data = valid.copy()
    unique_values = set(data["factor"].dropna().unique().tolist())
    if unique_values.issubset({0, 1, 0.0, 1.0}):
        changed = data.sort_values(["stock_id", "trade_date"]).groupby("stock_id")["factor"].diff().abs()
        value = changed.dropna().mean()
    else:
        data["rank"] = data.groupby("trade_date")["factor"].rank(pct=True)
        changed = data.sort_values(["stock_id", "trade_date"]).groupby("stock_id")["rank"].diff().abs()
        value = changed.dropna().mean()
    if pd.isna(value):
        return None
    return float(value)
