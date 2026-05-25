"""產業中性化與 ETF 風險研究。

這支腳本只產生研究證據，不修改模型、ranking 權重或正式資料。
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

from app.api.main import market_service
from app.data.reference_repository import ReferenceRepository
from app.labels import LabelGenerator
from app.monitoring.factor_monitor import _daily_cross_sectional_ic


HORIZON_DAYS = 10
FACTORS = [
    "relative_position_60d",
    "relative_position_250d",
    "volume_ratio_20d",
    "macd",
    "macd_hist",
    "rsi",
    "break_20d_high",
    "close_above_bb_mid",
]


def main() -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    reference_repository = ReferenceRepository(PROJECT_ROOT)
    labeled = _load_labeled_features(reference_repository)
    latest_ranking = market_service.latest_ranking(limit=10)

    report = {
        "status": "OK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": HORIZON_DAYS,
        "summary": _summary(latest_ranking.model_dump(), labeled),
        "factor_ic": _factor_ic_report(labeled),
        "recommendation": _recommendation(labeled),
    }

    json_path = artifacts_dir / "industry_etf_risk_research.json"
    md_path = artifacts_dir / "industry_etf_risk_research.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(f"INDUSTRY_ETF_RISK_RESEARCH_OK json={json_path} md={md_path}")
    return 0


def _load_labeled_features(reference_repository: ReferenceRepository) -> pd.DataFrame:
    features_path = PROJECT_ROOT / "data" / "clean" / "features.parquet"
    features = pd.read_parquet(features_path)
    features["date"] = pd.to_datetime(features["date"]).dt.normalize()
    features["trade_date"] = features["date"]
    features["stock_id"] = features["stock_id"].astype(str).str.strip()
    duplicated = features.duplicated(["trade_date", "stock_id"], keep=False)
    if duplicated.any():
        sample = features.loc[duplicated, ["trade_date", "stock_id"]].head(5).to_dict(orient="records")
        raise ValueError(f"features 含同股同交易日重複資料：{sample}")

    labeled = LabelGenerator(horizon=HORIZON_DAYS).generate_labels(features)
    labeled = labeled.dropna(subset=["future_return"]).copy()
    industries = [reference_repository.stock_industry(stock_id) for stock_id in labeled["stock_id"]]
    labeled["industry_name"] = [item.industry_name or "未分類" for item in industries]
    labeled["sector_name"] = [item.sector_name or "未分類" for item in industries]
    labeled["industry_source"] = [item.source or "unavailable" for item in industries]
    return labeled


def _summary(ranking_payload: dict[str, Any], labeled: pd.DataFrame) -> dict[str, Any]:
    items = ranking_payload.get("items") or []
    reference_summary = ranking_payload.get("reference_summary") or {}
    source_mix = labeled["industry_source"].value_counts(normalize=True).round(4).to_dict()
    industry_counts = labeled.groupby("industry_name")["stock_id"].nunique().sort_values(ascending=False).head(10)
    return {
        "latest_ranking_date": ranking_payload.get("date"),
        "top10_count": len(items),
        "top_industry_concentration": reference_summary.get("top_industry_concentration"),
        "industry_exposure": reference_summary.get("industry_exposure", []),
        "sector_exposure": reference_summary.get("sector_exposure", []),
        "etf_overlap_count": reference_summary.get("etf_overlap_count"),
        "reference_notes": reference_summary.get("notes"),
        "labeled_rows": int(len(labeled)),
        "labeled_stocks": int(labeled["stock_id"].nunique()),
        "industry_source_mix": source_mix,
        "largest_industry_sample": industry_counts.to_dict(),
    }


def _factor_ic_report(labeled: pd.DataFrame) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for factor in FACTORS:
        if factor not in labeled.columns:
            continue
        valid = labeled[["trade_date", "stock_id", "industry_name", factor, "future_return"]].copy()
        valid[factor] = pd.to_numeric(valid[factor], errors="coerce")
        valid["future_return"] = pd.to_numeric(valid["future_return"], errors="coerce")
        valid = valid.dropna(subset=[factor, "future_return"])
        if valid.empty:
            continue

        overall_ic = _daily_cross_sectional_ic(
            valid.rename(columns={factor: "factor"})[["trade_date", "stock_id", "factor", "future_return"]]
        )
        neutral = valid.copy()
        neutral["factor"] = neutral[factor] - neutral.groupby(["trade_date", "industry_name"])[factor].transform("mean")
        neutral_ic = _daily_cross_sectional_ic(neutral[["trade_date", "stock_id", "factor", "future_return"]])
        by_industry = _by_industry_ic(valid, factor)
        report.append(
            {
                "factor": factor,
                "observations": int(len(valid)),
                "overall_ic_mean": _round_or_none(overall_ic.mean()),
                "overall_ic_days": int(len(overall_ic)),
                "industry_neutral_ic_mean": _round_or_none(neutral_ic.mean()),
                "industry_neutral_ic_days": int(len(neutral_ic)),
                "by_industry": by_industry,
            }
        )
    return report


def _by_industry_ic(valid: pd.DataFrame, factor: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for industry_name, group in valid.groupby("industry_name"):
        if group["stock_id"].nunique() < 3 or len(group) < 100:
            continue
        ic = _daily_cross_sectional_ic(
            group.rename(columns={factor: "factor"})[["trade_date", "stock_id", "factor", "future_return"]]
        )
        if ic.empty:
            continue
        rows.append(
            {
                "industry_name": str(industry_name),
                "stocks": int(group["stock_id"].nunique()),
                "observations": int(len(group)),
                "ic_mean": _round_or_none(ic.mean()),
                "ic_days": int(len(ic)),
            }
        )
    return sorted(rows, key=lambda item: abs(item["ic_mean"] or 0), reverse=True)[:8]


def _recommendation(labeled: pd.DataFrame) -> dict[str, Any]:
    formal_sources = ~labeled["industry_source"].isin({"code_prefix_fallback", "unavailable"})
    full_mapping_ratio = float(formal_sources.mean())
    fallback_or_missing_ratio = float((~formal_sources).mean())
    if full_mapping_ratio >= 0.95:
        reason = (
            "本地產業 reference mapping 覆蓋率已足以支撐風險揭露與分群研究；"
            "但目前 IC 結果仍是研究證據，不足以直接改模型或 ranking 權重。"
        )
        next_card = "另開卡評估 industry_momentum / sector_rotation，並用 walk-forward 或 shadow ranking 驗證。"
    else:
        reason = (
            "目前可用於 Top10 產業集中與 ETF overlap 風險揭露；"
            "但本地產業 reference mapping 覆蓋率仍過低，多數樣本缺 mapping 或依賴代號前綴 fallback，"
            "尚不足以直接把產業特徵加進模型或 ranking 權重。"
        )
        next_card = "擴充本地 industry reference mapping 後，再開卡評估 industry_momentum / sector_rotation 是否進模型。"
    return {
        "decision": "risk_disclosure_only",
        "reason": reason,
        "formal_mapping_ratio": round(full_mapping_ratio, 4),
        "fallback_or_missing_ratio": round(fallback_or_missing_ratio, 4),
        "next_card": next_card,
    }


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# M13-03 產業中性化與 ETF 風險研究",
        "",
        f"- 狀態：`{report['status']}`",
        f"- 產生時間：`{report['generated_at']}`",
        f"- 預測 horizon：`{report['horizon_days']}` trading days",
        "",
        "## 結論",
        "",
        f"- 決策：`{report['recommendation']['decision']}`",
        f"- 理由：{report['recommendation']['reason']}",
        f"- 本地 reference mapping 覆蓋率（不含 missing / prefix fallback）：{report['recommendation']['formal_mapping_ratio']:.2%}",
        f"- 缺 mapping 或 prefix fallback 比例：{report['recommendation']['fallback_or_missing_ratio']:.2%}",
        "",
        "## Top10 風險揭露",
        "",
        f"- latest ranking date：`{summary['latest_ranking_date']}`",
        f"- top industry concentration：`{summary['top_industry_concentration']}`",
        f"- ETF overlap count：`{summary['etf_overlap_count']}`",
        f"- notes：{summary['reference_notes']}",
        "",
        "## Factor IC 摘要",
        "",
    ]
    for item in report["factor_ic"]:
        lines.append(
            "- "
            f"`{item['factor']}` overall IC={item['overall_ic_mean']} "
            f"({item['overall_ic_days']} days), "
            f"industry-neutral IC={item['industry_neutral_ic_mean']} "
            f"({item['industry_neutral_ic_days']} days)"
        )
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            f"- {report['recommendation']['next_card']}",
            "- 研究結果不得直接改 `risk_adjusted_score`；若要進 ranking，需另開權重與回測驗證卡。",
            "",
        ]
    )
    return "\n".join(lines)


def _round_or_none(value: Any, digits: int = 4) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), digits)


if __name__ == "__main__":
    raise SystemExit(main())
