#!/usr/bin/env python3
"""彙整 odd-lot 候選的分盤勢敏感度報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-regime-sensitivity-report.v1"
REGIMES = ("BIG_BULL", "HIGH_CHOPPY_CONTEXT", "OTHER")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot regime sensitivity report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital-levels", default="100000,300000,500000")
    parser.add_argument("--variant", default="top7_sl12_min5")
    parser.add_argument("--setting", default="g75_pos12")
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


def artifact_path(capital: int, run_date: str, variant: str, setting: str) -> Path:
    label = f"odd_lot_candidate_{variant}_{capital // 1000}k_{setting}"
    name = f"portfolio_replay_regime_attribution_{label}_{run_date}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def rows_from_payload(capital: int, path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    for regime in REGIMES:
        item = comparison.get(regime, {})
        candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
        production = item.get("production") if isinstance(item.get("production"), dict) else {}
        rows.append(
            {
                "capital": capital,
                "regime": regime,
                "path": repo_path(path),
                "candidate_trade_count": candidate.get("trade_count"),
                "production_trade_count": production.get("trade_count"),
                "candidate_avg_net_return": candidate.get("avg_net_return"),
                "production_avg_net_return": production.get("avg_net_return"),
                "avg_net_return_delta": item.get("avg_net_return_delta"),
                "candidate_win_rate": candidate.get("win_rate"),
                "production_win_rate": production.get("win_rate"),
                "win_rate_delta": item.get("win_rate_delta"),
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for regime in REGIMES:
        items = [row for row in rows if row["regime"] == regime]
        result[regime] = {
            "capital_count": len(items),
            "total_candidate_trades": sum(int(row.get("candidate_trade_count") or 0) for row in items),
            "total_production_trades": sum(int(row.get("production_trade_count") or 0) for row in items),
            "avg_delta": round(sum(safe_float(row.get("avg_net_return_delta")) for row in items) / len(items), 6) if items else None,
            "avg_win_rate_delta": round(sum(safe_float(row.get("win_rate_delta")) for row in items) / len(items), 6) if items else None,
            "min_delta": min((safe_float(row.get("avg_net_return_delta")) for row in items), default=None),
        }
    return result


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    big = summary.get("BIG_BULL", {})
    choppy = summary.get("HIGH_CHOPPY_CONTEXT", {})
    big_ok = safe_float(big.get("min_delta")) > 0 and int(big.get("total_candidate_trades") or 0) >= 30
    choppy_monitor = int(choppy.get("total_candidate_trades") or 0) >= 20
    if big_ok and choppy_monitor:
        status = "BIG_BULL_OK_HIGH_CHOPPY_MONITOR"
        reason = "BIG_BULL 證據可用；HIGH_CHOPPY_CONTEXT 有樣本但優勢較薄，維持 monitor。"
    else:
        status = "REGIME_EVIDENCE_INCOMPLETE"
        reason = "分盤勢樣本或 delta 不足，不能升級。"
    return {
        "status": status,
        "promotion_ready": False,
        "big_bull_ready_for_next_review": big_ok,
        "high_choppy_monitor_only": choppy_monitor,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for capital in capital_levels:
        path = artifact_path(capital, args.date, args.variant, args.setting)
        if not path.exists():
            missing.append(repo_path(path))
            continue
        rows.extend(rows_from_payload(capital, path, read_json(path)))
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
            "fixed_capital_odd_lot": True,
        },
        "inputs": {
            "capital_levels": capital_levels,
            "variant": args.variant,
            "setting": args.setting,
        },
        "summary": summary,
        "decision": decision(summary),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Odd-Lot Regime Sensitivity",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Summary",
        "",
    ]
    for regime, item in payload["summary"].items():
        lines.append(
            f"- {regime}: avg_delta={item.get('avg_delta')}, "
            f"win_delta={item.get('avg_win_rate_delta')}, candidate_trades={item.get('total_candidate_trades')}"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_regime_sensitivity_report_{args.date}.json"
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
