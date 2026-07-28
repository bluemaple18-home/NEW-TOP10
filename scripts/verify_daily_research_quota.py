#!/usr/bin/env python3
"""驗證每日研究配額 artifact。

這個 verifier 檢查的是研究配額與安全邊界，不判斷策略應不應上線。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_closed_regime_runtime import verify_receipt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "daily-research-quota-verification.v2"
REPORT_SCHEMA = "autonomous-research-run.v1"
FOLLOWUP_DECISIONS = {"CONFIRMED_FOR_NEXT_REPLAY", "PARTIAL_SCORE_ONLY"}
REJECTION_DECISIONS = {"REJECTED_BY_STRATEGY_MATRIX", "NO_COMPARISON_EVIDENCE"}
SUCCESS_STATES = {"COMPLETED", "PARTIAL_NO_MORE_WORK"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily research quota artifact")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--min-quota", type=int, default=5, help="相容參數；研究單批最多可執行 topic 數")
    parser.add_argument("--output", default="artifacts/autonomous_research/daily_research_quota_verification_latest.json")
    parser.add_argument(
        "--runtime-receipt",
        help="closed-regime runtime receipt v3；提供時由 verifier 自有 clock 重算",
    )
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


def build_payload(
    artifact: Path,
    min_quota: int,
    *,
    runtime_receipt: Path | None = None,
    verification_time_utc: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """驗證單批上限，並把可接受的 partial 與實際失敗分開。"""
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
    decisions = [(run.get("outcome") or {}).get("decision") for run in topic_runs]
    outcome = payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {}
    quota = int(inputs.get("execute_topic_count") or 0)
    queue_empty = inputs.get("from_queue") is True and outcome.get("decision") == "NO_EXECUTABLE_TOPIC" and not topic_runs
    followup_count = sum(1 for decision in decisions if decision in FOLLOWUP_DECISIONS)
    rejection_count = sum(1 for decision in decisions if decision in REJECTION_DECISIONS)
    if queue_empty:
        research_value_status = "QUEUE_EMPTY"
    elif followup_count > 0:
        research_value_status = "HAS_FOLLOWUP_SIGNAL"
    elif topic_runs and rejection_count == len(topic_runs):
        research_value_status = "PURE_REJECTION_EVIDENCE"
    else:
        research_value_status = "LOW_INFORMATION"

    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "execute_true", "ok": inputs.get("execute") is True, "value": inputs.get("execute")},
        {
            "name": "selection_source_declared",
            "ok": inputs.get("from_queue") in {True, False},
            "value": {"from_queue": inputs.get("from_queue")},
        },
        {
            "name": "quota_is_batch_cap",
            "ok": quota > 0 and (min_quota <= 0 or quota <= min_quota),
            "value": {"configured_quota": quota, "max_quota": min_quota},
        },
        {
            "name": "topic_count_within_batch_cap",
            "ok": len(selected_topics) <= quota and len(topic_runs) <= quota,
            "value": {
                "topic_runs": len(topic_runs),
                "selected_topics": len(selected_topics),
                "configured_quota": quota,
            },
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
    runtime_receipt_result: dict[str, Any] | None = None
    if runtime_receipt is not None:
        try:
            receipt_payload = read_json(runtime_receipt)
            runtime_receipt_result = verify_receipt(
                receipt_payload,
                project_root=project_root,
                verification_time_utc=verification_time_utc,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            runtime_receipt_result = {
                "ok": False,
                "reason_codes": ["RECEIPT_AUTHORITY_REJECT"],
                "error": str(error),
            }
        checks.append(
            {
                "name": "runtime_receipt_v3",
                "ok": runtime_receipt_result["ok"],
                "value": runtime_receipt_result,
            }
        )
    failed = [check for check in checks if not check["ok"]]
    runtime_failed = payload.get("status") != "OK" or any(run.get("status") != "OK" for run in topic_runs)
    if runtime_failed:
        state = "FAILED"
    elif failed:
        state = "BLOCKED"
    elif len(topic_runs) >= quota:
        state = "COMPLETED"
    else:
        # quota 是單批上限：queue 沒有更多可執行 topic 時，0/1/3 筆都可正常結束。
        state = "PARTIAL_NO_MORE_WORK"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": state,
        "artifact": repo_path(artifact),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "topic_runs": len(topic_runs),
            "selected_topics": len(selected_topics),
            "requested_quota": min_quota,
            "configured_quota": quota,
            "research_value_status": research_value_status,
            "followup_signal_count": followup_count,
            "rejection_count": rejection_count,
            "include_rejected": inputs.get("include_rejected"),
            "decisions": decisions,
        },
        "checks": checks,
        "runtime_receipt_verification": runtime_receipt_result,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    runtime_receipt = resolve_path(args.runtime_receipt)
    if args.runtime_receipt and (
        runtime_receipt is None or not runtime_receipt.exists()
    ):
        raise FileNotFoundError(f"找不到 runtime receipt：{args.runtime_receipt}")
    payload = build_payload(
        artifact,
        args.min_quota,
        runtime_receipt=runtime_receipt,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "topic_runs": payload["summary"]["topic_runs"]}, ensure_ascii=False))
    return 0 if payload["status"] in SUCCESS_STATES else 1


if __name__ == "__main__":
    raise SystemExit(main())
