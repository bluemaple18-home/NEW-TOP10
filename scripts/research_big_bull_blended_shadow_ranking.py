#!/usr/bin/env python3
"""產生 BIG_BULL/global blended shadow ranking。

這支腳本只輸出研究用 ranking artifacts，不修改 production ranking、
不寫入正式模型，也不覆蓋 `models/latest_lgbm.pkl`。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_big_bull_shadow_ranking as big_bull_ranking  # noqa: E402
from scripts import research_regime_family_training_candidates as candidates  # noqa: E402


SCHEMA_VERSION = "big-bull-blended-shadow-ranking.v1"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "backtest"
SUMMARY_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build BIG_BULL/global blended shadow rankings")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--dates-from-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT.relative_to(PROJECT_ROOT)))
    parser.add_argument("--family", default="BIG_BULL")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--min-train-family-dates", type=int, default=18)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--rerank-pool-multiplier", type=int, default=3)
    parser.add_argument("--blend-family-weight", type=float, default=0.5)
    parser.add_argument("--num-boost-round", type=int, default=120)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    return big_bull_ranking.resolve_path(value)


def score_frame(day: pd.DataFrame, features: list[str], global_model: Any, family_model: Any) -> pd.DataFrame:
    scored = day.copy()
    scored["global_model_prob"] = global_model.predict(scored[features])
    scored["family_model_prob"] = family_model.predict(scored[features])
    return scored


def apply_ranking_columns(scored: pd.DataFrame, score_col: str, family: str, note: str, top_n: int) -> pd.DataFrame:
    ranked = scored.sort_values(score_col, ascending=False).head(top_n).copy()
    gross_exposure = 0.65
    max_position_weight = 0.2
    target_weight = round(min(max_position_weight, gross_exposure / max(len(ranked), 1)), 6)
    allocated = round(target_weight * len(ranked), 6)
    ranked["stock_id"] = ranked["stock_id"].astype(str).str.zfill(4)
    ranked["stock_name"] = [big_bull_ranking.stock_name(stock_id) for stock_id in ranked["stock_id"]]
    ranked["model_prob"] = ranked[score_col]
    ranked["risk_adjusted_score"] = ranked[score_col]
    ranked["final_score"] = ranked[score_col]
    ranked["prediction_score"] = ranked[score_col]
    ranked["rule_score"] = 0.0
    ranked["setup_score"] = 0.0
    ranked["quality_score"] = 0.0
    ranked["risk_penalty"] = 0.0
    ranked["suggested_weight"] = target_weight
    ranked["max_position_weight"] = max_position_weight
    ranked["gross_exposure"] = gross_exposure
    ranked["allocated_exposure"] = allocated
    ranked["cash_weight"] = round(max(0.0, 1 - allocated), 6)
    ranked["exposure_note"] = note
    ranked["risk_reward"] = None
    ranked["market_regime"] = family
    ranked["reasons"] = f"{note}; research-only, not production evidence"
    return ranked


def build_blended_outputs(scored: pd.DataFrame, args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    family_weight = max(0.0, min(1.0, float(args.blend_family_weight)))
    global_weight = 1.0 - family_weight
    blended = scored.copy()
    blended["blended_score"] = (
        global_weight * blended["global_model_prob"] + family_weight * blended["family_model_prob"]
    )
    pool_size = max(args.top_n, args.top_n * max(1, args.rerank_pool_multiplier))
    rerank_pool = scored.sort_values("global_model_prob", ascending=False).head(pool_size).copy()
    rerank_pool["rerank_score"] = rerank_pool["family_model_prob"]
    return {
        "score_blend": apply_ranking_columns(
            blended,
            "blended_score",
            args.family,
            f"{args.family} research-only global/family score blend",
            args.top_n,
        ),
        "ranking_rerank": apply_ranking_columns(
            rerank_pool,
            "rerank_score",
            args.family,
            f"{args.family} research-only global prefilter then family rerank",
            args.top_n,
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    family = args.family.strip().upper()
    if family != "BIG_BULL":
        raise ValueError("此 blended shadow ranking builder 只允許 BIG_BULL family")
    dates_dir = resolve_path(args.dates_from_dir)
    output_root = resolve_path(args.output_root)
    if dates_dir is None or output_root is None:
        raise RuntimeError("path resolution failed")

    requested_dates = big_bull_ranking.ranking_dates(dates_dir, args.max_ranking_files)
    frame_args = argparse.Namespace(
        data_dir=args.data_dir,
        market_regime_history=args.market_regime_history,
        horizon=args.horizon,
        threshold=args.threshold,
    )
    frame, features, _regimes = candidates.labeled_frame(frame_args, [family])
    frame = frame.sort_values(["trade_date", "stock_id"]).copy()
    all_dates = sorted(pd.to_datetime(frame["trade_date"]).drop_duplicates().tolist())
    outputs = {"score_blend": [], "ranking_rerank": []}
    skipped: list[dict[str, Any]] = []
    output_dirs = {
        "score_blend": output_root / "shadow_rankings_big_bull_blended_score",
        "ranking_rerank": output_root / "shadow_rankings_big_bull_blended_rerank",
    }

    for date_text in requested_dates:
        target = pd.Timestamp(date_text)
        day = frame[(frame["trade_date"] == target) & frame[f"family_{family}"]].copy()
        if day.empty:
            skipped.append({"date": date_text, "reason": "not_big_bull_family_date"})
            continue
        train_dates = big_bull_ranking.training_dates_for_target(all_dates, target, args.embargo_trade_days)
        global_train = frame[frame["trade_date"].isin(train_dates)].copy()
        family_train = global_train[global_train[f"family_{family}"]].copy()
        train_family_dates = int(pd.to_datetime(family_train["trade_date"]).nunique())
        if train_family_dates < args.min_train_family_dates or family_train["target"].nunique() < 2:
            skipped.append(
                {
                    "date": date_text,
                    "reason": "insufficient_family_training_window",
                    "train_family_dates": train_family_dates,
                    "target_classes": int(family_train["target"].nunique()),
                }
            )
            continue
        if global_train["target"].nunique() < 2:
            skipped.append({"date": date_text, "reason": "insufficient_global_training_classes"})
            continue

        global_model = big_bull_ranking.train_model(global_train, features, args.num_boost_round)
        family_model = big_bull_ranking.train_model(family_train, features, args.num_boost_round)
        scored = score_frame(day, features, global_model, family_model)
        ranked_by_mode = build_blended_outputs(scored, args)
        for mode, ranking in ranked_by_mode.items():
            out_path = output_dirs[mode] / f"ranking_{date_text}.csv"
            big_bull_ranking.write_ranking(out_path, ranking)
            outputs[mode].append(
                {
                    "date": date_text,
                    "ranking": big_bull_ranking.repo_path(out_path),
                    "train_start_date": pd.Timestamp(min(train_dates)).date().isoformat() if train_dates else None,
                    "train_end_date": pd.Timestamp(max(train_dates)).date().isoformat() if train_dates else None,
                    "train_family_dates": train_family_dates,
                    "ranked_count": int(len(ranking)),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if any(outputs.values()) else "WARN",
        "family": family,
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "blended_candidates": ["score_blend", "ranking_rerank"],
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "ranking_followup_only": True,
            "no_hindsight_policy": {
                "train_dates_end_before_ranking_date": True,
                "embargo_trade_days": args.embargo_trade_days,
                "family_definitions_pre_registered": True,
            },
        },
        "inputs": {
            "dates_from_dir": big_bull_ranking.repo_path(dates_dir),
            "output_root": big_bull_ranking.repo_path(output_root),
            "data_dir": big_bull_ranking.repo_path(resolve_path(args.data_dir)),
            "market_regime_history": big_bull_ranking.repo_path(resolve_path(args.market_regime_history)),
            "requested_dates": requested_dates,
            "top_n": args.top_n,
            "rerank_pool_multiplier": args.rerank_pool_multiplier,
            "blend_family_weight": args.blend_family_weight,
            "num_boost_round": args.num_boost_round,
            "feature_count": len(features),
        },
        "summary": {
            mode: {
                "ranking_count": len(rows),
                "start_date": rows[0]["date"] if rows else None,
                "end_date": rows[-1]["date"] if rows else None,
                "output_dir": big_bull_ranking.repo_path(output_dirs[mode]),
            }
            for mode, rows in outputs.items()
        }
        | {"skipped_count": len(skipped)},
        "outputs": outputs,
        "skipped": skipped,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# BIG_BULL Blended Shadow Ranking",
        "",
        f"- status: {payload['status']}",
        f"- family: {payload['family']}",
        f"- production_promotion_allowed: {payload['contract']['production_promotion_allowed']}",
        f"- skipped_count: {payload['summary']['skipped_count']}",
        "",
        "## Outputs",
    ]
    for mode in ("score_blend", "ranking_rerank"):
        summary = payload["summary"][mode]
        lines.extend(
            [
                "",
                f"### {mode}",
                f"- ranking_count: {summary['ranking_count']}",
                f"- date_range: {summary['start_date']} ~ {summary['end_date']}",
                f"- output_dir: {summary['output_dir']}",
            ]
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args)
    summary_path = SUMMARY_DIR / f"big_bull_blended_shadow_ranking_{args.date}.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_markdown(payload, summary_path)
    print(json.dumps({"status": payload["status"], "output": big_bull_ranking.repo_path(summary_path), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
