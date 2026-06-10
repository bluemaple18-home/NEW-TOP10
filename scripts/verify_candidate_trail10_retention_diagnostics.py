#!/usr/bin/env python3
"""驗證 candidate trail10 retention diagnostics。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "candidate-trail10-retention-diagnostics-verification.v1"
REPORT_SCHEMA = "candidate-trail10-retention-diagnostics.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify candidate trail10 retention diagnostics")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/candidate_trail10_retention_diagnostics_verification_latest.json")
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


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    windows = payload.get("calendar_window_breakdown") if isinstance(payload.get("calendar_window_breakdown"), list) else []
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "diagnostic_only",
            "ok": contract.get("diagnostic_only") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False,
            "value": contract,
        },
        {
            "name": "no_immediate_switch",
            "ok": contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False
            and decision.get("production_switch_ready") is False
            and decision.get("promotion_ready") is False,
            "value": {"contract": contract, "decision": decision},
        },
        {
            "name": "long_supported",
            "ok": n(summary.get("long_return_delta")) > 0 and n(summary.get("long_drawdown_delta")) > 0,
            "value": summary,
        },
        {
            "name": "recent_underperforming_declared",
            "ok": n(summary.get("recent_100_return_delta")) < 0
            and n(summary.get("recent_6m_return_delta")) < 0
            and summary.get("diagnosis") == "long_supported_but_recent_underperforming",
            "value": summary,
        },
        {
            "name": "candidate_retained_not_rejected",
            "ok": decision.get("candidate_trail10") == "RETAIN_FOR_CONDITIONAL_SWITCH_RESEARCH"
            and decision.get("overlap_first") == "REJECTED_AS_REPLACEMENT",
            "value": decision,
        },
        {"name": "calendar_windows_present", "ok": len(windows) >= 5, "value": [row.get("window") for row in windows]},
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
            "diagnosis": summary.get("diagnosis"),
            "operator_decision": summary.get("operator_decision"),
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
