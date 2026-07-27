#!/usr/bin/env python3
"""驗證每日研究配額 artifact。

這個 verifier 檢查的是研究配額與安全邊界，不判斷策略應不應上線。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "daily-research-quota-verification.v2"
REPORT_SCHEMA = "autonomous-research-run.v1"
RUNTIME_RECEIPT_SCHEMA = "closed-regime-runtime-receipt.v2"
EXPECTED_QUEUE_OWNER = "fog_worker"
EXPECTED_RUNNER_IDENTITY = "scripts/run_daily_research_quota.sh"
FOLLOWUP_DECISIONS = {"CONFIRMED_FOR_NEXT_REPLAY", "PARTIAL_SCORE_ONLY"}
REJECTION_DECISIONS = {"REJECTED_BY_STRATEGY_MATRIX", "NO_COMPARISON_EVIDENCE"}
SUCCESS_STATES = {"COMPLETED", "PARTIAL_NO_MORE_WORK"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily research quota artifact")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--min-quota", type=int, default=5, help="相容參數；研究單批最多可執行 topic 數")
    parser.add_argument("--closed-regime-runtime-receipt", default=None)
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


def sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def paths_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    left_path = resolve_path(left)
    right_path = resolve_path(right)
    return bool(
        left_path is not None
        and right_path is not None
        and left_path.resolve() == right_path.resolve()
    )


def date_not_after(value: Any, upper_bound: Any) -> bool:
    try:
        return date.fromisoformat(str(value)) <= date.fromisoformat(str(upper_bound))
    except ValueError:
        return False


def topic_run_lineage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "topic_id": str((row.get("topic") or {}).get("topic_id") or ""),
            "status": str(row.get("status") or ""),
            "decision": (row.get("outcome") or {}).get("decision"),
        }
        for row in rows
    ]


def build_payload(
    artifact: Path,
    min_quota: int,
    runtime_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """驗證單批上限，並把可接受的 partial 與實際失敗分開。"""
    payload = read_json(artifact)
    if runtime_receipt_path is None:
        runtime_receipt_path = resolve_path(
            f"artifacts/autonomous_research/closed_regime_runtime_{payload.get('date')}.json"
        )
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
    runtime_receipt = (
        read_json(runtime_receipt_path)
        if runtime_receipt_path is not None and runtime_receipt_path.is_file()
        else {}
    )
    runtime_history = (
        runtime_receipt.get("market_regime_history")
        if isinstance(runtime_receipt.get("market_regime_history"), dict)
        else {}
    )
    artifact_history = str(inputs.get("market_regime_history") or "")
    artifact_history_path = resolve_path(artifact_history)
    runtime_contract = (
        runtime_receipt.get("research_contract")
        if isinstance(runtime_receipt.get("research_contract"), dict)
        else {}
    )
    runtime_contract_path = resolve_path(runtime_contract.get("path"))
    runtime_daily = (
        runtime_receipt.get("daily_research_artifact")
        if isinstance(runtime_receipt.get("daily_research_artifact"), dict)
        else {}
    )
    expected_topic_runs = topic_run_lineage(topic_runs)
    receipt_allowed_keys = {
        "schema_version",
        "status",
        "generated_at",
        "run_date",
        "closed_regime_research",
        "queue_owner",
        "runner_identity",
        "market_regime_history",
        "research_contract",
        "exact_regime",
        "state_transition",
        "daily_research_artifact",
        "topic_runs",
        "topic_runs_sha256",
        "production_impact",
    }
    history_allowed_keys = {"path", "schema_version", "sha256", "source_trade_date"}
    contract_allowed_keys = {"path", "sha256"}
    regime_allowed_keys = {"base_regime", "family_tags", "identity_id"}
    transition_allowed_keys = {"from", "to"}
    daily_allowed_keys = {"path", "schema_version", "sha256", "run_date"}
    receipt_schema_exact = (
        set(runtime_receipt) == receipt_allowed_keys
        and set(runtime_history) == history_allowed_keys
        and set(runtime_contract) == contract_allowed_keys
        and set(
            runtime_receipt.get("exact_regime")
            if isinstance(runtime_receipt.get("exact_regime"), dict)
            else {}
        )
        == regime_allowed_keys
        and set(
            runtime_receipt.get("state_transition")
            if isinstance(runtime_receipt.get("state_transition"), dict)
            else {}
        )
        == transition_allowed_keys
        and set(runtime_daily) == daily_allowed_keys
    )
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
            "name": "closed_regime_contract",
            "ok": contract.get("closed_regime_research") is True
            and inputs.get("closed_regime_research") is True,
            "value": {
                "contract": contract.get("closed_regime_research"),
                "input": inputs.get("closed_regime_research"),
            },
        },
        {
            "name": "runtime_receipt_schema",
            "ok": runtime_receipt.get("schema_version") == RUNTIME_RECEIPT_SCHEMA
            and receipt_schema_exact,
            "value": {
                "schema_version": runtime_receipt.get("schema_version"),
                "unknown_or_missing_top_level": sorted(
                    set(runtime_receipt).symmetric_difference(receipt_allowed_keys)
                ),
            },
        },
        {
            "name": "runtime_receipt_run_date",
            "ok": bool(payload.get("date"))
            and runtime_receipt.get("run_date") == payload.get("date")
            and date_not_after(
                runtime_history.get("source_trade_date"),
                payload.get("date"),
            )
            and runtime_daily.get("run_date") == payload.get("date"),
            "value": {
                "expected": payload.get("date"),
                "receipt": runtime_receipt.get("run_date"),
                "history": runtime_history.get("source_trade_date"),
                "daily_artifact": runtime_daily.get("run_date"),
            },
        },
        {
            "name": "runtime_receipt_identity",
            "ok": runtime_receipt.get("queue_owner") == EXPECTED_QUEUE_OWNER
            and runtime_receipt.get("runner_identity") == EXPECTED_RUNNER_IDENTITY,
            "value": {
                "queue_owner": runtime_receipt.get("queue_owner"),
                "runner_identity": runtime_receipt.get("runner_identity"),
            },
        },
        {
            "name": "runtime_receipt_state_transition",
            "ok": runtime_receipt.get("state_transition")
            == {
                "from": "VERIFIED_HISTORY",
                "to": "CLOSED_RESEARCH_COMPLETED",
            },
            "value": runtime_receipt.get("state_transition"),
        },
        {
            "name": "runtime_receipt_topic_run_lineage",
            "ok": runtime_receipt.get("topic_runs") == expected_topic_runs
            and runtime_receipt.get("topic_runs_sha256")
            == canonical_json_hash(expected_topic_runs)
            and runtime_daily.get("schema_version") == REPORT_SCHEMA
            and paths_match(runtime_daily.get("path"), str(artifact))
            and runtime_daily.get("sha256") == sha256(artifact),
            "value": {
                "expected": expected_topic_runs,
                "receipt": runtime_receipt.get("topic_runs"),
                "daily_artifact": runtime_daily,
            },
        },
        {
            "name": "verified_regime_history_lineage",
            "ok": runtime_receipt.get("status") == "OK"
            and runtime_receipt.get("closed_regime_research") is True
            and paths_match(runtime_history.get("path"), artifact_history)
            and runtime_history.get("schema_version") == "market-regime-history.v2"
            and runtime_history.get("sha256") == sha256(artifact_history_path)
            and paths_match(runtime_contract.get("path"), str(inputs.get("research_contract") or ""))
            and runtime_contract.get("sha256") == sha256(runtime_contract_path)
            and bool((runtime_receipt.get("exact_regime") or {}).get("base_regime"))
            and isinstance((runtime_receipt.get("exact_regime") or {}).get("family_tags"), list)
            and bool((runtime_receipt.get("exact_regime") or {}).get("identity_id"))
            and runtime_receipt.get("production_impact") == "NO_PRODUCTION_CHANGE",
            "value": {
                "receipt": repo_path(runtime_receipt_path),
                "history": runtime_history,
                "exact_regime": runtime_receipt.get("exact_regime"),
                "production_impact": runtime_receipt.get("production_impact"),
            },
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
        "closed_regime_runtime": runtime_receipt,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    runtime_receipt = resolve_path(args.closed_regime_runtime_receipt)
    payload = build_payload(artifact, args.min_quota, runtime_receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "topic_runs": payload["summary"]["topic_runs"]}, ensure_ascii=False))
    return 0 if payload["status"] in SUCCESS_STATES else 1


if __name__ == "__main__":
    raise SystemExit(main())
