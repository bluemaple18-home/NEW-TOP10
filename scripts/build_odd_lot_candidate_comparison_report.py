#!/usr/bin/env python3
"""彙整固定本金零股候選比較報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-candidate-comparison-report.v1"


VARIANTS = ("production_top7", "production_top7_sl12_min5", "candidate_top7", "candidate_top7_sl12_min5")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot candidate comparison report")
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


def artifact_path(variant: str, capital: int, run_date: str) -> Path:
    if variant == "production_top7":
        name = f"odd_lot_portfolio_production_top7_{capital // 1000}k_gross85_{run_date}.json"
    elif variant == "production_top7_sl12_min5":
        name = f"odd_lot_portfolio_production_top7_sl12_min5_{capital // 1000}k_gross85_{run_date}.json"
    elif variant == "candidate_top7":
        name = f"odd_lot_portfolio_candidate_top7_{capital // 1000}k_gross85_{run_date}.json"
    else:
        name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital // 1000}k_gross85_{run_date}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / name


def peer_variant(variant: str) -> str:
    if variant == "candidate_top7_sl12_min5":
        return "production_top7_sl12_min5"
    return "production_top7"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def row_for(
    variant: str,
    capital: int,
    path: Path,
    production_summary: dict[str, Any],
    peer_summary: dict[str, Any],
    peer_path: Path,
) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary", {})
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    production_return = safe_float(production_summary.get("total_return"))
    production_drawdown = safe_float(production_summary.get("max_drawdown"))
    peer_return = safe_float(peer_summary.get("total_return"))
    peer_drawdown = safe_float(peer_summary.get("max_drawdown"))
    return {
        "variant": variant,
        "capital": capital,
        "path": repo_path(path),
        "peer_variant": peer_variant(variant),
        "peer_path": repo_path(peer_path),
        "final_equity": summary.get("final_equity"),
        "total_pnl": summary.get("total_pnl"),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "below_minimum_odd_lot_count": summary.get("below_minimum_odd_lot_count"),
        "return_delta_vs_production": round(total_return - production_return, 6),
        "drawdown_delta_vs_production": round(max_drawdown - production_drawdown, 6),
        "return_delta_vs_peer": round(total_return - peer_return, 6),
        "drawdown_delta_vs_peer": round(max_drawdown - peer_drawdown, 6),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(row["variant"], []).append(row)
    result = {}
    for variant, items in by_variant.items():
        result[variant] = {
            "capital_count": len(items),
            "avg_return": round(sum(safe_float(row["total_return"]) for row in items) / len(items), 6),
            "avg_max_drawdown": round(sum(safe_float(row["max_drawdown"]) for row in items) / len(items), 6),
            "avg_return_delta_vs_production": round(sum(safe_float(row["return_delta_vs_production"]) for row in items) / len(items), 6),
            "avg_return_delta_vs_peer": round(sum(safe_float(row["return_delta_vs_peer"]) for row in items) / len(items), 6),
            "worst_drawdown": min(safe_float(row["max_drawdown"]) for row in items),
            "min_return_delta_vs_production": min(safe_float(row["return_delta_vs_production"]) for row in items),
            "min_return_delta_vs_peer": min(safe_float(row["return_delta_vs_peer"]) for row in items),
        }
    return result


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    candidates = {
        variant: data
        for variant, data in summary.items()
        if not variant.startswith("production_")
        and data["min_return_delta_vs_production"] > 0
        and data["min_return_delta_vs_peer"] > 0
    }
    if not candidates:
        return {
            "status": "NO_ODD_LOT_CANDIDATE",
            "selected": None,
            "promotion_ready": False,
            "reason": "候選規則沒有在所有本金級距都勝過 production。",
        }
    selected = max(candidates.items(), key=lambda item: item[1]["avg_return_delta_vs_production"])[0]
    balanced = min(candidates.items(), key=lambda item: abs(item[1]["avg_max_drawdown"]))[0]
    return {
        "status": "ODD_LOT_REPLAY_CANDIDATE",
        "selected_return_candidate": selected,
        "selected_balanced_candidate": balanced,
        "promotion_ready": False,
        "reason": "候選規則在 10萬/30萬/50萬本金下都保留報酬優勢，但仍需確認回撤與盤勢分層後才可進 promotion review。",
        "peer_rule": "candidate variants must beat both production_top7 and their matching production peer when available",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows = []
    missing = []
    for capital in capital_levels:
        production_path = artifact_path("production_top7", capital, args.date)
        if not production_path.exists():
            missing.append(repo_path(production_path))
            continue
        production_summary = read_json(production_path).get("summary", {})
        for variant in VARIANTS:
            path = artifact_path(variant, capital, args.date)
            if not path.exists():
                missing.append(repo_path(path))
                continue
            peer_path = artifact_path(peer_variant(variant), capital, args.date)
            if not peer_path.exists():
                missing.append(repo_path(peer_path))
                continue
            peer_summary = read_json(peer_path).get("summary", {})
            rows.append(row_for(variant, capital, path, production_summary, peer_summary, peer_path))
    summary = summarize(rows)
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
            "gross_exposure": 0.85,
            "max_position_weight": 0.15,
        },
        "summary": summary,
        "decision": decision(summary),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Odd-Lot Candidate Comparison",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- return_candidate: {payload['decision'].get('selected_return_candidate')}",
        f"- balanced_candidate: {payload['decision'].get('selected_balanced_candidate')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            "- {variant} {capital}: return={total_return}, maxDD={max_drawdown}, "
            "delta={return_delta_vs_production}, peer_delta={return_delta_vs_peer}, cash={avg_cash_weight}".format(**row)
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_candidate_comparison_report_{args.date}.json"
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
