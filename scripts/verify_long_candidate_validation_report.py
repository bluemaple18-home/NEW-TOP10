#!/usr/bin/env python3
"""驗證長區間候選策略驗證報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "long-candidate-validation-report-verification.v1"
REPORT_SCHEMA = "long-candidate-validation-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify long candidate validation report")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/long_candidate_validation_report_verification_latest.json")
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


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    capital_rows = payload.get("odd_lot_capital_matrix") if isinstance(payload.get("odd_lot_capital_matrix"), list) else []
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    horizon = payload.get("ranking_day_backtest_by_horizon") if isinstance(payload.get("ranking_day_backtest_by_horizon"), dict) else {}
    exit_matrix = payload.get("exit_rule_matrix_300k") if isinstance(payload.get("exit_rule_matrix_300k"), dict) else {}
    best_exit = (
        exit_matrix.get("best_by_return_drawdown_ratio")
        if isinstance(exit_matrix.get("best_by_return_drawdown_ratio"), dict)
        else {}
    )
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {
            "name": "production_publish_changes_false",
            "ok": contract.get("production_publish_changes") is False,
            "value": contract.get("production_publish_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "comparable_days_sufficient", "ok": int(coverage.get("comparable_days") or 0) >= 500, "value": coverage},
        {"name": "single_day_gap_only", "ok": len(coverage.get("missing_candidate_dates") or []) <= 1, "value": coverage.get("missing_candidate_dates")},
        {"name": "capital_matrix_three_levels", "ok": len(capital_rows) == 3, "value": len(capital_rows)},
        {
            "name": "candidate_beats_return_all_capitals",
            "ok": all(bool(row.get("candidate_return_better")) for row in capital_rows),
            "value": capital_rows,
        },
        {
            "name": "candidate_beats_drawdown_all_capitals",
            "ok": all(bool(row.get("candidate_drawdown_better")) for row in capital_rows),
            "value": capital_rows,
        },
        {
            "name": "candidate_10d_signal_better",
            "ok": float((horizon.get("10") or {}).get("avg_net_return_delta") or 0) > 0,
            "value": horizon.get("10"),
        },
        {
            "name": "candidate_40d_signal_better",
            "ok": float((horizon.get("40") or {}).get("avg_net_return_delta") or 0) > 0,
            "value": horizon.get("40"),
        },
        {
            "name": "no_direct_switch",
            "ok": decision.get("production_switch_ready") is False and decision.get("promotion_ready") is False,
            "value": decision,
        },
        {"name": "exit_matrix_present", "ok": int(exit_matrix.get("variant_count") or 0) >= 10, "value": exit_matrix.get("variant_count")},
        {
            "name": "trail10_selected",
            "ok": decision.get("selected_exit_rule") == "trail10" and best_exit.get("variant") == "trail10",
            "value": {"decision": decision, "best_exit": best_exit},
        },
        {
            "name": "exit_rule_supported",
            "ok": decision.get("exit_rule_supported") is True,
            "value": decision,
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "decision": decision.get("status"),
            "comparable_days": coverage.get("comparable_days"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
