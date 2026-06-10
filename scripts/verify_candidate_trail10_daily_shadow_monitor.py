#!/usr/bin/env python3
"""驗證 candidate trail10 daily shadow monitor artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "candidate-trail10-daily-shadow-monitor-verification.v1"
REPORT_SCHEMA = "candidate-trail10-daily-shadow-monitor.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify candidate trail10 daily shadow monitor")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/candidate_trail10_daily_shadow_monitor_verification_latest.json")
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
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    top10 = payload.get("candidate_top10") if isinstance(payload.get("candidate_top10"), list) else []
    plans = payload.get("trail10_trade_plans") if isinstance(payload.get("trail10_trade_plans"), list) else []
    candidate_ranking = resolve_path(inputs.get("candidate_ranking"))
    production_ranking = resolve_path(inputs.get("production_ranking"))
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "monitor_ready",
            "ok": payload.get("monitor_status") == "READY_FOR_DAILY_SHADOW_MONITOR",
            "value": payload.get("monitor_status"),
        },
        {"name": "shadow_only", "ok": contract.get("operational_shadow_only") is True, "value": contract},
        {
            "name": "no_production_changes",
            "ok": contract.get("changes_production_top10_membership") is False
            and contract.get("changes_risk_adjusted_score") is False
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False,
            "value": contract,
        },
        {
            "name": "no_direct_switch",
            "ok": contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False
            and contract.get("default_allowed") is False,
            "value": contract,
        },
        {"name": "production_ranking_exists", "ok": production_ranking is not None and production_ranking.exists(), "value": repo_path(production_ranking)},
        {"name": "candidate_ranking_exists", "ok": candidate_ranking is not None and candidate_ranking.exists(), "value": repo_path(candidate_ranking)},
        {"name": "candidate_top10_count", "ok": len(top10) == int(inputs.get("top_n") or 10), "value": len(top10)},
        {"name": "actionable_top7_count", "ok": len(plans) == int(inputs.get("actionable_top_n") or 7), "value": len(plans)},
        {
            "name": "trail10_policy",
            "ok": policy.get("trailing_stop_pct") == 0.10
            and policy.get("stop_loss_pct") == 0.12
            and policy.get("min_event_holding_days") == 5
            and policy.get("max_holding_days") == 40,
            "value": policy,
        },
        {
            "name": "plans_have_prices",
            "ok": all(row.get("hard_stop_loss_price") and row.get("initial_trailing_floor") for row in plans),
            "value": plans[:2],
        },
        {
            "name": "summary_consistent",
            "ok": int(summary.get("actionable_count") or 0) == len(plans)
            and int(summary.get("overlap_count") or 0) <= len(top10),
            "value": summary,
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
            "monitor_status": payload.get("monitor_status"),
            "candidate_ranking": repo_path(candidate_ranking),
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
