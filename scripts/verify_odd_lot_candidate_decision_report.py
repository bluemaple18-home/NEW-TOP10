#!/usr/bin/env python3
"""驗證零股候選策略主決策報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-candidate-decision-report-verification.v1"
REPORT_SCHEMA = "odd-lot-candidate-decision-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot candidate decision report")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/odd_lot_candidate_decision_report_verification_latest.json")
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
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    source = payload.get("source_decisions") if isinstance(payload.get("source_decisions"), dict) else {}
    spec = payload.get("candidate_spec") if isinstance(payload.get("candidate_spec"), dict) else {}
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
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "decision_promotion_false", "ok": decision.get("promotion_ready") is False, "value": decision},
        {"name": "model_promotion_false", "ok": decision.get("model_promotion_ready") is False, "value": decision},
        {
            "name": "production_change_false",
            "ok": decision.get("production_ranking_change_ready") is False,
            "value": decision,
        },
        {
            "name": "shadow_ready_or_blocked",
            "ok": decision.get("status") in {"READY_FOR_SHADOW_MONITOR", "BLOCKED", "FAILED"},
            "value": decision.get("status"),
        },
        {"name": "exit_source_ok", "ok": source.get("exit_strategy") == "EXIT_STRATEGY_FOLLOWUP_CANDIDATE", "value": source},
        {
            "name": "horizon_source_ok",
            "ok": source.get("horizon_sensitivity") == "HORIZON_40_BALANCED_CANDIDATE",
            "value": source,
        },
        {
            "name": "throttle_source_safe",
            "ok": source.get("regime_throttle") in {"THROTTLE_MONITOR_ONLY", "THROTTLE_REJECTED"},
            "value": source,
        },
        {"name": "candidate_spec_present", "ok": bool(spec.get("ranking_source") and spec.get("runner_exit")), "value": spec},
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
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
            "selected_candidate": decision.get("selected_candidate"),
            "next_stage": decision.get("next_stage"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")
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
