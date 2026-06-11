#!/usr/bin/env python3
"""驗證每日研究配額 artifact。

這個 verifier 檢查的是研究配額與安全邊界，不判斷策略應不應上線。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "daily-research-quota-verification.v1"
REPORT_SCHEMA = "autonomous-research-run.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily research quota artifact")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--min-quota", type=int, default=5)
    parser.add_argument("--output", default="artifacts/autonomous_research/daily_research_quota_verification_latest.json")
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


def build_payload(artifact: Path, min_quota: int) -> dict[str, Any]:
    payload = read_json(artifact)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    selected_topics = payload.get("selected_topics") if isinstance(payload.get("selected_topics"), list) else []
    topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
    runner_scripts = {
        str(command[1])
        for run in topic_runs
        for step in run.get("steps", [])
        for command in [step.get("command") if isinstance(step.get("command"), list) else []]
        if len(command) > 1
    }
    allowed_scripts = {"scripts/run_backtest_strategy_matrix.py", "scripts/compare_strategy_matrices.py"}

    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "execute_true", "ok": inputs.get("execute") is True, "value": inputs.get("execute")},
        {"name": "from_queue_true", "ok": inputs.get("from_queue") is True, "value": inputs.get("from_queue")},
        {"name": "quota_configured", "ok": int(inputs.get("execute_topic_count") or 0) >= min_quota, "value": inputs.get("execute_topic_count")},
        {
            "name": "selected_topic_count_meets_daily_quota",
            "ok": len(selected_topics) >= min_quota and len(topic_runs) >= min_quota,
            "value": {"topic_runs": len(topic_runs), "selected_topics": len(selected_topics), "min_quota": min_quota},
        },
        {
            "name": "research_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("does_not_train_model") is True
            and contract.get("does_not_write_models_latest_lgbm") is True
            and contract.get("does_not_change_risk_adjusted_score") is True
            and contract.get("does_not_change_production_ranking") is True
            and contract.get("production_promotion_allowed") is False,
            "value": contract,
        },
        {
            "name": "allowlisted_runners_only",
            "ok": runner_scripts.issubset(allowed_scripts),
            "value": sorted(runner_scripts),
        },
        {
            "name": "no_topic_promotes",
            "ok": all((run.get("outcome") or {}).get("promotion_allowed") is False for run in topic_runs),
            "value": [run.get("outcome") for run in topic_runs],
        },
        {
            "name": "all_topic_runs_ok",
            "ok": all(run.get("status") == "OK" for run in topic_runs),
            "value": [{"topic_id": (run.get("topic") or {}).get("topic_id"), "status": run.get("status")} for run in topic_runs],
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "topic_runs": len(topic_runs),
            "selected_topics": len(selected_topics),
            "requested_quota": min_quota,
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
    payload = build_payload(artifact, args.min_quota)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "topic_runs": payload["summary"]["topic_runs"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
