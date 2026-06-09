#!/usr/bin/env python3
"""彙整 odd-lot HIGH_CHOPPY 推薦日降曝險報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-regime-throttle-report.v1"
VARIANTS = ("baseline", "hc45", "hc55", "hc65")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot regime throttle report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital", type=int, default=300_000)
    parser.add_argument("--variant", default="candidate_top7_sl12_min5")
    parser.add_argument("--setting", default="gross75_pos12")
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


def artifact_path(name: str, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    if name == "baseline":
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json"
    else:
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_regime_signal_throttle_{name}_{run_date}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / file_name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def entry_limit_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    buckets: dict[float, dict[str, Any]] = {}
    for row in rows:
        raw_limit = row.get("entry_gross_exposure_limit")
        if raw_limit is None:
            raw_limit = row.get("max_gross_exposure_limit")
        if raw_limit is None:
            continue
        limit = safe_float(raw_limit)
        bucket = buckets.setdefault(limit, {"entry_gross_exposure_limit": limit, "days": 0, "entries": 0})
        bucket["days"] += 1
        bucket["entries"] += int(row.get("entries") or 0)
    return [buckets[key] for key in sorted(buckets)]


def row_for(name: str, path: Path, baseline_summary: dict[str, Any]) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    baseline_return = safe_float(baseline_summary.get("total_return"))
    baseline_drawdown = safe_float(baseline_summary.get("max_drawdown"))
    return {
        "variant": name,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "return_delta_vs_baseline": round(total_return - baseline_return, 6),
        "drawdown_delta_vs_baseline": round(max_drawdown - baseline_drawdown, 6),
        "entry_limit_summary": entry_limit_summary(payload),
    }


def choose_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in rows if row["variant"] != "baseline"]
    improved_drawdown = [row for row in candidates if safe_float(row.get("drawdown_delta_vs_baseline")) > 0]
    improved_return = [row for row in candidates if safe_float(row.get("return_delta_vs_baseline")) > 0]
    best_return = max(candidates, key=lambda row: safe_float(row.get("return_delta_vs_baseline")), default=None)
    if improved_drawdown:
        status = "THROTTLE_FOLLOWUP_CANDIDATE"
        reason = "至少一個 HIGH_CHOPPY 降曝險版本改善回撤，可進下一輪多本金驗證。"
    elif improved_return:
        status = "THROTTLE_MONITOR_ONLY"
        reason = "降曝險版本有報酬改善，但沒有改善回撤；不可當風險控制升級證據。"
    else:
        status = "THROTTLE_REJECTED"
        reason = "降曝險沒有改善報酬或回撤。"
    return {
        "status": status,
        "promotion_ready": False,
        "selected_followup": best_return.get("variant") if best_return else None,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    baseline_path = artifact_path("baseline", args.capital, args.date)
    missing: list[str | None] = []
    if not baseline_path.exists():
        missing.append(repo_path(baseline_path))
        baseline_summary: dict[str, Any] = {}
    else:
        baseline_summary = read_json(baseline_path).get("summary", {})
    rows: list[dict[str, Any]] = []
    for name in VARIANTS:
        path = artifact_path(name, args.capital, args.date)
        if not path.exists():
            missing.append(repo_path(path))
            continue
        rows.append(row_for(name, path, baseline_summary))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if len(rows) == len(VARIANTS) and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "fixed_capital_odd_lot": True,
            "signal_day_regime_controls_next_entry": True,
        },
        "inputs": {
            "capital": args.capital,
            "variant": args.variant,
            "setting": args.setting,
        },
        "decision": choose_decision(rows),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Odd-Lot Regime Throttle",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- selected_followup: {payload['decision'].get('selected_followup')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            "- {variant}: return={total_return}, maxDD={max_drawdown}, "
            "return_delta={return_delta_vs_baseline}, drawdown_delta={drawdown_delta_vs_baseline}, trades={trade_count}".format(**row)
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_regime_throttle_report_{args.date}.json"
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
