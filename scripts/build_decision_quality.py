#!/usr/bin/env python3
"""彙整每日 Top10 決策品質摘要。

本腳本只讀既有 ranking / persistence / replay / market context artifacts，
並可用本地 data/reference mapping 做中性 reference annotation；
不重跑模型、不重算 ranking score，也不觸發外部 API。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "decision-quality.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily Top10 decision quality summary")
    parser.add_argument("--date", default=None, help="ranking 日期，格式 YYYY-MM-DD；未指定時使用最新 ranking")
    parser.add_argument("--ranking", default=None, help="指定 ranking CSV 路徑")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--persistence", default=None, help="candidate_persistence JSON；未指定時依 ranking date 尋找")
    parser.add_argument("--backtest", default=None, help="production replay JSON；未指定時使用 artifacts/backtest/replay_*.json 最新檔")
    parser.add_argument("--portfolio", default=None, help="portfolio replay JSON；未指定時使用 artifacts/backtest/portfolio_replay_*.json 最新檔")
    parser.add_argument("--market-context", default=None, help="market_context JSON；未指定時只使用同日期 artifact")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output", default=None, help="輸出 JSON；未指定時寫 artifacts/decision_quality_YYYY-MM-DD.json")
    return parser.parse_args()


def resolve_path(value: str | None, base: Path = PROJECT_ROOT) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_date(path: Path) -> str:
    match = re.search(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def portfolio_replay_date(path: Path | None) -> str | None:
    if path is None:
        return None
    match = re.search(r"portfolio_replay_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    return match.group(1) if match else None


def sorted_ranking_files(artifacts_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in artifacts_dir.glob("ranking_*.csv")
            if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)
        ],
        key=ranking_date,
    )


def resolve_ranking_path(artifacts_dir: Path, date: str | None, ranking: str | None) -> Path:
    if ranking:
        path = resolve_path(ranking)
        if path and path.exists():
            return path
        raise FileNotFoundError(f"指定 ranking 不存在：{path}")
    if date:
        path = artifacts_dir / f"ranking_{date}.csv"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 ranking 不存在：{path}")
    files = sorted_ranking_files(artifacts_dir)
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{artifacts_dir}")
    return files[-1]


def latest_existing(pattern: str, base: Path) -> Path | None:
    files = sorted(base.glob(pattern))
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_top_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    frame = pd.read_csv(path, dtype={"stock_id": str}).head(top_n)
    frame = ReferenceRepository(PROJECT_ROOT).annotate_ranking(frame)
    items: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        stock_id = str(row.get("stock_id", "")).strip().zfill(4)
        items.append(
            {
                "rank": int(index) + 1,
                "stock_id": stock_id,
                "stock_name": text_value(row.get("stock_name")),
                "scores": {
                    "risk_adjusted_score": number_value(row.get("risk_adjusted_score")),
                    "final_score": number_value(row.get("final_score")),
                    "model_prob": number_value(row.get("model_prob")),
                    "prediction_score": number_value(row.get("prediction_score")),
                    "setup_score": number_value(row.get("setup_score")),
                    "quality_score": number_value(row.get("quality_score")),
                    "risk_penalty": number_value(row.get("risk_penalty")),
                },
                "position": {
                    "suggested_weight": number_value(row.get("suggested_weight")),
                    "max_position_weight": number_value(row.get("max_position_weight")),
                    "gross_exposure": number_value(row.get("gross_exposure")),
                    "allocated_exposure": number_value(row.get("allocated_exposure")),
                    "cash_weight": number_value(row.get("cash_weight")),
                },
                "market_regime": text_value(row.get("market_regime")),
                "reference": {
                    "industry_name": text_value(row.get("industry_name")),
                    "sector_name": text_value(row.get("sector_name")),
                    "market_type": text_value(row.get("market_type")),
                },
            }
        )
    return items


def load_persistence(path: Path | None) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    return {
        str(item.get("stock_id", "")).zfill(4): item
        for item in payload.get("items", [])
        if item.get("stock_id")
    }


def persistence_summary(stock_id: str, persistence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = persistence.get(stock_id)
    if not item:
        return {"available": False}
    return {
        "available": True,
        "first_seen_date": item.get("first_seen_date"),
        "consecutive_ranked_days": item.get("consecutive_ranked_days"),
        "ranked_history_count": item.get("ranked_history_count"),
        "previous_rank": item.get("previous_rank"),
        "rank_delta": item.get("rank_delta"),
    }


def historical_backtest_summary(
    stock_id: str,
    replay_payload: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    if not replay_payload:
        return {"available": False, "reason": "missing_backtest_replay_artifact"}
    trades = [
        trade
        for trade in replay_payload.get("trades", [])
        if str(trade.get("stock_id", "")).zfill(4) == stock_id
        and text_value(trade.get("ranking_date")) < target_date
        and number_value(trade.get("net_return")) is not None
    ]
    if not trades:
        return {"available": False, "reason": "no_matured_history_before_ranking_date"}

    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon, group in group_by(trades, lambda item: str(item.get("horizon"))).items():
        returns = [float(item["net_return"]) for item in group]
        maes = [float(item["mae"]) for item in group if number_value(item.get("mae")) is not None]
        mfes = [float(item["mfe"]) for item in group if number_value(item.get("mfe")) is not None]
        latest = sorted(group, key=lambda item: text_value(item.get("ranking_date")))[-1]
        by_horizon[horizon] = {
            "trade_count": len(group),
            "avg_net_return": rounded(mean(returns)),
            "median_net_return": rounded(median(returns)),
            "hit_rate": rounded(sum(value > 0 for value in returns) / len(returns)),
            "avg_mae": rounded(mean(maes)) if maes else None,
            "avg_mfe": rounded(mean(mfes)) if mfes else None,
            "latest_ranking_date": latest.get("ranking_date"),
            "latest_net_return": number_value(latest.get("net_return")),
        }
    return {
        "available": True,
        "source_schema_version": replay_payload.get("schema_version"),
        "trade_count": len(trades),
        "horizons": by_horizon,
    }


def portfolio_date_alignment(artifact_date: str | None, target_date: str) -> str:
    if artifact_date is None:
        return "unknown"
    if artifact_date == target_date:
        return "exact"
    if artifact_date > target_date:
        return "future"
    return "stale"


def portfolio_risk_summary(payload: dict[str, Any], source_path: Path | None, target_date: str) -> dict[str, Any]:
    if not payload:
        return {"available": False, "reason": "missing_exact_portfolio_replay_artifact"}
    artifact_date = portfolio_replay_date(source_path)
    alignment = portfolio_date_alignment(artifact_date, target_date)
    if alignment != "exact":
        return {
            "available": False,
            "reason": "portfolio_replay_date_mismatch",
            "source": repo_path(source_path),
            "artifact_date": artifact_date,
            "target_date": target_date,
            "date_alignment": alignment,
            "source_schema_version": payload.get("schema_version"),
        }
    summary = payload.get("summary", {})
    risk = {
        "final_equity": number_value(summary.get("final_equity")),
        "total_return": number_value(summary.get("total_return")),
        "max_drawdown": number_value(summary.get("max_drawdown")),
        "trade_count": summary.get("trade_count"),
        "skipped_count": summary.get("skipped_count"),
        "win_rate": number_value(summary.get("win_rate")),
        "avg_trade_return": number_value(summary.get("avg_trade_return")),
        "max_gross_exposure": number_value(summary.get("max_gross_exposure")),
        "avg_gross_exposure": number_value(summary.get("avg_gross_exposure")),
        "max_group_exposure": number_value(summary.get("max_group_exposure")),
    }
    return {
        "available": True,
        "source": repo_path(source_path),
        "artifact_date": artifact_date,
        "target_date": target_date,
        "date_alignment": alignment,
        "source_schema_version": payload.get("schema_version"),
        "inputs": {
            "horizon": payload.get("inputs", {}).get("horizon"),
            "max_gross_exposure": payload.get("inputs", {}).get("max_gross_exposure"),
            "max_group_exposure": payload.get("inputs", {}).get("max_group_exposure"),
        },
        "summary": risk,
        "risk_flags": portfolio_risk_flags(risk),
    }


def portfolio_risk_flags(summary: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    max_drawdown = number_value(summary.get("max_drawdown"))
    max_gross = number_value(summary.get("max_gross_exposure"))
    skipped = summary.get("skipped_count")
    if max_drawdown is not None and max_drawdown <= -0.1:
        flags.append("max_drawdown_over_10pct")
    if max_gross is not None and max_gross > 0.8:
        flags.append("gross_exposure_over_80pct")
    if isinstance(skipped, int) and skipped > 0:
        flags.append("replay_has_skipped_entries")
    return flags


def market_context_summary(payload: dict[str, Any], source_path: Path | None, target_date: str) -> dict[str, Any]:
    if not payload:
        return {"available": False, "reason": "missing_exact_market_context_artifact"}
    trade_date = payload.get("trade_date")
    alignment = "exact" if trade_date == target_date else "provided_mismatch"
    return {
        "available": True,
        "source": repo_path(source_path),
        "trade_date": trade_date,
        "date_alignment": alignment,
        "summary": payload.get("summary", {}),
        "taiex": payload.get("taiex", {}),
        "breadth": payload.get("breadth", {}),
        "institutional": payload.get("institutional", {}),
        "futures": payload.get("futures", {}),
        "options": payload.get("options", {}),
        "source_status": payload.get("source_status", {}),
    }


def resolve_market_context_path(args: argparse.Namespace, artifacts_dir: Path, target_date: str) -> Path | None:
    if args.market_context:
        return resolve_path(args.market_context)
    exact = artifacts_dir / f"market_context_{target_date}.json"
    return exact if exact.exists() else None


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = resolve_path(args.artifacts_dir) or ARTIFACTS_DIR
    ranking_path = resolve_ranking_path(artifacts_dir=artifacts_dir, date=args.date, ranking=args.ranking)
    target_date = ranking_date(ranking_path)
    persistence_path = resolve_path(args.persistence) or artifacts_dir / f"candidate_persistence_{target_date}.json"
    backtest_path = resolve_path(args.backtest) or latest_existing("replay_*.json", artifacts_dir / "backtest")
    portfolio_path = resolve_path(args.portfolio) or latest_existing("portfolio_replay_*.json", artifacts_dir / "backtest")
    market_context_path = resolve_market_context_path(args, artifacts_dir, target_date)

    ranking_items = read_top_ranking(ranking_path, args.top_n)
    persistence = load_persistence(persistence_path)
    replay_payload = load_json(backtest_path)
    portfolio_payload = load_json(portfolio_path)
    market_payload = load_json(market_context_path)
    portfolio_risk = portfolio_risk_summary(portfolio_payload, portfolio_path, target_date)
    market_context = market_context_summary(market_payload, market_context_path, target_date)

    enriched_items = []
    for item in ranking_items:
        enriched_items.append(
            {
                **item,
                "persistence": persistence_summary(item["stock_id"], persistence),
                "historical_backtest": historical_backtest_summary(item["stock_id"], replay_payload, target_date),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": target_date,
        "contract": {
            "ranking_score_policy": "read_only_annotation; ranking scores are copied for context only and never recomputed",
            "data_source_policy": (
                "existing_artifacts_plus_read_only_local_reference_mapping; "
                "no model, ranking, replay, ETL, or external API execution"
            ),
            "reference_scope": "read-only data/reference mapping for neutral industry/sector/market annotation only",
            "backtest_scope": "stock replay trades with ranking_date < target ranking_date",
            "portfolio_replay_scope": "exact ranking_date artifact only; mismatched artifacts are marked unavailable",
            "market_context_scope": "exact ranking_date artifact by default; explicit --market-context is marked if date mismatches",
            "model_feature": False,
        },
        "inputs": {
            "ranking": repo_path(ranking_path),
            "persistence": repo_path(persistence_path) if persistence_path and persistence_path.exists() else None,
            "backtest_replay": repo_path(backtest_path) if backtest_path and backtest_path.exists() else None,
            "portfolio_replay": repo_path(portfolio_path) if portfolio_path and portfolio_path.exists() else None,
            "market_context": repo_path(market_context_path) if market_context_path and market_context_path.exists() else None,
            "top_n": args.top_n,
        },
        "summary": summary(enriched_items, portfolio_risk, market_context),
        "portfolio_replay_risk": portfolio_risk,
        "market_context": market_context,
        "top10": enriched_items,
    }


def summary(items: list[dict[str, Any]], portfolio_risk: dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_count": len(items),
        "persistence_available_count": sum(1 for item in items if item["persistence"].get("available")),
        "historical_backtest_available_count": sum(1 for item in items if item["historical_backtest"].get("available")),
        "portfolio_replay_risk_available": bool(portfolio_risk.get("available")),
        "market_context_available": bool(market_context.get("available")),
        "risk_flags": portfolio_risk.get("risk_flags", []),
        "market_context_label": (market_context.get("summary") or {}).get("domestic_context_label"),
    }


def group_by(items: list[dict[str, Any]], key_func) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(key_func(item), []).append(item)
    return grouped


def text_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def number_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return round(parsed, 6)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def rounded(value: float) -> float:
    return round(float(value), 6)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = resolve_path(args.output) if args.output else ARTIFACTS_DIR / f"decision_quality_{payload['ranking_date']}.json"
    if output_path is None:
        raise RuntimeError("output path resolution failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output_path),
                "ranking_date": payload["ranking_date"],
                "top_count": payload["summary"]["top_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
