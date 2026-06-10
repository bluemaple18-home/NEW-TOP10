#!/usr/bin/env python3
"""產出 candidate ranking + trail10 每日 shadow monitor。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker  # noqa: E402


SCHEMA_VERSION = "candidate-trail10-daily-shadow-monitor.v1"
DEFAULT_CANDIDATE_ROOT = "artifacts/model_experiments/training_candidates/current_baseline_candidate_2026-06-08"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build candidate trail10 daily shadow monitor")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--production-ranking", default=None)
    parser.add_argument("--candidate-root", default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--candidate-ranking-dir", default=None)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--actionable-top-n", type=int, default=7)
    parser.add_argument("--initial-cash", type=float, default=300_000)
    parser.add_argument("--max-gross-exposure", type=float, default=0.75)
    parser.add_argument("--max-position-weight", type=float, default=0.12)
    parser.add_argument("--stop-loss-pct", type=float, default=0.12)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.10)
    parser.add_argument("--min-event-holding-days", type=int, default=5)
    parser.add_argument("--max-holding-days", type=int, default=40)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def production_ranking_path(args: argparse.Namespace) -> Path:
    if args.production_ranking:
        path = resolve_path(args.production_ranking)
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到 production ranking：{args.production_ranking}")
        return path
    path = PROJECT_ROOT / "artifacts" / f"ranking_{args.date}.csv"
    if path.exists():
        return path
    files = sorted((PROJECT_ROOT / "artifacts").glob("ranking_*.csv"))
    if not files:
        raise FileNotFoundError("找不到 artifacts/ranking_*.csv")
    return files[-1]


def normalize_stock_id(value: Any) -> str:
    return str(value or "").strip().replace(".0", "").zfill(4)


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for rank, row in enumerate(csv.DictReader(handle), start=1):
            if rank > top_n:
                break
            normalized = dict(row)
            normalized["rank"] = rank
            normalized["stock_id"] = normalize_stock_id(normalized.get("stock_id"))
            rows.append(normalized)
    return rows


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def generate_candidate_ranking(args: argparse.Namespace, candidate_root: Path, output_dir: Path) -> tuple[Path, str]:
    model_dir = candidate_root / "models"
    ranker = StockRanker(
        data_dir=args.data_dir,
        model_dir=str(model_dir),
        artifact_dir=str(output_dir),
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model()
    captured = StringIO()
    with redirect_stdout(captured):
        ranking_path = Path(ranker.run_ranking(date=args.date))
    return ranking_path, captured.getvalue()[-1000:]


def candidate_ranking_path(args: argparse.Namespace, candidate_root: Path) -> tuple[Path, str]:
    output_dir = resolve_path(args.candidate_ranking_dir)
    if output_dir is None:
        output_dir = candidate_root / "candidate_trail10_daily_shadow_rankings"
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = output_dir / f"ranking_{args.date}.csv"
    if expected.exists():
        return expected, "existing candidate shadow ranking reused"
    return generate_candidate_ranking(args, candidate_root, output_dir)


def trail10_plan(row: dict[str, Any], args: argparse.Namespace, rank: int) -> dict[str, Any]:
    close = to_float(row.get("close"), 0.0) or 0.0
    hard_stop = close * (1 - args.stop_loss_pct) if close > 0 else None
    initial_trailing_floor = close * (1 - args.trailing_stop_pct) if close > 0 else None
    position_cap = min(to_float(row.get("max_position_weight"), args.max_position_weight) or args.max_position_weight, args.max_position_weight)
    return {
        "rank": rank,
        "stock_id": row.get("stock_id"),
        "stock_name": row.get("stock_name"),
        "close": round(close, 4) if close else None,
        "entry_reference": round(close, 4) if close else None,
        "hard_stop_loss_pct": args.stop_loss_pct,
        "hard_stop_loss_price": round(hard_stop, 4) if hard_stop is not None else None,
        "trailing_stop_pct": args.trailing_stop_pct,
        "initial_trailing_floor": round(initial_trailing_floor, 4) if initial_trailing_floor is not None else None,
        "trailing_rule": "持有滿 5 個交易日後，以持有期間最高價往下 10% 作移動停利/轉弱線。",
        "min_event_holding_days": args.min_event_holding_days,
        "max_holding_days": args.max_holding_days,
        "max_position_weight": round(position_cap, 6),
        "gross_exposure": args.max_gross_exposure,
        "model_prob": to_float(row.get("model_prob")),
        "risk_adjusted_score": to_float(row.get("risk_adjusted_score")),
        "market_regime": row.get("market_regime"),
    }


def compare_rankings(production: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    production_ids = [row["stock_id"] for row in production]
    candidate_ids = [row["stock_id"] for row in candidate]
    overlap = [stock_id for stock_id in candidate_ids if stock_id in set(production_ids)]
    return {
        "production_count": len(production),
        "candidate_count": len(candidate),
        "overlap_count": len(overlap),
        "overlap_stock_ids": overlap,
        "candidate_only_stock_ids": [stock_id for stock_id in candidate_ids if stock_id not in set(production_ids)],
        "production_only_stock_ids": [stock_id for stock_id in production_ids if stock_id not in set(candidate_ids)],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_root = resolve_path(args.candidate_root)
    if candidate_root is None or not candidate_root.exists():
        raise FileNotFoundError(f"找不到 candidate root：{args.candidate_root}")
    production_path = production_ranking_path(args)
    candidate_path, ranking_stdout = candidate_ranking_path(args, candidate_root)
    production_rows = read_ranking(production_path, args.top_n)
    candidate_rows = read_ranking(candidate_path, args.top_n)
    actionable = candidate_rows[: args.actionable_top_n]
    comparison = compare_rankings(production_rows, candidate_rows)
    trade_plans = [trail10_plan(row, args, rank=index + 1) for index, row in enumerate(actionable)]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "monitor_status": "READY_FOR_DAILY_SHADOW_MONITOR",
        "contract": {
            "operational_shadow_only": True,
            "changes_production_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
            "default_allowed": False,
        },
        "inputs": {
            "candidate_root": repo_path(candidate_root),
            "production_ranking": repo_path(production_path),
            "candidate_ranking": repo_path(candidate_path),
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "top_n": args.top_n,
            "actionable_top_n": args.actionable_top_n,
            "ranking_stdout_tail": ranking_stdout,
        },
        "policy": {
            "name": "candidate_ranking_top7_trail10_shadow",
            "initial_cash": args.initial_cash,
            "max_gross_exposure": args.max_gross_exposure,
            "max_position_weight": args.max_position_weight,
            "stop_loss_pct": args.stop_loss_pct,
            "trailing_stop_pct": args.trailing_stop_pct,
            "min_event_holding_days": args.min_event_holding_days,
            "max_holding_days": args.max_holding_days,
        },
        "summary": {
            "production_ranking_date": production_path.stem.removeprefix("ranking_"),
            "candidate_ranking_date": candidate_path.stem.removeprefix("ranking_"),
            "overlap_count": comparison["overlap_count"],
            "candidate_only_count": len(comparison["candidate_only_stock_ids"]),
            "production_only_count": len(comparison["production_only_stock_ids"]),
            "actionable_count": len(trade_plans),
            "operator_note": "後台 shadow only；今天不改正式榜、不改推播。",
        },
        "comparison": comparison,
        "candidate_top10": [
            {
                "rank": row.get("rank"),
                "stock_id": row.get("stock_id"),
                "stock_name": row.get("stock_name"),
                "close": to_float(row.get("close")),
                "model_prob": to_float(row.get("model_prob")),
                "risk_adjusted_score": to_float(row.get("risk_adjusted_score")),
                "market_regime": row.get("market_regime"),
            }
            for row in candidate_rows
        ],
        "trail10_trade_plans": trade_plans,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Candidate Trail10 Daily Shadow Monitor",
        "",
        f"- status: `{payload['status']}`",
        f"- monitor_status: `{payload['monitor_status']}`",
        f"- production_ranking_date: `{summary['production_ranking_date']}`",
        f"- candidate_ranking_date: `{summary['candidate_ranking_date']}`",
        f"- overlap_count: `{summary['overlap_count']}`",
        f"- actionable_count: `{summary['actionable_count']}`",
        "",
        "## Candidate Top7 Trail10",
        "",
        "| Rank | Stock | Close | Hard Stop | Initial Trail Floor |",
        "|---:|---|---:|---:|---:|",
    ]
    for row in payload["trail10_trade_plans"]:
        lines.append(
            f"| {row['rank']} | {row['stock_id']} {row.get('stock_name') or ''} | {row.get('close')} | {row.get('hard_stop_loss_price')} | {row.get('initial_trailing_floor')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 不改正式 Top10。",
            "- 不改 ranking CSV。",
            "- 不改 Clawd 訊息。",
            "- 不改模型。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_trail10_daily_shadow_monitor_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "monitor_status": payload["monitor_status"],
                "output": repo_path(output),
                "candidate_ranking": payload["inputs"]["candidate_ranking"],
                "overlap_count": payload["summary"]["overlap_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
