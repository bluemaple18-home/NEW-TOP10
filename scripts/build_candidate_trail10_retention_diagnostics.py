#!/usr/bin/env python3
"""整理 candidate+trail10 是否該保留的診斷報告。

用途：把「長區間勝出」與「近期輸 production」拆清楚，避免因 overlap-first
失敗而誤砍 candidate+trail10 主候選。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "candidate-trail10-retention-diagnostics.v1"


DEFAULT_CANDIDATE_LONG = (
    "artifacts/model_experiments/"
    "odd_lot_portfolio_candidate_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_matrix_trail10_2026-06-10.json"
)
DEFAULT_PRODUCTION_LONG = (
    "artifacts/model_experiments/"
    "odd_lot_portfolio_production_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_trail10_2026-06-10.json"
)
DEFAULT_RECENT_100 = "artifacts/model_experiments/overlap_first_recommendation_performance_recent_100_2026-06-10.json"
DEFAULT_RECENT_6M = "artifacts/model_experiments/overlap_first_recommendation_performance_recent_6m_2026-06-10.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build candidate trail10 retention diagnostics")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-long", default=DEFAULT_CANDIDATE_LONG)
    parser.add_argument("--production-long", default=DEFAULT_PRODUCTION_LONG)
    parser.add_argument("--recent-100", default=DEFAULT_RECENT_100)
    parser.add_argument("--recent-6m", default=DEFAULT_RECENT_6M)
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def n(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def product_return(rows: list[dict[str, Any]]) -> float:
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return value - 1


def max_drawdown_from_returns(rows: list[dict[str, Any]]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for row in rows:
        equity *= 1 + n(row.get("daily_return"))
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst


def daily_slice(payload: dict[str, Any], start: str, end: str) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("daily", [])
        if start <= str(row.get("date")) <= end
    ]


def trade_slice(payload: dict[str, Any], start: str, end: str) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("trades", [])
        if start <= str(row.get("exit_date")) <= end
    ]


def window_summary(payload: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    daily = daily_slice(payload, start, end)
    trades = trade_slice(payload, start, end)
    returns = [n(row.get("net_return")) for row in trades]
    return {
        "start": start,
        "end": end,
        "daily_count": len(daily),
        "trade_count": len(trades),
        "total_return": round(product_return(daily), 6) if daily else None,
        "max_drawdown": round(max_drawdown_from_returns(daily), 6) if daily else None,
        "win_rate": round(sum(value > 0 for value in returns) / len(returns), 6) if returns else None,
        "avg_trade_return": round(sum(returns) / len(returns), 6) if returns else None,
    }


def compact_long(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    return {
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "trade_count": summary.get("trade_count"),
        "daily_count": summary.get("daily_count"),
    }


def compare(candidate: dict[str, Any], production: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(n(candidate.get("total_return")) - n(production.get("total_return")), 6),
        "drawdown_delta": round(n(candidate.get("max_drawdown")) - n(production.get("max_drawdown")), 6),
        "win_rate_delta": round(n(candidate.get("win_rate")) - n(production.get("win_rate")), 6),
        "avg_trade_return_delta": round(n(candidate.get("avg_trade_return")) - n(production.get("avg_trade_return")), 6),
    }


def recent_candidate_vs_production(payload: dict[str, Any]) -> dict[str, Any]:
    replays = payload.get("replays") if isinstance(payload.get("replays"), dict) else {}
    production = replays.get("production") if isinstance(replays.get("production"), dict) else {}
    candidate = replays.get("candidate") if isinstance(replays.get("candidate"), dict) else {}
    return {
        "window": payload.get("window"),
        "start": (payload.get("inputs") or {}).get("selected_start_date"),
        "end": (payload.get("inputs") or {}).get("selected_end_date"),
        "ranking_days": (payload.get("inputs") or {}).get("selected_ranking_days"),
        "production": production,
        "candidate": candidate,
        "candidate_vs_production": compare(candidate, production),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = resolve_path(args.candidate_long)
    production_path = resolve_path(args.production_long)
    recent_100_path = resolve_path(args.recent_100)
    recent_6m_path = resolve_path(args.recent_6m)
    for path in [candidate_path, production_path, recent_100_path, recent_6m_path]:
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到必要 artifact：{path}")
    candidate_long = read_json(candidate_path)
    production_long = read_json(production_path)
    recent_100 = read_json(recent_100_path)
    recent_6m = read_json(recent_6m_path)
    windows = {
        "2024_H1": ("2023-11-22", "2024-06-30"),
        "2024_H2": ("2024-07-01", "2024-12-31"),
        "2025_H1": ("2025-01-01", "2025-06-30"),
        "2025_H2": ("2025-07-01", "2025-12-31"),
        "2026_YTD_to_0515": ("2026-01-01", "2026-05-15"),
    }
    window_rows = []
    for label, (start, end) in windows.items():
        production_row = window_summary(production_long, start, end)
        candidate_row = window_summary(candidate_long, start, end)
        window_rows.append(
            {
                "window": label,
                "production": production_row,
                "candidate": candidate_row,
                "candidate_vs_production": compare(candidate_row, production_row),
            }
        )
    long_production = compact_long(production_long)
    long_candidate = compact_long(candidate_long)
    recent_checks = {
        "recent_100": recent_candidate_vs_production(recent_100),
        "recent_6m": recent_candidate_vs_production(recent_6m),
    }
    long_delta = compare(long_candidate, long_production)
    recent_100_delta = recent_checks["recent_100"]["candidate_vs_production"]
    recent_6m_delta = recent_checks["recent_6m"]["candidate_vs_production"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "diagnostic_only": True,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
        },
        "inputs": {
            "candidate_long": repo_path(candidate_path),
            "production_long": repo_path(production_path),
            "recent_100": repo_path(recent_100_path),
            "recent_6m": repo_path(recent_6m_path),
        },
        "summary": {
            "long_candidate_total_return": long_candidate.get("total_return"),
            "long_production_total_return": long_production.get("total_return"),
            "long_return_delta": long_delta["return_delta"],
            "long_drawdown_delta": long_delta["drawdown_delta"],
            "recent_100_return_delta": recent_100_delta["return_delta"],
            "recent_6m_return_delta": recent_6m_delta["return_delta"],
            "diagnosis": "long_supported_but_recent_underperforming",
            "operator_decision": "KEEP_CANDIDATE_TRAIL10_AS_MAIN_CANDIDATE_BUT_BLOCK_IMMEDIATE_SWITCH",
        },
        "long_replay": {
            "production": long_production,
            "candidate": long_candidate,
            "candidate_vs_production": long_delta,
        },
        "recent_replays": recent_checks,
        "calendar_window_breakdown": window_rows,
        "decision": {
            "overlap_first": "REJECTED_AS_REPLACEMENT",
            "candidate_trail10": "RETAIN_FOR_CONDITIONAL_SWITCH_RESEARCH",
            "production_switch_ready": False,
            "promotion_ready": False,
            "next_required_work": [
                "identify recent underperformance window and regime",
                "test candidate+trail10 as conditional profile, not overlap-first blend",
                "do not replace production until recent_100 or recent_6m no longer underperforms production",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Candidate Trail10 Retention Diagnostics",
        "",
        f"- diagnosis: `{summary['diagnosis']}`",
        f"- operator_decision: `{summary['operator_decision']}`",
        f"- long return delta: `{pct(summary['long_return_delta'])}`",
        f"- long drawdown delta: `{pct(summary['long_drawdown_delta'])}`",
        f"- recent_100 return delta: `{pct(summary['recent_100_return_delta'])}`",
        f"- recent_6m return delta: `{pct(summary['recent_6m_return_delta'])}`",
        "",
        "| Window | Production Return | Candidate Return | Delta | Production DD | Candidate DD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["calendar_window_breakdown"]:
        production = row["production"]
        candidate = row["candidate"]
        delta = row["candidate_vs_production"]
        lines.append(
            f"| {row['window']} | {pct(production.get('total_return'))} | {pct(candidate.get('total_return'))} | "
            f"{pct(delta.get('return_delta'))} | {pct(production.get('max_drawdown'))} | {pct(candidate.get('max_drawdown'))} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- overlap-first：淘汰，不作正式替換。",
            "- candidate+trail10：保留，不砍；但近期輸 production，不能今天直接切正式。",
            "- 下一步應研究條件式切換或近期退化原因，而不是新增第四條排序支線。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_trail10_retention_diagnostics_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "diagnosis": payload["summary"]["diagnosis"],
                "operator_decision": payload["summary"]["operator_decision"],
                "output": repo_path(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
