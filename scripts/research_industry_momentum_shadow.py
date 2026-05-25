"""M13-05：產業動能與 sector rotation shadow research。

只產出研究 artifact，不修改模型、ranking 權重或正式 API 行為。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository
from app.labels import LabelGenerator
from app.monitoring.factor_monitor import _daily_cross_sectional_ic


HORIZON_DAYS = 10
SHADOW_FACTORS = [
    "industry_momentum_20d",
    "industry_relative_strength_20d",
    "industry_breadth_ma20",
    "sector_rotation_score_20d",
]


def main() -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame = _load_shadow_frame()
    report = {
        "status": "OK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": HORIZON_DAYS,
        "summary": _summary(frame),
        "factor_ic": [_factor_metric(frame, factor) for factor in SHADOW_FACTORS],
        "shadow_buckets": [_shadow_bucket(frame, factor) for factor in SHADOW_FACTORS],
        "recommendation": _recommendation(frame),
    }

    json_path = artifacts_dir / "industry_momentum_shadow_research.json"
    md_path = artifacts_dir / "industry_momentum_shadow_research.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(f"INDUSTRY_MOMENTUM_SHADOW_OK json={json_path} md={md_path}")
    return 0


def _load_shadow_frame() -> pd.DataFrame:
    features = pd.read_parquet(PROJECT_ROOT / "data" / "clean" / "features.parquet")
    features["date"] = pd.to_datetime(features["date"]).dt.normalize()
    features["trade_date"] = features["date"]
    features["stock_id"] = features["stock_id"].astype(str).str.strip()
    duplicated = features.duplicated(["trade_date", "stock_id"], keep=False)
    if duplicated.any():
        sample = features.loc[duplicated, ["trade_date", "stock_id"]].head(5).to_dict(orient="records")
        raise ValueError(f"features 含同股同交易日重複資料：{sample}")

    features = features.sort_values(["stock_id", "trade_date"]).copy()
    features["close"] = pd.to_numeric(features["close"], errors="coerce")
    features["ma20"] = pd.to_numeric(features.get("ma20"), errors="coerce")
    features["stock_return_20d"] = features.groupby("stock_id")["close"].pct_change(20)
    features["above_ma20"] = (features["close"] > features["ma20"]).astype("Float64")

    repository = ReferenceRepository(PROJECT_ROOT)
    industries = [repository.stock_industry(stock_id) for stock_id in features["stock_id"]]
    features["industry_name"] = [item.industry_name or "未分類" for item in industries]
    features["sector_name"] = [item.sector_name or "未分類" for item in industries]

    industry_daily = (
        features.groupby(["trade_date", "industry_name"], as_index=False)
        .agg(
            industry_momentum_20d=("stock_return_20d", "mean"),
            industry_breadth_ma20=("above_ma20", "mean"),
            industry_member_count=("stock_id", "nunique"),
        )
    )
    market_daily = (
        features.groupby("trade_date", as_index=False)
        .agg(market_momentum_20d=("stock_return_20d", "mean"))
    )
    industry_daily = industry_daily.merge(market_daily, on="trade_date", how="left")
    industry_daily["industry_relative_strength_20d"] = (
        industry_daily["industry_momentum_20d"] - industry_daily["market_momentum_20d"]
    )
    sector_daily = (
        features.groupby(["trade_date", "sector_name"], as_index=False)
        .agg(sector_rotation_score_20d=("stock_return_20d", "mean"))
    )

    enriched = features.merge(industry_daily, on=["trade_date", "industry_name"], how="left")
    enriched = enriched.merge(sector_daily, on=["trade_date", "sector_name"], how="left")
    enriched = LabelGenerator(horizon=HORIZON_DAYS).generate_labels(enriched)
    return enriched.dropna(subset=["future_return"]).copy()


def _summary(frame: pd.DataFrame) -> dict[str, Any]:
    latest = frame["trade_date"].max()
    latest_frame = frame[frame["trade_date"] == latest]
    return {
        "rows": int(len(frame)),
        "stocks": int(frame["stock_id"].nunique()),
        "trade_days": int(frame["trade_date"].nunique()),
        "latest_trade_date": str(latest.date()),
        "industry_count": int(frame["industry_name"].nunique()),
        "sector_count": int(frame["sector_name"].nunique()),
        "latest_industry_count": int(latest_frame["industry_name"].nunique()),
        "latest_sector_count": int(latest_frame["sector_name"].nunique()),
    }


def _factor_metric(frame: pd.DataFrame, factor: str) -> dict[str, Any]:
    valid = frame[["trade_date", "stock_id", factor, "future_return"]].copy()
    valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
    valid["future_return"] = pd.to_numeric(valid["future_return"], errors="coerce")
    valid = valid.dropna(subset=[factor, "future_return"])
    daily_ic = _daily_cross_sectional_ic(
        valid.rename(columns={factor: "factor"})[["trade_date", "stock_id", "factor", "future_return"]]
    )
    latest_date = frame["trade_date"].max()
    latest_coverage = float(frame.loc[frame["trade_date"] == latest_date, factor].notna().mean())
    coverage = float(frame[factor].notna().mean())
    return {
        "factor": factor,
        "observations": int(len(valid)),
        "coverage": round(coverage, 4),
        "latest_coverage": round(latest_coverage, 4),
        "ic_mean": _round_or_none(daily_ic.mean()),
        "ic_median": _round_or_none(daily_ic.median()),
        "ic_days": int(len(daily_ic)),
    }


def _shadow_bucket(frame: pd.DataFrame, factor: str) -> dict[str, Any]:
    valid = frame[["trade_date", "stock_id", factor, "future_return"]].copy()
    valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
    valid["future_return"] = pd.to_numeric(valid["future_return"], errors="coerce")
    valid = valid.dropna(subset=[factor, "future_return"])
    buckets = []
    for _, group in valid.groupby("trade_date"):
        if len(group) < 20 or group[factor].nunique(dropna=True) < 3:
            continue
        top_cut = group[factor].quantile(0.8)
        bottom_cut = group[factor].quantile(0.2)
        top = group[group[factor] >= top_cut]["future_return"].mean()
        bottom = group[group[factor] <= bottom_cut]["future_return"].mean()
        if pd.notna(top) and pd.notna(bottom):
            buckets.append({"top": float(top), "bottom": float(bottom), "spread": float(top - bottom)})
    bucket_frame = pd.DataFrame(buckets)
    return {
        "factor": factor,
        "days": int(len(bucket_frame)),
        "top_mean_return": _round_or_none(bucket_frame["top"].mean() if not bucket_frame.empty else None),
        "bottom_mean_return": _round_or_none(bucket_frame["bottom"].mean() if not bucket_frame.empty else None),
        "top_bottom_spread": _round_or_none(bucket_frame["spread"].mean() if not bucket_frame.empty else None),
    }


def _recommendation(frame: pd.DataFrame) -> dict[str, str]:
    metrics = [_factor_metric(frame, factor) for factor in SHADOW_FACTORS]
    strong = [
        item
        for item in metrics
        if item["ic_mean"] is not None and abs(float(item["ic_mean"])) >= 0.03 and int(item["ic_days"]) >= 20
    ]
    if strong:
        return {
            "decision": "shadow_candidate",
            "reason": "部分產業/sector 因子有初步 IC 訊號，但仍需 walk-forward shadow ranking 與回測驗證後才能接進 ranking。",
            "next_step": "開 M13-06：產業動能 shadow ranking / walk-forward 評估，不改 production score。",
        }
    return {
        "decision": "monitor_only",
        "reason": "本輪 IC 或樣本天數不足，先保留在風險揭露與監控，不進 ranking。",
        "next_step": "延長樣本或補更長歷史資料後重跑研究。",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M13-05 Industry Momentum Shadow Research",
        "",
        f"- 狀態：`{report['status']}`",
        f"- 產生時間：`{report['generated_at']}`",
        f"- horizon：`{report['horizon_days']}` trading days",
        "",
        "## 結論",
        "",
        f"- 決策：`{report['recommendation']['decision']}`",
        f"- 理由：{report['recommendation']['reason']}",
        f"- 下一步：{report['recommendation']['next_step']}",
        "",
        "## 樣本",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`：{value}")
    lines.extend(["", "## Factor IC", ""])
    for item in report["factor_ic"]:
        lines.append(
            f"- `{item['factor']}` IC={item['ic_mean']} median={item['ic_median']} "
            f"days={item['ic_days']} coverage={item['coverage']}"
        )
    lines.extend(["", "## Shadow Buckets", ""])
    for item in report["shadow_buckets"]:
        lines.append(
            f"- `{item['factor']}` top-bottom spread={item['top_bottom_spread']} "
            f"days={item['days']}"
        )
    lines.extend(
        [
            "",
            "## 邊界",
            "",
            "- 本研究不修改 `risk_adjusted_score`。",
            "- 本研究不修改 LightGBM feature list。",
            "- 若要進 production，需另開 walk-forward shadow ranking / 回測驗證卡。",
            "",
        ]
    )
    return "\n".join(lines)


def _round_or_none(value: Any, digits: int = 4) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


if __name__ == "__main__":
    raise SystemExit(main())
