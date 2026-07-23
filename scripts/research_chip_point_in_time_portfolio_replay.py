#!/usr/bin/env python3
"""籌碼 point-in-time candidate 的成本化 Top10 cohort replay。

本腳本重建 walk-forward artifact 的 train-only feature selection，僅比較
liquidity baseline 與固定 chip rank overlay。輸出只供研究，不修改正式排名。
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402
from scripts.research_alpha_candidate_overlay_portfolio_replay import (  # noqa: E402
    load_group_map,
    simulate_bucket,
    turnover,
)
from scripts.research_feature_group_regime_walkforward import (  # noqa: E402
    apply_research_universe,
    build_group_score,
    clean_feature_groups,
    mask_unavailable_source_features,
)
from scripts.research_feature_group_ablation_by_regime import load_frame  # noqa: E402


SCHEMA_VERSION = "chip-point-in-time-portfolio-replay.v1"
GENERIC_SCHEMA_VERSION = "feature-group-point-in-time-portfolio-replay.v1"
OVERLAY_WEIGHTS = (0.10, 0.20)
MIN_POSITIVE_FOLDS = 3
MAX_TURNOVER_DELTA = 0.10
MIN_BUCKET_TRADES = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="chip point-in-time portfolio replay")
    parser.add_argument(
        "--walkforward",
        default="artifacts/model_experiments/chip_point_in_time_walkforward_2026-07-23.json",
    )
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument(
        "--market-regime-history",
        default="artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json",
    )
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--primary-group", default="chip_flow")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument(
        "--known-market-gap",
        action="append",
        default=["2026-04-13:TPEX"],
        help="允許成對排除的已驗證市場級缺口，格式 YYYY-MM-DD:MARKET",
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--output",
        default="artifacts/model_experiments/chip_point_in_time_portfolio_replay_2026-07-23.json",
    )
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_known_market_gaps(values: list[str]) -> list[dict[str, str]]:
    gaps = []
    for value in values:
        date_text, separator, market = value.partition(":")
        if not separator or not date_text or not market:
            raise ValueError(f"known market gap 格式錯誤：{value}")
        gaps.append({"date": date_text, "market": market.upper()})
    return gaps


def top_ids(frame: pd.DataFrame, score: str, top_n: int) -> list[str]:
    ranked = frame.sort_values([score, "stock_id"], ascending=[False, True]).head(top_n)
    return ranked["stock_id"].astype(str).str.zfill(4).tolist()


def variant_prefix(primary_group: str) -> str:
    """保留既有 chip artifact key，其餘 group 使用原名。"""
    return "chip" if primary_group == "chip_flow" else primary_group


def score_daily(
    daily: pd.DataFrame,
    selected: dict[str, dict[str, list[dict[str, Any]]]],
    top_n: int,
    primary_group: str = "chip_flow",
) -> dict[str, list[str]] | None:
    regime = str(daily["regime_label"].iloc[0])
    liquidity = build_group_score(daily, selected.get(regime, {}).get("liquidity_activity", []))
    primary = build_group_score(daily, selected.get(regime, {}).get(primary_group, []))
    scored = pd.DataFrame(
        {
            "stock_id": daily["stock_id"].astype(str).str.zfill(4),
            "liquidity": liquidity,
            "primary": primary,
        }
    ).dropna()
    required = max(top_n, int(len(daily) * 0.70 + 0.999999))
    if len(scored) < required or scored["liquidity"].nunique() < 3 or scored["primary"].nunique() < 3:
        return None
    scored["liquidity_rank"] = scored["liquidity"].rank(pct=True)
    scored["primary_rank"] = scored["primary"].rank(pct=True)
    result = {"baseline": top_ids(scored, "liquidity_rank", top_n)}
    prefix = variant_prefix(primary_group)
    for weight in OVERLAY_WEIGHTS:
        key = f"{prefix}_{weight:.2f}"
        scored[key] = (1 - weight) * scored["liquidity_rank"] + weight * scored["primary_rank"]
        result[key] = top_ids(scored, key, top_n)
    return result


def variant_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    valid_rows = [row for row in rows if row[key]["avg_net_return"] is not None]
    returns = [float(row[key]["avg_net_return"]) for row in valid_rows]
    exposures = [
        float(row[key]["max_group_exposure"])
        for row in valid_rows
        if row[key].get("max_group_exposure") is not None
    ]
    trade_counts = [int(row[key]["valid_trade_count"]) for row in rows]
    return {
        "date_count": len(valid_rows),
        "avg_net_return": round(float(pd.Series(returns).mean()), 6) if returns else None,
        "hit_rate": round(float(pd.Series([row[key]["hit_rate"] for row in valid_rows]).mean()), 6)
        if valid_rows
        else None,
        "turnover": turnover(
            [{f"{key}_stock_ids": row[key]["stock_ids"]} for row in rows],
            f"{key}_stock_ids",
        ),
        "avg_max_group_exposure": round(float(pd.Series(exposures).mean()), 6) if exposures else None,
        "min_valid_trade_count": min(trade_counts) if trade_counts else 0,
        "incomplete_bucket_count": sum(count < MIN_BUCKET_TRADES for count in trade_counts),
    }


def compare_variant(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    baseline = variant_summary(rows, "baseline")
    overlay = variant_summary(rows, key)
    fold_deltas = []
    for fold in sorted({int(row["fold"]) for row in rows}):
        subset = [row for row in rows if int(row["fold"]) == fold]
        base_fold = variant_summary(subset, "baseline")
        overlay_fold = variant_summary(subset, key)
        delta = (
            float(overlay_fold["avg_net_return"]) - float(base_fold["avg_net_return"])
            if overlay_fold["avg_net_return"] is not None and base_fold["avg_net_return"] is not None
            else None
        )
        fold_deltas.append({"fold": fold, "date_count": len(subset), "return_delta": round(delta, 6) if delta is not None else None})
    return_delta = (
        float(overlay["avg_net_return"]) - float(baseline["avg_net_return"])
        if overlay["avg_net_return"] is not None and baseline["avg_net_return"] is not None
        else None
    )
    turnover_delta = (
        float(overlay["turnover"]) - float(baseline["turnover"])
        if overlay["turnover"] is not None and baseline["turnover"] is not None
        else None
    )
    exposure_delta = (
        float(overlay["avg_max_group_exposure"]) - float(baseline["avg_max_group_exposure"])
        if overlay["avg_max_group_exposure"] is not None and baseline["avg_max_group_exposure"] is not None
        else None
    )
    positive_folds = sum((row["return_delta"] or 0) > 0 for row in fold_deltas)
    failed = []
    if return_delta is None or return_delta <= 0:
        failed.append("return_delta<=0")
    if positive_folds < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")
    if turnover_delta is None or turnover_delta > MAX_TURNOVER_DELTA:
        failed.append(f"turnover_delta>{MAX_TURNOVER_DELTA}")
    if exposure_delta is None or exposure_delta > 0:
        failed.append("group_exposure_worse_or_missing")
    if overlay["incomplete_bucket_count"] > 0:
        failed.append("incomplete_bucket_count>0")
    return {
        "variant": key,
        "decision": "SHADOW_CANDIDATE" if not failed else "REJECTED",
        "failed": failed,
        "baseline": baseline,
        "overlay": overlay,
        "return_delta": round(return_delta, 6) if return_delta is not None else None,
        "positive_fold_count": positive_folds,
        "turnover_delta": round(turnover_delta, 6) if turnover_delta is not None else None,
        "avg_max_group_exposure_delta": round(exposure_delta, 6) if exposure_delta is not None else None,
        "folds": fold_deltas,
    }


def pairwise_gap_receipt(
    row: dict[str, Any],
    *,
    variant_keys: list[str],
    trade_dates: list[Any],
    stock_market: dict[str, str],
    known_gaps: list[dict[str, str]],
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    """只有缺失股票都能對上同一持有窗內的已知市場缺口才允許排除。"""
    entry_date = run_backtest_replay.next_market_trade_date(
        trade_dates,
        row["ranking_date"],
        args.entry_delay_trade_days,
    )
    holding_dates = (
        run_backtest_replay.market_holding_dates(trade_dates, entry_date, args.horizon)
        if entry_date is not None
        else None
    )
    if not holding_dates:
        return None
    holding_date_texts = {str(value) for value in holding_dates}
    missing_by_variant: dict[str, list[str]] = {}
    matched_gaps: set[tuple[str, str]] = set()
    for key in variant_keys:
        expected = {str(stock_id).zfill(4) for stock_id in row[key]["stock_ids"]}
        actual = {str(trade["stock_id"]).zfill(4) for trade in row[key]["trades"]}
        missing = sorted(expected - actual)
        if not missing:
            continue
        missing_by_variant[key] = missing
        for stock_id in missing:
            market = stock_market.get(stock_id, "").upper()
            matches = [
                gap
                for gap in known_gaps
                if gap["date"] in holding_date_texts and gap["market"] == market
            ]
            if not matches:
                return None
            matched_gaps.update((gap["date"], gap["market"]) for gap in matches)
    if not missing_by_variant:
        return None
    return {
        "fold": row["fold"],
        "ranking_date": row["ranking_date"],
        "valid_trade_counts": {
            key: int(row[key]["valid_trade_count"])
            for key in variant_keys
        },
        "missing_stock_ids": missing_by_variant,
        "matched_market_gaps": [
            {"date": date_text, "market": market}
            for date_text, market in sorted(matched_gaps)
        ],
        "reason_code": "VERIFIED_MARKET_LEVEL_OHLC_GAP_PAIRWISE_EXCLUSION",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    walkforward_path = resolve_path(args.walkforward)
    walkforward = json.loads(walkforward_path.read_text(encoding="utf-8"))
    incremental_key = f"{args.primary_group}_vs_liquidity_activity"
    incremental_evidence = walkforward.get("incremental_evidence") or {}
    if incremental_key not in incremental_evidence:
        raise RuntimeError(f"walkforward 缺少 incremental evidence：{incremental_key}")
    incremental = incremental_evidence[incremental_key]["summary"]
    if incremental["decision"] != "INCREMENTAL_WALKFORWARD_CANDIDATE":
        raise RuntimeError(f"{args.primary_group} 未通過 incremental gate，不應執行 portfolio replay")

    frame, source_groups, _ = load_frame(
        resolve_path(args.data_dir),
        resolve_path(args.market_regime_history),
        resolve_path(args.industry_map),
    )
    groups, _ = clean_feature_groups(source_groups)
    frame, _ = mask_unavailable_source_features(frame, groups)
    frame = frame[frame["regime_label"].ne("UNKNOWN")].copy()
    frame, universe = apply_research_universe(
        frame,
        mode="point-in-time-liquidity",
        liquidity_top_n=int(walkforward["inputs"]["liquidity_top_n"]),
    )
    price_frame = run_backtest_replay.load_price_frame(resolve_path("data/clean/features.parquet"))
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    group_map = load_group_map(resolve_path(args.industry_map))
    stock_market = {
        str(stock_id).zfill(4): str(market).upper()
        for stock_id, market in frame[["stock_id", "market"]].dropna().drop_duplicates("stock_id").itertuples(index=False, name=None)
    }
    known_gaps = parse_known_market_gaps(args.known_market_gap)
    selections = {int(row["fold_id"]): row["selected"] for row in walkforward["selections"]}

    attempted_rows: list[dict[str, Any]] = []
    unavailable_days = 0
    for fold in walkforward["folds"]:
        fold_id = int(fold["fold_id"])
        test = frame[frame["trade_date"].between(fold["test_start"], fold["test_end"])]
        for trade_date, daily in test.groupby("trade_date", sort=True):
            ids = score_daily(
                daily,
                selections[fold_id],
                args.top_n,
                primary_group=args.primary_group,
            )
            if ids is None:
                unavailable_days += 1
                continue
            row: dict[str, Any] = {"fold": fold_id, "ranking_date": str(trade_date.date())}
            for key, stock_ids in ids.items():
                row[key] = simulate_bucket(price_index, trade_dates, row["ranking_date"], stock_ids, group_map, args)
            attempted_rows.append(row)

    prefix = variant_prefix(args.primary_group)
    variant_keys = ["baseline", *[f"{prefix}_{weight:.2f}" for weight in OVERLAY_WEIGHTS]]
    excluded_incomplete = []
    rows = []
    for row in attempted_rows:
        if all(int(row[key]["valid_trade_count"]) >= MIN_BUCKET_TRADES for key in variant_keys):
            rows.append(row)
            continue
        receipt = pairwise_gap_receipt(
            row,
            variant_keys=variant_keys,
            trade_dates=trade_dates,
            stock_market=stock_market,
            known_gaps=known_gaps,
            args=args,
        )
        if receipt is None:
            rows.append(row)
        else:
            excluded_incomplete.append(receipt)
    comparisons = [compare_variant(rows, f"{prefix}_{weight:.2f}") for weight in OVERLAY_WEIGHTS]
    candidates = [row["variant"] for row in comparisons if row["decision"] == "SHADOW_CANDIDATE"]
    return {
        "schema_version": SCHEMA_VERSION if args.primary_group == "chip_flow" else GENERIC_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "decision": "SHADOW_CANDIDATE" if candidates else "NO_GO",
        "contract": {
            "research_only": True,
            "point_in_time_universe": True,
            "paired_chip_available_universe": args.primary_group == "chip_flow",
            "paired_primary_available_universe": True,
            "train_only_feature_selection": True,
            "shared_oos_with_incremental_gate": True,
            "independent_validation": False,
            "changes_production_ranking": False,
            "promotion_ready": False,
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "exit_timing": f"D+{args.horizon} close",
        },
        "decision_policy": {
            "overlay_weights_pre_registered": list(OVERLAY_WEIGHTS),
            "min_return_delta": 0,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "max_turnover_delta": MAX_TURNOVER_DELTA,
            "max_group_exposure_delta": 0,
            "min_bucket_trades": MIN_BUCKET_TRADES,
        },
        "inputs": {
            "walkforward": repo_path(walkforward_path),
            "primary_group": args.primary_group,
            "top_n": args.top_n,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
            "known_market_gaps": known_gaps,
        },
        "universe": universe,
        "attempted_days": len(attempted_rows),
        "replay_days": len(rows),
        "unavailable_days": unavailable_days,
        "excluded_incomplete_days": excluded_incomplete,
        "shadow_candidates": candidates,
        "comparisons": comparisons,
        "daily": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['inputs']['primary_group']} Point-in-time Portfolio Replay",
        "",
        f"- decision：`{payload['decision']}`",
        f"- replay_days：`{payload['replay_days']}`",
        f"- unavailable_days：`{payload['unavailable_days']}`",
        f"- independent_validation：`{payload['contract']['independent_validation']}`",
        f"- promotion_ready：`{payload['contract']['promotion_ready']}`",
        "",
        "| Variant | Decision | Return Delta | Positive Folds | Turnover Δ | Industry Exposure Δ |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["comparisons"]:
        lines.append(
            f"| {row['variant']} | {row['decision']} | {row['return_delta']} | "
            f"{row['positive_fold_count']} | {row['turnover_delta']} | "
            f"{row['avg_max_group_exposure_delta']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"],
                "output": repo_path(output),
                "shadow_candidates": payload["shadow_candidates"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
