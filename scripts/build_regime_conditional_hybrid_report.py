#!/usr/bin/env python3
"""彙整 regime conditional hybrid ranking replay 報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "regime-conditional-hybrid-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build regime conditional hybrid replay report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital-levels", default="100000,300000,500000")
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


def artifact_path(side: str, capital: int, run_date: str) -> Path:
    prefix = PROJECT_ROOT / "artifacts" / "model_experiments"
    k = capital // 1000
    if side == "production":
        name = f"odd_lot_portfolio_production_top7_sl12_min5_{k}k_gross75_pos12_{run_date}.json"
    elif side == "candidate_all":
        name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{k}k_gross75_pos12_{run_date}.json"
    elif side == "hybrid_big_bull":
        name = f"odd_lot_portfolio_hybrid_big_bull_candidate_top7_sl12_min5_{k}k_g75_pos12_{run_date}.json"
    else:
        raise ValueError(f"unknown side: {side}")
    return prefix / name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def row(side: str, capital: int, path: Path, production: dict[str, Any], candidate_all: dict[str, Any]) -> dict[str, Any]:
    summary = read_json(path).get("summary", {})
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    return {
        "side": side,
        "capital": capital,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "total_pnl": summary.get("total_pnl"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "return_delta_vs_production": round(total_return - safe_float(production.get("total_return")), 6),
        "drawdown_delta_vs_production": round(max_drawdown - safe_float(production.get("max_drawdown")), 6),
        "return_delta_vs_candidate_all": round(total_return - safe_float(candidate_all.get("total_return")), 6),
        "drawdown_delta_vs_candidate_all": round(max_drawdown - safe_float(candidate_all.get("max_drawdown")), 6),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for side in sorted({row["side"] for row in rows}):
        items = [row for row in rows if row["side"] == side]
        result[side] = {
            "capital_count": len(items),
            "avg_return": round(sum(safe_float(item["total_return"]) for item in items) / len(items), 6),
            "avg_max_drawdown": round(sum(safe_float(item["max_drawdown"]) for item in items) / len(items), 6),
            "avg_return_delta_vs_production": round(
                sum(safe_float(item["return_delta_vs_production"]) for item in items) / len(items),
                6,
            ),
            "avg_return_delta_vs_candidate_all": round(
                sum(safe_float(item["return_delta_vs_candidate_all"]) for item in items) / len(items),
                6,
            ),
        }
    return result


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    hybrid = summary.get("hybrid_big_bull", {})
    candidate = summary.get("candidate_all", {})
    if safe_float(hybrid.get("avg_return_delta_vs_production")) <= 0:
        status = "HYBRID_REJECTED"
        reason = "BIG_BULL-only hybrid 沒有勝過 production。"
    elif safe_float(hybrid.get("avg_return")) < safe_float(candidate.get("avg_return")) and safe_float(hybrid.get("avg_max_drawdown")) > safe_float(candidate.get("avg_max_drawdown")):
        status = "HYBRID_MONITOR_ONLY"
        reason = "hybrid 勝過 production，但相對 all-candidate 報酬較低、回撤只小幅改善；先 monitor，不作主升級路線。"
    else:
        status = "HYBRID_CANDIDATE"
        reason = "hybrid 同時保留報酬優勢並改善風險，可進下一階段。"
    return {
        "status": status,
        "promotion_ready": False,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for capital in capital_levels:
        paths = {side: artifact_path(side, capital, args.date) for side in ["production", "candidate_all", "hybrid_big_bull"]}
        for path in paths.values():
            if not path.exists():
                missing.append(repo_path(path))
        if any(not path.exists() for path in paths.values()):
            continue
        production = read_json(paths["production"]).get("summary", {})
        candidate = read_json(paths["candidate_all"]).get("summary", {})
        for side, path in paths.items():
            rows.append(row(side, capital, path, production, candidate))
    summary = aggregate(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if rows and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "capital_levels": capital_levels,
            "ranking_policy": "BIG_BULL uses candidate ranking; inactive regimes use production ranking",
        },
        "summary": summary,
        "decision": decision(summary),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Regime Conditional Hybrid Report",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Summary",
        "",
    ]
    for side, item in payload["summary"].items():
        lines.append(f"- {side}: avg_return={item['avg_return']}, avg_maxDD={item['avg_max_drawdown']}")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"regime_conditional_hybrid_report_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
