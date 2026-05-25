"""產生基本面 shadow score 與驗證報告。

此腳本只輸出研究 artifact，不改 ranking 檔、不改模型權重。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals import compute_financial_metrics, sanity_check, score_from_feature_row, score_fundamentals
from app.fundamentals.metrics import FinancialYearMetrics
from app.labels import LabelGenerator
from app.modeling.feature_contract import load_m4_feature_frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fundamental shadow score artifacts")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--output-prefix", default="fundamental_shadow")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    data_dir = PROJECT_ROOT / args.data_dir
    scores = _stock_scores(data_dir=data_dir)
    score_frame = pd.DataFrame(scores)
    csv_path = artifacts_dir / f"{args.output_prefix}_scores.csv"
    score_frame.to_csv(csv_path, index=False)

    evaluation = _evaluate_shadow_score(score_frame=score_frame, horizon=args.horizon, data_dir=data_dir)
    json_path = artifacts_dir / f"{args.output_prefix}_report.json"
    report = {
        "score_artifact": str(csv_path),
        "data_dir": str(data_dir),
        "horizon_days": args.horizon,
        "summary": _score_summary(score_frame),
        "evaluation": evaluation,
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "FUNDAMENTAL_SHADOW_SCORE "
        f"stocks={len(score_frame)} coverage={report['summary']['score_coverage']:.4f} "
        f"ic={evaluation.get('ic')} top_bottom_spread={evaluation.get('top_bottom_spread')} "
        f"csv={csv_path} report={json_path}"
    )
    return 0


def _stock_scores(data_dir: Path) -> list[dict[str, Any]]:
    repository = FundamentalRepository(PROJECT_ROOT)
    stock_ids = _stock_universe(data_dir=data_dir)
    rows = []
    for stock_id in stock_ids:
        payload = repository.load_cached(stock_id)
        if payload is None:
            rows.append({"stock_id": stock_id, "available": False})
            continue
        metrics = _metrics_from_payload(payload)
        warnings = sanity_check(metrics)
        warnings.extend(payload.get("warnings", []))
        score = score_fundamentals(stock_id=stock_id, metrics=metrics, warnings=warnings)
        rows.append(
            {
                **score.to_dict(),
                "available": score.fundamental_quality_score is not None,
                "source": payload.get("source"),
                "updated_at": payload.get("updated_at"),
                "years": ",".join(payload.get("years", [])[:5]),
                "warning_count": len(warnings),
            }
        )
    return rows


def _metrics_from_payload(payload: dict[str, Any]) -> list[FinancialYearMetrics]:
    if payload.get("metrics"):
        return [FinancialYearMetrics(**item) for item in payload["metrics"]]
    return compute_financial_metrics(payload.get("financials_by_year") or {})


def _stock_universe(data_dir: Path) -> list[str]:
    features_path = data_dir / "features.parquet"
    features = pd.read_parquet(features_path, columns=["stock_id"])
    return sorted(features["stock_id"].astype(str).str.strip().unique().tolist())


def _evaluate_shadow_score(score_frame: pd.DataFrame, horizon: int, data_dir: Path) -> dict[str, Any]:
    feature_frame, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=PROJECT_ROOT)
    feature_frame = feature_frame.copy()
    feature_frame["fundamental_quality_score"] = feature_frame.apply(score_from_feature_row, axis=1)
    labeled = LabelGenerator(horizon=horizon).generate_labels(feature_frame)
    labeled = labeled.dropna(subset=["future_return"]).copy()
    valid = labeled[["trade_date", "stock_id", "fundamental_quality_score", "future_return"]].dropna().copy()
    daily_ic = _daily_ic(valid)
    quantiles = _quantile_returns(valid)
    ranking_probe = _ranking_probe(score_frame)
    return {
        "feature_rows": int(len(feature_frame)),
        "feature_stocks": int(feature_frame["stock_id"].nunique()),
        "fundamental_cache_coverage": round(float(metadata.fundamental_cache_coverage), 4),
        "score_observations": int(len(valid)),
        "score_coverage": round(float(feature_frame["fundamental_quality_score"].notna().mean()), 4),
        "latest_score_coverage": round(
            float(
                feature_frame.loc[
                    feature_frame["trade_date"] == feature_frame["trade_date"].max(),
                    "fundamental_quality_score",
                ].notna().mean()
            ),
            4,
        ),
        "ic": round(float(daily_ic.mean()), 4) if not daily_ic.empty else None,
        "ic_days": int(len(daily_ic)),
        "ic_median": round(float(daily_ic.median()), 4) if not daily_ic.empty else None,
        "quantile_returns": quantiles,
        "top_bottom_spread": _top_bottom_spread(quantiles),
        "ranking_probe": ranking_probe,
    }


def _daily_ic(valid: pd.DataFrame) -> pd.Series:
    values = []
    for _, group in valid.groupby("trade_date"):
        if len(group) < 3 or group["fundamental_quality_score"].nunique(dropna=True) < 2:
            continue
        value = group["fundamental_quality_score"].corr(group["future_return"], method="spearman")
        if pd.notna(value):
            values.append(float(value))
    return pd.Series(values, dtype=float)


def _quantile_returns(valid: pd.DataFrame) -> dict[str, float]:
    frames = []
    for _, group in valid.groupby("trade_date"):
        if len(group) < 10 or group["fundamental_quality_score"].nunique(dropna=True) < 5:
            continue
        current = group.copy()
        current["quantile"] = pd.qcut(current["fundamental_quality_score"], q=5, labels=False, duplicates="drop")
        frames.append(current)
    if not frames:
        return {}
    combined = pd.concat(frames, ignore_index=True)
    result = combined.groupby("quantile")["future_return"].mean().sort_index()
    return {str(int(index) + 1): round(float(value), 6) for index, value in result.items()}


def _top_bottom_spread(quantiles: dict[str, float]) -> float | None:
    if "1" not in quantiles or "5" not in quantiles:
        return None
    return round(float(quantiles["5"] - quantiles["1"]), 6)


def _ranking_probe(score_frame: pd.DataFrame) -> dict[str, Any]:
    ranking_files = sorted((PROJECT_ROOT / "artifacts").glob("ranking_*.csv"))
    if not ranking_files:
        return {"available": False}
    ranking_path = ranking_files[-1]
    ranking = pd.read_csv(ranking_path, dtype={"stock_id": str})
    ranking["stock_id"] = ranking["stock_id"].astype(str).str.strip()
    merged = ranking.merge(
        score_frame[["stock_id", "fundamental_quality_score"]],
        on="stock_id",
        how="left",
    )
    score_stock_ids = set(score_frame["stock_id"].astype(str).str.strip())
    ranking_stock_ids = set(merged["stock_id"].astype(str).str.strip())
    overlap = sorted(score_stock_ids.intersection(ranking_stock_ids))
    if "risk_adjusted_score" not in merged.columns:
        return {
            "available": False,
            "ranking_path": str(ranking_path),
            "score_ranking_overlap": len(overlap),
            "comparable": False,
        }
    current_top10 = merged.sort_values("risk_adjusted_score", ascending=False)["stock_id"].head(10).tolist()
    merged["shadow_overlay_score"] = pd.to_numeric(merged["risk_adjusted_score"], errors="coerce").fillna(0) + (
        pd.to_numeric(merged["fundamental_quality_score"], errors="coerce").fillna(0.5) - 0.5
    ) * 0.2
    shadow_top10 = merged.sort_values("shadow_overlay_score", ascending=False)["stock_id"].head(10).tolist()
    top10_overlap = len(set(current_top10).intersection(shadow_top10))
    return {
        "available": True,
        "ranking_path": str(ranking_path),
        "score_ranking_overlap": len(overlap),
        "score_stocks": len(score_stock_ids),
        "ranking_stocks": len(ranking_stock_ids),
        "comparable": len(overlap) >= min(10, len(score_stock_ids)),
        "current_top10": current_top10,
        "shadow_overlay_top10": shadow_top10,
        "top10_overlap": top10_overlap,
        "note": "shadow_overlay_score 只作敏感度檢查，不代表建議權重。",
    }


def _score_summary(score_frame: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(score_frame.get("fundamental_quality_score"), errors="coerce")
    return {
        "stocks": int(len(score_frame)),
        "available": int(values.notna().sum()),
        "score_coverage": round(float(values.notna().mean()), 4) if len(score_frame) else 0.0,
        "mean": round(float(values.mean()), 4) if values.notna().any() else None,
        "median": round(float(values.median()), 4) if values.notna().any() else None,
        "min": round(float(values.min()), 4) if values.notna().any() else None,
        "max": round(float(values.max()), 4) if values.notna().any() else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
