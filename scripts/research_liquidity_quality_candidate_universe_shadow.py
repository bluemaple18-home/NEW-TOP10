#!/usr/bin/env python3
"""用完整候選池測流動性品質 shadow ranking。

RANKING-QUALITY-02 只重排既有 ranking artifact 內的候選列；本腳本改用
StockRanker 同模型、同資料重建完整每日候選池，再比較 production /
percentile_gate / log_gate 的 Top10 成員差異。

此腳本只輸出研究 artifact，不覆蓋 artifacts/ranking_*.csv。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker  # noqa: E402


SCHEMA_VERSION = "liquidity-quality-candidate-universe-shadow.v1"
VARIANTS = ["production", "percentile_gate", "log_gate"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research liquidity quality on full candidate universe")
    parser.add_argument("--dates", default="2026-05-26,2026-05-27,2026-05-28,2026-05-29,2026-06-01,2026-06-02")
    parser.add_argument("--start-date", default=None, help="從 features 交易日自動產生區間起日；設定後優先於 --dates")
    parser.add_argument("--end-date", default=None, help="從 features 交易日自動產生區間迄日；設定後優先於 --dates")
    parser.add_argument("--max-dates", type=int, default=None, help="限制處理最近 N 個交易日，用於本機壓力測試")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--tradability-threshold", type=float, default=30_000_000.0)
    parser.add_argument("--log-full-score-value", type=float, default=500_000_000.0)
    parser.add_argument("--output", default="artifacts/liquidity_quality_candidate_universe_shadow_2026-06-03.json")
    parser.add_argument("--shadow-ranking-dir", default="artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_2026-06-03")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(parsed) else parsed


def date_values(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_date_values(args: argparse.Namespace) -> list[str]:
    if not args.start_date and not args.end_date:
        values = date_values(args.dates)
        return values[-args.max_dates :] if args.max_dates else values

    features_path = resolve_path(args.data_dir) / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在，無法自動產生日期區間：{features_path}")
    try:
        frame = pd.read_parquet(features_path, columns=["trade_date"])
        date_column = "trade_date"
    except Exception as exc:
        if "trade_date" not in str(exc):
            raise
        frame = pd.read_parquet(features_path, columns=["date"])
        date_column = "date"

    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna().dt.date
    values = sorted({item.isoformat() for item in dates})
    if args.start_date:
        values = [item for item in values if item >= args.start_date]
    if args.end_date:
        values = [item for item in values if item <= args.end_date]
    if args.max_dates:
        values = values[-args.max_dates :]
    if not values:
        raise ValueError("日期區間沒有任何交易日")
    return values


def read_official_ranking(date_text: str, top_n: int) -> list[str]:
    path = PROJECT_ROOT / "artifacts" / f"ranking_{date_text}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [str(row.get("stock_id", "")).zfill(4) for row in rows[:top_n]]


def percentile_liquidity_score(frame: pd.DataFrame, threshold: float) -> pd.Series:
    values = pd.to_numeric(frame.get("avg_value_20d", 0), errors="coerce").fillna(0.0)
    score = pd.Series(0.0, index=frame.index)
    tradable = values >= threshold
    if tradable.any():
        ranks = values[tradable].rank(method="average", pct=True)
        score.loc[tradable] = 0.5 + 0.5 * ranks
    return score.clip(0, 1)


def log_liquidity_score(frame: pd.DataFrame, threshold: float, full_score_value: float) -> pd.Series:
    values = pd.to_numeric(frame.get("avg_value_20d", 0), errors="coerce").fillna(0.0)
    lower = math.log1p(threshold)
    upper = math.log1p(max(full_score_value, threshold + 1))
    raw = (values.map(math.log1p) - lower) / (upper - lower)
    score = (0.5 + 0.5 * raw).clip(0.5, 1.0)
    return score.where(values >= threshold, 0.0).clip(0, 1)


def apply_shadow_score(df: pd.DataFrame, variant: str, threshold: float, log_full_score_value: float) -> pd.DataFrame:
    result = df.copy()
    if variant == "production":
        result["shadow_quality_score"] = pd.to_numeric(result.get("quality_score", 0.5), errors="coerce").fillna(0.5)
        result["shadow_score"] = pd.to_numeric(result.get("risk_adjusted_score", 0), errors="coerce").fillna(0.0)
    elif variant == "percentile_gate":
        result["shadow_quality_score"] = percentile_liquidity_score(result, threshold)
        result["shadow_score"] = shadow_total_score(result, result["shadow_quality_score"], threshold)
    elif variant == "log_gate":
        result["shadow_quality_score"] = log_liquidity_score(result, threshold, log_full_score_value)
        result["shadow_score"] = shadow_total_score(result, result["shadow_quality_score"], threshold)
    else:
        raise ValueError(f"未知 variant：{variant}")
    result["liquidity_gate_pass"] = pd.to_numeric(result.get("avg_value_20d", 0), errors="coerce").fillna(0.0) >= threshold
    result["risk_adjusted_score"] = result["shadow_score"].clip(lower=0)
    result["quality_score"] = result["shadow_quality_score"].clip(0, 1)
    return result.sort_values("risk_adjusted_score", ascending=False)


def shadow_total_score(df: pd.DataFrame, quality: pd.Series, threshold: float) -> pd.Series:
    avg_value = pd.to_numeric(df.get("avg_value_20d", 0), errors="coerce").fillna(0.0)
    prediction = pd.to_numeric(df.get("prediction_score", df.get("model_prob", 0.5)), errors="coerce").fillna(0.5)
    setup = pd.to_numeric(df.get("setup_score", 0.5), errors="coerce").fillna(0.5)
    risk = pd.to_numeric(df.get("risk_penalty", 0), errors="coerce").fillna(0.0)
    score = (prediction + setup + quality - risk).clip(lower=0)
    return score.where(avg_value >= threshold, -1.0)


def top10_with_portfolio(ranker: StockRanker, df: pd.DataFrame, market_regime: Any, top_n: int) -> pd.DataFrame:
    top = df.head(top_n).copy()
    return ranker.portfolio_policy.apply(top, market_regime)


def compact_items(frame: pd.DataFrame, variant: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(frame.iterrows(), start=1):
        trade_plan = row.get("trade_plan") if isinstance(row.get("trade_plan"), dict) else {}
        entry_zone = {
            "low": trade_plan.get("entry_low"),
            "high": trade_plan.get("entry_high"),
        }
        rows.append(
            {
                "rank": rank,
                "stock_id": str(row.get("stock_id", "")).zfill(4),
                "stock_name": row.get("stock_name"),
                "close": numeric(row.get("close")),
                "risk_adjusted_score": round(numeric(row.get("risk_adjusted_score")), 6),
                "final_score": round(numeric(row.get("final_score")), 6),
                "model_prob": round(numeric(row.get("model_prob")), 6),
                "rule_score": round(numeric(row.get("rule_score")), 6),
                "prediction_score": round(numeric(row.get("prediction_score")), 6),
                "setup_score": round(numeric(row.get("setup_score")), 6),
                "quality_score": round(numeric(row.get("quality_score")), 6),
                "risk_penalty": round(numeric(row.get("risk_penalty")), 6),
                "avg_value_20d": round(numeric(row.get("avg_value_20d")), 2),
                "liquidity_gate_pass": bool(row.get("liquidity_gate_pass", True)),
                "suggested_weight": round(numeric(row.get("suggested_weight")), 6),
                "max_position_weight": round(numeric(row.get("max_position_weight")), 6),
                "gross_exposure": round(numeric(row.get("gross_exposure")), 6),
                "market_regime": row.get("market_regime"),
                "entry_low": round(numeric(entry_zone.get("low")), 2),
                "entry_high": round(numeric(entry_zone.get("high")), 2),
                "stop_loss": round(numeric(trade_plan.get("stop_loss")), 2),
                "target_price": round(numeric(trade_plan.get("target_price")), 2),
                "stop_basis": trade_plan.get("stop_basis"),
                "target_basis": trade_plan.get("target_basis"),
                "risk_reward": round(numeric(row.get("risk_reward")), 6),
                "variant": variant,
            }
        )
    return rows


def write_ranking_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "stock_id",
        "stock_name",
        "close",
        "risk_adjusted_score",
        "final_score",
        "model_prob",
        "rule_score",
        "prediction_score",
        "setup_score",
        "quality_score",
        "risk_penalty",
        "avg_value_20d",
        "liquidity_gate_pass",
        "suggested_weight",
        "max_position_weight",
        "gross_exposure",
        "market_regime",
        "entry_low",
        "entry_high",
        "stop_loss",
        "target_price",
        "stop_basis",
        "target_basis",
        "risk_reward",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            writer.writerow({key: item.get(key) for key in fieldnames})


def stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    values = [numeric(item.get("avg_value_20d")) for item in items]
    return {
        "avg_avg_value_20d": round(sum(values) / len(values), 2) if values else None,
        "min_avg_value_20d": round(min(values), 2) if values else None,
        "gate_fail_count": sum(1 for item in items if not item.get("liquidity_gate_pass")),
    }


def analyze_date(ranker: StockRanker, date_text: str, args: argparse.Namespace, shadow_dir: Path) -> dict[str, Any]:
    daily, history = ranker.load_daily_data(date_text)
    scored = ranker.calculate_scores(daily)
    target = daily["date"].max() if "date" in daily else None
    market_regime = ranker.market_regime_service.evaluate(history, target_date=target)
    production_ranked = ranker.ranking_policy.apply(scored, market_regime)
    official_ids = read_official_ranking(date_text, args.top_n)

    variants: dict[str, Any] = {}
    production_ids: set[str] | None = None
    for variant in VARIANTS:
        shadow_ranked = apply_shadow_score(
            production_ranked,
            variant=variant,
            threshold=args.tradability_threshold,
            log_full_score_value=args.log_full_score_value,
        )
        top = top10_with_portfolio(ranker, shadow_ranked, market_regime, args.top_n)
        items = compact_items(top, variant)
        write_ranking_csv(shadow_dir / variant / f"ranking_{date_text}.csv", items)
        ids = {item["stock_id"] for item in items}
        if variant == "production":
            production_ids = ids
        variants[variant] = {
            "items": items,
            "stats": stats(items),
            "official_overlap_count": len(ids & set(official_ids)) if official_ids else None,
            "official_overlap_rate": round(len(ids & set(official_ids)) / args.top_n, 6) if official_ids else None,
        }
    production_ids = production_ids or set()
    production_top1 = variants["production"]["items"][0]["stock_id"]
    for variant in VARIANTS:
        ids = {item["stock_id"] for item in variants[variant]["items"]}
        variants[variant]["overlap_with_recomputed_production"] = len(ids & production_ids)
        variants[variant]["overlap_rate_with_recomputed_production"] = round(len(ids & production_ids) / args.top_n, 6)
        variants[variant]["top1_changed_vs_recomputed_production"] = (
            variants[variant]["items"][0]["stock_id"] != production_top1
        )

    return {
        "date": date_text,
        "candidate_universe_rows": int(len(production_ranked)),
        "market_regime": market_regime.label,
        "official_top10_ids": official_ids,
        "variants": variants,
    }


def summarize(dates: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"date_count": len(dates), "variants": {}}
    for variant in VARIANTS:
        rows = [item["variants"][variant] for item in dates]
        overlaps = [numeric(row.get("overlap_rate_with_recomputed_production")) for row in rows]
        official = [numeric(row.get("official_overlap_rate")) for row in rows if row.get("official_overlap_rate") is not None]
        top1_changes = [bool(row.get("top1_changed_vs_recomputed_production")) for row in rows]
        avg_values = [numeric((row.get("stats") or {}).get("avg_avg_value_20d")) for row in rows]
        result["variants"][variant] = {
            "avg_overlap_rate_with_recomputed_production": round(sum(overlaps) / len(overlaps), 6) if overlaps else None,
            "avg_official_overlap_rate": round(sum(official) / len(official), 6) if official else None,
            "top1_change_count": sum(top1_changes),
            "avg_top10_avg_value_20d": round(sum(avg_values) / len(avg_values), 2) if avg_values else None,
        }
    return result


def decide(summary: dict[str, Any]) -> dict[str, Any]:
    log_gate = summary.get("variants", {}).get("log_gate", {})
    percentile = summary.get("variants", {}).get("percentile_gate", {})
    log_overlap = numeric(log_gate.get("avg_overlap_rate_with_recomputed_production"))
    percentile_overlap = numeric(percentile.get("avg_overlap_rate_with_recomputed_production"))
    candidates = []
    if 0.4 <= log_overlap < 1.0:
        candidates.append("log_gate")
    if 0.4 <= percentile_overlap < 1.0 and int(percentile.get("top1_change_count") or 0) <= int(log_gate.get("top1_change_count") or 0) + 2:
        candidates.append("percentile_gate")
    return {
        "status": "READY_FOR_REPLAY_EXTENSION" if candidates else "MONITOR_ONLY",
        "shadow_candidates": candidates,
        "production_ready": False,
        "reason": "完整候選池 shadow 已能檢查 Top10 成員變化；仍需 replay 才能判斷績效。",
        "next_step": "run replay on candidate-universe shadow rankings" if candidates else "keep diagnostic only",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    shadow_dir = resolve_path(args.shadow_ranking_dir)
    selected_dates = resolve_date_values(args)
    ranker = StockRanker(
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        artifact_dir=args.artifact_dir,
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model()
    dates = [analyze_date(ranker, date_text, args, shadow_dir) for date_text in selected_dates]
    summary = summarize(dates)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
            "candidate_scope": "full daily StockRanker candidate universe rebuilt in memory",
            "tradability_gate_preserved": True,
        },
        "inputs": {
            "dates": selected_dates,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "max_dates": args.max_dates,
            "data_dir": args.data_dir,
            "model_dir": args.model_dir,
            "top_n": args.top_n,
            "tradability_threshold": args.tradability_threshold,
            "log_full_score_value": args.log_full_score_value,
            "shadow_ranking_dir": repo_path(shadow_dir),
        },
        "summary": summary,
        "decision": decide(summary),
        "dates": dates,
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Quality Candidate Universe Shadow",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- candidate_scope: `{payload['contract']['candidate_scope']}`",
        "",
        "## Summary",
        "",
        "| variant | overlap vs recomputed production | overlap vs official | top1 changes | avg top10 value |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in payload["summary"].get("variants", {}).items():
        lines.append(
            f"| {variant} | {pct(row.get('avg_overlap_rate_with_recomputed_production'))} | {pct(row.get('avg_official_overlap_rate'))} | {row.get('top1_change_count')} | {money(row.get('avg_top10_avg_value_20d'))} |"
        )
    lines.extend(["", "## Daily Top1", ""])
    for item in payload.get("dates", []):
        production = item["variants"]["production"]["items"][0]["stock_id"]
        percentile = item["variants"]["percentile_gate"]["items"][0]["stock_id"]
        log_gate = item["variants"]["log_gate"]["items"][0]["stock_id"]
        lines.append(f"- {item['date']}: production `{production}`; percentile `{percentile}`; log `{log_gate}`")
    lines.extend(["", "## Decision", "", json.dumps(payload["decision"], ensure_ascii=False, indent=2), ""])
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
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
                "shadow_candidates": payload["decision"]["shadow_candidates"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
