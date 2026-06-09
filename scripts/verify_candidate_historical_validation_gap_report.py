#!/usr/bin/env python3
"""驗證候選策略長區間驗證缺口報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "candidate-historical-validation-gap-report-verification.v1"
REPORT_SCHEMA = "candidate-historical-validation-gap-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證候選策略長區間驗證缺口報告")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/candidate_historical_validation_gap_report_verification_latest.json")
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
    rankings = payload.get("rankings") if isinstance(payload.get("rankings"), dict) else {}
    production = rankings.get("production") if isinstance(rankings.get("production"), dict) else {}
    candidate = rankings.get("candidate") if isinstance(rankings.get("candidate"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    missing_inputs = decision.get("missing_inputs") if isinstance(decision.get("missing_inputs"), list) else []
    missing_candidate_days = int(decision.get("missing_candidate_ranking_days") or rankings.get("missing_candidate_ranking_days") or 0)
    expected_status = "FAILED" if missing_inputs else "OK"
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_matches_required_inputs", "ok": payload.get("status") == expected_status, "value": {"status": payload.get("status"), "missing_inputs": missing_inputs}},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "audit_only", "ok": contract.get("audit_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "production_has_long_window", "ok": int(production.get("date_count") or 0) >= 500, "value": production},
        {"name": "candidate_coverage_reported", "ok": int(candidate.get("date_count") or 0) > 0, "value": candidate},
        {
            "name": "coverage_gap_not_hidden",
            "ok": int(candidate.get("date_count") or 0) < int(production.get("date_count") or 0) or missing_candidate_days > 0,
            "value": {"rankings": rankings, "decision": decision},
        },
        {
            "name": "candidate_date_set_gap_reported",
            "ok": missing_candidate_days > 0,
            "value": decision,
        },
        {
            "name": "blocked_until_long_candidate_rankings",
            "ok": decision.get("status") == "BLOCKED_NEEDS_HISTORICAL_CANDIDATE_RANKINGS",
            "value": decision,
        },
        {"name": "decision_safe", "ok": decision.get("promotion_ready") is False, "value": decision},
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
            "production_days": production.get("date_count"),
            "candidate_days": candidate.get("date_count"),
            "overlap_days": rankings.get("overlap_days"),
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
        raise RuntimeError("output 路徑解析失敗")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
