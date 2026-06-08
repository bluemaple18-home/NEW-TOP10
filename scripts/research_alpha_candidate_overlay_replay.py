#!/usr/bin/env python3
"""產生 alpha overlay shadow replay。

輸出每日 TopN baseline vs overlay 清單與聚合指標；不保存模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research_alpha_candidate_offline_ablation import (  # noqa: E402
    delta,
    fold_windows,
    labeled_frame,
    model_params,
    repo_path,
    resolve_path,
    train_dates_for_fold,
)
from scripts.research_alpha_candidate_overlay import rank_pct_by_date, with_alpha_score  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-overlay-replay.v1"
DECISION_PROMOTE = "PROMOTE_TO_PORTFOLIO_REPLAY_CANDIDATE"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
MIN_TOPN_DELTA = 0.0
MIN_POSITIVE_FOLDS = 2
MIN_AVG_OVERLAP = 0.35


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research alpha candidate overlay shadow replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--alpha-artifact", default=None)
    parser.add_argument("--signal-check", default=None)
    parser.add_argument("--overlay-artifact", default=None)
    parser.add_argument("--variant", default=None)
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-retain-baseline", type=int, default=0)
    parser.add_argument("--candidate-pool-multiplier", type=int, default=3)
    parser.add_argument("--num-boost-round", type=int, default=30)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_overlay_artifact() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_overlay_????-??-??.json"))
    return matches[-1] if matches else None


def selected_variant(args: argparse.Namespace) -> tuple[str, Path | None, dict[str, Any]]:
    overlay_path = resolve_path(args.overlay_artifact) or latest_overlay_artifact()
    payload = load_json(overlay_path)
    variant = args.variant or payload.get("summary", {}).get("best_variant") or "blend_0.30"
    if variant == "baseline" or variant == "alpha_only_diagnostic":
        raise ValueError("variant 必須是預註冊 blend，不可用 baseline 或 alpha_only_diagnostic")
    if not str(variant).startswith("blend_"):
        raise ValueError(f"不支援的 overlay variant：{variant}")
    return str(variant), overlay_path, payload


def score_column_for_variant(variant: str) -> str:
    return f"{variant}_score"


def add_overlay_scores(valid: pd.DataFrame, baseline_features: list[str], alpha_features: list[str], model: Any) -> pd.DataFrame:
    result = with_alpha_score(valid.copy(), alpha_features)
    result["baseline_score"] = model.predict(result[baseline_features])
    result["baseline_rank_score"] = rank_pct_by_date(result, "baseline_score")
    for weight in (0.1, 0.2, 0.3):
        result[f"blend_{weight:.2f}_score"] = (
            (1 - weight) * result["baseline_rank_score"] + weight * result["alpha_rank_score"]
        )
    return result


def top_rows(group: pd.DataFrame, score_col: str, top_n: int) -> pd.DataFrame:
    return group.sort_values(score_col, ascending=False).head(top_n).copy()


def constrained_overlay_rows(
    group: pd.DataFrame,
    variant_score: str,
    top_n: int,
    min_retain_baseline: int,
    candidate_pool_multiplier: int,
) -> pd.DataFrame:
    baseline = top_rows(group, "baseline_score", top_n)
    if min_retain_baseline <= 0:
        return top_rows(group, variant_score, top_n)
    retain_count = min(max(min_retain_baseline, 0), top_n)
    retained = baseline.head(retain_count).copy()
    pool_size = max(top_n, top_n * max(candidate_pool_multiplier, 1))
    pool = top_rows(group, "baseline_score", pool_size)
    retained_ids = set(retained["stock_id"].astype(str))
    fill = pool[~pool["stock_id"].astype(str).isin(retained_ids)].sort_values(variant_score, ascending=False).head(top_n - retain_count)
    return pd.concat([retained, fill], ignore_index=True).head(top_n).copy()


def daily_replay_rows(
    valid: pd.DataFrame,
    variant: str,
    top_n: int,
    min_retain_baseline: int,
    candidate_pool_multiplier: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    variant_score = score_column_for_variant(variant)
    for trade_date, group in valid.groupby("trade_date_text", sort=True):
        baseline = top_rows(group, "baseline_score", top_n)
        overlay = constrained_overlay_rows(
            group,
            variant_score=variant_score,
            top_n=top_n,
            min_retain_baseline=min_retain_baseline,
            candidate_pool_multiplier=candidate_pool_multiplier,
        )
        baseline_ids = set(baseline["stock_id"].astype(str))
        overlay_ids = set(overlay["stock_id"].astype(str))
        overlap = len(baseline_ids & overlay_ids)
        baseline_return = float(pd.to_numeric(baseline["future_return"], errors="coerce").mean())
        overlay_return = float(pd.to_numeric(overlay["future_return"], errors="coerce").mean())
        rows.append(
            {
                "trade_date": str(trade_date),
                "baseline_avg_future_return": round(baseline_return, 6),
                "overlay_avg_future_return": round(overlay_return, 6),
                "return_delta": round(overlay_return - baseline_return, 6),
                "baseline_hit_rate": round(float((pd.to_numeric(baseline["future_return"], errors="coerce") > 0).mean()), 6),
                "overlay_hit_rate": round(float((pd.to_numeric(overlay["future_return"], errors="coerce") > 0).mean()), 6),
                "overlap_count": overlap,
                "overlap_ratio": round(overlap / top_n, 6),
                "baseline_stock_ids": sorted(baseline_ids),
                "overlay_stock_ids": sorted(overlay_ids),
            }
        )
    return rows


def turnover(rows: list[dict[str, Any]], key: str) -> float | None:
    if len(rows) < 2:
        return None
    values: list[float] = []
    previous: set[str] | None = None
    for row in rows:
        current = set(row[key])
        if previous is not None:
            values.append(1 - len(previous & current) / max(len(current), 1))
        previous = current
    return round(float(pd.Series(values).mean()), 6) if values else None


def summarize_daily(rows: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"date_count": 0}
    return {
        "date_count": int(len(frame)),
        "baseline_avg_future_return": round(float(frame["baseline_avg_future_return"].mean()), 6),
        "overlay_avg_future_return": round(float(frame["overlay_avg_future_return"].mean()), 6),
        "return_delta": round(float(frame["return_delta"].mean()), 6),
        "positive_day_count": int((frame["return_delta"] > 0).sum()),
        "negative_day_count": int((frame["return_delta"] <= 0).sum()),
        "baseline_hit_rate": round(float(frame["baseline_hit_rate"].mean()), 6),
        "overlay_hit_rate": round(float(frame["overlay_hit_rate"].mean()), 6),
        "avg_overlap_ratio": round(float(frame["overlap_ratio"].mean()), 6),
        "baseline_turnover": turnover(rows, "baseline_stock_ids"),
        "overlay_turnover": turnover(rows, "overlay_stock_ids"),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    variant, overlay_path, overlay_payload = selected_variant(args)
    frame, baseline_features, alpha_features, alpha_path, signal_path = labeled_frame(args)
    windows = fold_windows(frame["trade_date"].drop_duplicates().tolist(), folds=args.folds)
    all_dates = sorted(frame["trade_date"].drop_duplicates().tolist())
    folds: list[dict[str, Any]] = []
    all_daily: list[dict[str, Any]] = []
    for window in windows:
        validation_dates = window["validation_dates"]
        train_dates = train_dates_for_fold(all_dates, validation_dates, embargo=args.embargo_trade_days)
        train = frame[frame["trade_date"].isin(train_dates)].copy()
        valid = frame[frame["trade_date"].isin(validation_dates)].copy()
        if train.empty or valid.empty or train["target"].nunique() < 2 or valid["target"].nunique() < 2:
            folds.append({"fold": window["fold"], "status": "SKIPPED", "reason": "insufficient classes or rows"})
            continue
        model = lgb.train(
            model_params(),
            lgb.Dataset(train[baseline_features], label=train["target"], feature_name=baseline_features),
            num_boost_round=args.num_boost_round,
        )
        scored = add_overlay_scores(valid, baseline_features, alpha_features, model)
        daily = daily_replay_rows(
            scored,
            variant=variant,
            top_n=args.top_n,
            min_retain_baseline=args.min_retain_baseline,
            candidate_pool_multiplier=args.candidate_pool_multiplier,
        )
        fold_summary = summarize_daily(daily)
        folds.append(
            {
                "fold": window["fold"],
                "status": "OK",
                "train_start": str(pd.to_datetime(min(train_dates)).date()),
                "train_end": str(pd.to_datetime(max(train_dates)).date()),
                "validation_start": str(pd.to_datetime(min(validation_dates)).date()),
                "validation_end": str(pd.to_datetime(max(validation_dates)).date()),
                "summary": fold_summary,
            }
        )
        for row in daily:
            row["fold"] = window["fold"]
        all_daily.extend(daily)
    summary = summarize_daily(all_daily)
    positive_folds = sum(
        1
        for row in folds
        if row.get("status") == "OK" and float((row.get("summary") or {}).get("return_delta") or 0) > MIN_TOPN_DELTA
    )
    failed = []
    if float(summary.get("return_delta") or 0) <= MIN_TOPN_DELTA:
        failed.append("return_delta<=0")
    if positive_folds < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")
    if float(summary.get("avg_overlap_ratio") or 0) < MIN_AVG_OVERLAP:
        failed.append(f"avg_overlap<{MIN_AVG_OVERLAP}")
    decision = DECISION_REJECTED if failed else DECISION_PROMOTE
    rationale = (
        "overlay replay 通過 TopN delta、fold 一致性與 overlap gate；可進 portfolio replay candidate。"
        if not failed
        else "overlay replay 未通過：" + ", ".join(failed)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": "alpha overlay 每日 TopN rerank 是否穩定優於 baseline？",
        "layer": "ranking",
        "pre_registered": True,
        "decision": decision,
        "decision_rationale": rationale,
        "decision_policy": {
            "min_return_delta": MIN_TOPN_DELTA,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "min_avg_overlap": MIN_AVG_OVERLAP,
            "production_promotion_allowed": False,
        },
        "decision_diagnostics": {
            "positive_fold_count": positive_folds,
            "failed": failed,
        },
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "post_model_overlay_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_write_production_features": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "split_policy": "chronological validation tail with embargo",
            "no_hindsight_policy": {
                "validation_windows_are_chronological": True,
                "train_dates_end_before_validation_start": True,
                "embargo_trade_days": args.embargo_trade_days,
                "promotion_gate_variant": variant,
                "new_filters_require_next_walkforward_run": True,
            },
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "alpha_artifact": repo_path(alpha_path),
            "signal_check": repo_path(signal_path),
            "overlay_artifact": repo_path(overlay_path),
            "overlay_artifact_decision": overlay_payload.get("decision"),
            "variant": variant,
            "horizon": args.horizon,
            "threshold": args.threshold,
            "folds": args.folds,
            "embargo_trade_days": args.embargo_trade_days,
            "top_n": args.top_n,
            "min_retain_baseline": args.min_retain_baseline,
            "candidate_pool_multiplier": args.candidate_pool_multiplier,
            "num_boost_round": args.num_boost_round,
        },
        "summary": {
            **summary,
            "positive_fold_count": positive_folds,
            "alpha_features": alpha_features,
            "alpha_feature_count": len(alpha_features),
            "baseline_feature_count": len(baseline_features),
            "variant": variant,
            "min_retain_baseline": args.min_retain_baseline,
            "candidate_pool_multiplier": args.candidate_pool_multiplier,
        },
        "folds": folds,
        "daily": all_daily,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Alpha Candidate Overlay Replay",
        "",
        f"- decision：`{payload['decision']}`",
        f"- decision_rationale：{payload['decision_rationale']}",
        f"- variant：`{summary['variant']}`",
        f"- min_retain_baseline：`{summary['min_retain_baseline']}`",
        f"- candidate_pool_multiplier：`{summary['candidate_pool_multiplier']}`",
        f"- return_delta：`{summary['return_delta']}`",
        f"- positive_fold_count：`{summary['positive_fold_count']}`",
        f"- avg_overlap_ratio：`{summary['avg_overlap_ratio']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Fold | Window | Return Delta | Overlay Return | Baseline Return | Overlap | Overlay Turnover |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["folds"]:
        summary_row = row.get("summary") or {}
        lines.append(
            f"| {row.get('fold')} | {row.get('validation_start')} ~ {row.get('validation_end')} | "
            f"{summary_row.get('return_delta')} | {summary_row.get('overlay_avg_future_return')} | "
            f"{summary_row.get('baseline_avg_future_return')} | {summary_row.get('avg_overlap_ratio')} | "
            f"{summary_row.get('overlay_turnover')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"alpha_candidate_overlay_replay_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
