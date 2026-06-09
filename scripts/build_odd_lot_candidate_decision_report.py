#!/usr/bin/env python3
"""彙整零股候選策略的主決策報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-candidate-decision-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot candidate decision report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--exit-strategy-report", default=None)
    parser.add_argument("--horizon-sensitivity-report", default=None)
    parser.add_argument("--regime-throttle-report", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def default_report_path(kind: str, run_date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_{kind}_report_{run_date}.json"


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def build_decision(
    exit_report: dict[str, Any],
    horizon_report: dict[str, Any],
    throttle_report: dict[str, Any],
) -> dict[str, Any]:
    exit_status = safe_get(exit_report, "decision", "status")
    horizon_status = safe_get(horizon_report, "decision", "status")
    throttle_status = safe_get(throttle_report, "decision", "status")
    blockers: list[str] = []
    if exit_status != "EXIT_STRATEGY_FOLLOWUP_CANDIDATE":
        blockers.append(f"exit strategy is {exit_status}")
    if horizon_status != "HORIZON_40_BALANCED_CANDIDATE":
        blockers.append(f"horizon sensitivity is {horizon_status}")
    if throttle_status not in {"THROTTLE_MONITOR_ONLY", "THROTTLE_REJECTED"}:
        blockers.append(f"regime throttle has unresolved status {throttle_status}")
    if blockers:
        status = "BLOCKED"
        next_stage = None
        reason = "候選策略尚未通過出場、持有上限、盤勢降曝險三個研究閘門。"
    else:
        status = "READY_FOR_SHADOW_MONITOR"
        next_stage = "daily_shadow_candidate_replay"
        reason = "出場策略可進 shadow；HIGH_CHOPPY 降曝險不併入主線，只保留監控。"
    return {
        "status": status,
        "selected_candidate": "candidate_top7_gross75_pos12_sl12_ptp25_sell_one_third_runner_40d" if status != "BLOCKED" else None,
        "next_stage": next_stage,
        "promotion_ready": False,
        "model_promotion_ready": False,
        "production_ranking_change_ready": False,
        "blockers": blockers,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    exit_path = resolve_path(args.exit_strategy_report) or default_report_path("exit_strategy", args.date)
    horizon_path = resolve_path(args.horizon_sensitivity_report) or default_report_path("exit_horizon_sensitivity", args.date)
    throttle_path = resolve_path(args.regime_throttle_report) or default_report_path("regime_throttle", args.date)
    missing = [repo_path(path) for path in (exit_path, horizon_path, throttle_path) if not path.exists()]
    exit_report = read_json(exit_path) if exit_path.exists() else {}
    horizon_report = read_json(horizon_path) if horizon_path.exists() else {}
    throttle_report = read_json(throttle_path) if throttle_path.exists() else {}
    decision = build_decision(exit_report, horizon_report, throttle_report) if not missing else {
        "status": "FAILED",
        "selected_candidate": None,
        "next_stage": None,
        "promotion_ready": False,
        "model_promotion_ready": False,
        "production_ranking_change_ready": False,
        "blockers": [f"missing report: {path}" for path in missing],
        "reason": "必要研究報告缺失。",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "shadow_monitor_only": decision.get("status") == "READY_FOR_SHADOW_MONITOR",
        },
        "inputs": {
            "exit_strategy_report": repo_path(exit_path),
            "horizon_sensitivity_report": repo_path(horizon_path),
            "regime_throttle_report": repo_path(throttle_path),
        },
        "source_decisions": {
            "exit_strategy": safe_get(exit_report, "decision", "status"),
            "horizon_sensitivity": safe_get(horizon_report, "decision", "status"),
            "regime_throttle": safe_get(throttle_report, "decision", "status"),
        },
        "candidate_spec": {
            "ranking_source": "all-candidate top7",
            "gross_exposure": 0.75,
            "max_position_weight": 0.12,
            "stop_loss_pct": 0.12,
            "partial_take_profit_pct": 0.25,
            "partial_take_profit_fraction": 1 / 3,
            "runner_exit": "stop_loss_or_40d_horizon",
            "high_choppy_throttle": "monitor_only_not_included",
        },
        "decision": decision,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    decision = payload["decision"]
    lines = [
        "# Odd-Lot Candidate Decision",
        "",
        f"- status: {payload['status']}",
        f"- decision: {decision.get('status')}",
        f"- selected_candidate: {decision.get('selected_candidate')}",
        f"- next_stage: {decision.get('next_stage')}",
        f"- promotion_ready: {decision.get('promotion_ready')}",
        "",
        "## Source Decisions",
        "",
    ]
    for key, value in payload["source_decisions"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidate Spec", ""])
    for key, value in payload["candidate_spec"].items():
        lines.append(f"- {key}: {value}")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_candidate_decision_report_{args.date}.json"
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
