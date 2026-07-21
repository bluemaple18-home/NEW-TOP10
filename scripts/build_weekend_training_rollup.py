#!/usr/bin/env python3
"""建立 weekend training rollup。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from weekend_training_common import (
    MAP_PATH,
    PRODUCTION_IMPACT,
    inventory_paths,
    latest_stage2_path,
    now_utc,
    queue_paths,
    representative_paths,
    repo_path,
    resolve_path,
    rollup_paths,
    survivor_paths,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-training-rollup.v1"
ARTIFACT_BLOCKER_CATEGORY = "ARTIFACT_BLOCKER_PROVENANCE_GAP"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend training rollup")
    parser.add_argument("--date", required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def top_counts(values: list[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"reason": key, "count": count} for key, count in Counter(values).most_common(limit)]


def production_baseline_source_audit_path(date: str) -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "weekend_training" / f"weekend_production_baseline_source_audit_{date}.json"


def controlled_grid_drain_path(date: str) -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "weekend_training" / f"controlled_grid_drain_gates_{date}.json"


def unattended_run_path(date: str) -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "weekend_training" / f"weekend_unattended_run_{date}.json"


def host_runner_status_path(date: str) -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "host_runner" / date / f"controlled_grid_drain_host_runner_status_{date}.json"


def controlled_grid_drain_summary(date: str) -> dict[str, Any]:
    path = controlled_grid_drain_path(date)
    payload = read_json(path)
    if payload.get("runner_mode") == "linkage_only":
        gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
        queue = gates.get("queue_contract") if isinstance(gates.get("queue_contract"), dict) else {}
        inventory_summary = queue.get("inventory_summary") if isinstance(queue.get("inventory_summary"), dict) else {}
        queue_summary = queue.get("queue_summary") if isinstance(queue.get("queue_summary"), dict) else {}
        micro = gates.get("micro_batch") if isinstance(gates.get("micro_batch"), dict) else {}
        resume = gates.get("unattended_resume") if isinstance(gates.get("unattended_resume"), dict) else {}
        return {
            "source": repo_path(path),
            "status": payload.get("status"),
            "controlled_grid_drain_ready": payload.get("controlled_grid_drain_ready"),
            "baseline_alias": payload.get("baseline_alias"),
            "baseline_blocker_cleared": inventory_summary.get("baseline_blocker_cleared"),
            "no_replay_required_after_alias": inventory_summary.get("no_replay_required_after_alias"),
            "representative_replay_count": queue_summary.get("representative_replay_count"),
            "micro_batch_status": micro.get("status"),
            "unattended_resume_status": resume.get("status"),
            "target_production_path_created": payload.get("target_production_path_created"),
            "production_impact": payload.get("production_impact"),
        }

    unattended_path = unattended_run_path(date)
    unattended = read_json(unattended_path)
    if unattended:
        summary = unattended.get("summary") if isinstance(unattended.get("summary"), dict) else {}
        queue_summary = summary.get("queue") if isinstance(summary.get("queue"), dict) else {}
        latest = summary.get("latest_representative") if isinstance(summary.get("latest_representative"), dict) else {}
        rollup = summary.get("rollup") if isinstance(summary.get("rollup"), dict) else {}
        host = read_json(host_runner_status_path(date))
        status = unattended.get("status")
        return {
            "source": repo_path(unattended_path),
            "host_runner": repo_path(host_runner_status_path(date)) if host_runner_status_path(date).exists() else None,
            "status": status,
            "controlled_grid_drain_ready": status in {"RUNNING", "OK"},
            "baseline_alias": host.get("baseline_alias") or "artifacts/backtest/production_baseline_harness_medium_window",
            "baseline_blocker_cleared": rollup.get("baseline_blocker_cleared") is not False,
            "no_replay_required_after_alias": False,
            "representative_replay_count": queue_summary.get("representative_replay_count"),
            "micro_batch_status": "OK" if int(latest.get("completed_count") or 0) > 0 else None,
            "unattended_resume_status": status,
            "batch_completed_count": summary.get("batch_completed_count"),
            "target_production_path_created": False,
            "production_impact": unattended.get("production_impact") or PRODUCTION_IMPACT,
        }

    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    queue = gates.get("queue_contract") if isinstance(gates.get("queue_contract"), dict) else {}
    inventory_summary = queue.get("inventory_summary") if isinstance(queue.get("inventory_summary"), dict) else {}
    queue_summary = queue.get("queue_summary") if isinstance(queue.get("queue_summary"), dict) else {}
    micro = gates.get("micro_batch") if isinstance(gates.get("micro_batch"), dict) else {}
    resume = gates.get("unattended_resume") if isinstance(gates.get("unattended_resume"), dict) else {}
    return {
        "source": repo_path(path) if path.exists() else None,
        "status": payload.get("status"),
        "controlled_grid_drain_ready": payload.get("controlled_grid_drain_ready"),
        "baseline_alias": payload.get("baseline_alias"),
        "baseline_blocker_cleared": inventory_summary.get("baseline_blocker_cleared"),
        "no_replay_required_after_alias": inventory_summary.get("no_replay_required_after_alias"),
        "representative_replay_count": queue_summary.get("representative_replay_count"),
        "micro_batch_status": micro.get("status"),
        "unattended_resume_status": resume.get("status"),
        "target_production_path_created": payload.get("target_production_path_created"),
        "production_impact": payload.get("production_impact"),
    }


def artifact_blocker_summary(date: str, unsupported_reason_top_counts: dict[str, Any]) -> dict[str, Any]:
    controlled = controlled_grid_drain_summary(date)
    if controlled.get("status") in {"RUNNING", "OK"} and controlled.get("baseline_blocker_cleared") is True:
        return {
            "artifact_blocker_count": 0,
            "artifact_blocker_category_counts": {},
            "artifact_blocker_reason_top_counts": {},
            "artifact_blocker_source": controlled.get("source"),
            "artifact_blocker_source_status": "CLEARED_BY_BASELINE_HARNESS_ALIAS",
        }
    audit_path = production_baseline_source_audit_path(date)
    audit = read_json(audit_path)
    if audit.get("status") != "BLOCKED" or audit.get("can_materialize_artifacts_backtest_production") is not False:
        return {
            "artifact_blocker_count": 0,
            "artifact_blocker_category_counts": {},
            "artifact_blocker_reason_top_counts": {},
            "artifact_blocker_source": repo_path(audit_path) if audit_path.exists() else None,
            "artifact_blocker_source_status": audit.get("status"),
        }
    count = int((audit.get("summary") or {}).get("missing_baseline_rows") or 0)
    reason = "MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production"
    reason_count = int(unsupported_reason_top_counts.get(reason) or count)
    return {
        "artifact_blocker_count": count,
        "artifact_blocker_category_counts": {ARTIFACT_BLOCKER_CATEGORY: count} if count else {},
        "artifact_blocker_reason_top_counts": {reason: reason_count} if count else {},
        "artifact_blocker_source": repo_path(audit_path),
        "artifact_blocker_source_status": audit.get("baseline_source_status") or audit.get("status"),
    }


def pending_equivalence_inherited_count(
    queue_counts: dict[str, Any],
    burn_counts: dict[str, Any],
    *,
    processed_before: int,
    materialization_mode: str | None,
) -> int:
    if materialization_mode == "BOUNDED_REPRESENTATIVES":
        return int(burn_counts.get("EQUIVALENCE_INHERITED", 0) or 0)
    if queue_counts:
        return max(0, int(queue_counts.get("EQUIVALENCE_INHERIT", 0) or 0) - processed_before)
    return int(burn_counts.get("EQUIVALENCE_INHERITED", 0) or 0)


def build_payload(date: str) -> dict[str, Any]:
    inventory_path, _ = inventory_paths(date)
    queue_path, _ = queue_paths(date)
    representative_path, _ = representative_paths(date)
    survivor_path, _ = survivor_paths(date)
    inventory = read_json(inventory_path)
    queue = read_json(queue_path)
    representative = read_json(representative_path)
    survivor = read_json(survivor_path)
    map_payload = read_json(MAP_PATH)
    inv_summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    queue_summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
    queue_contract = queue.get("contract") if isinstance(queue.get("contract"), dict) else {}
    queue_counts = queue_summary.get("queue_type_counts") if isinstance(queue_summary.get("queue_type_counts"), dict) else {}
    current_counts = inv_summary.get("current_status_counts") if isinstance(inv_summary.get("current_status_counts"), dict) else {}
    burn_counts = inv_summary.get("burn_down_status_counts") if isinstance(inv_summary.get("burn_down_status_counts"), dict) else {}
    unsupported_category_counts = inv_summary.get("unsupported_category_counts") if isinstance(inv_summary.get("unsupported_category_counts"), dict) else {}
    unsupported_reason_top_counts = inv_summary.get("unsupported_reason_top_counts") if isinstance(inv_summary.get("unsupported_reason_top_counts"), dict) else {}
    rep_rows = representative.get("rows") if isinstance(representative.get("rows"), list) else []
    survivor_rows = survivor.get("rows") if isinstance(survivor.get("rows"), list) else []
    rep_decisions = Counter(str(row.get("decision") or "") for row in rep_rows)
    processed_before = int(inv_summary.get("current_processed_count") or 0)
    full_total = int(inv_summary.get("full_universe_total") or 0)
    map_processed = int((map_payload.get("summary") or {}).get("expanded_processed") or processed_before)
    failure_reasons = [
        str(reason)
        for row in [*rep_rows, *survivor_rows]
        for reason in (row.get("failure_reasons") or [])
        if reason
    ]
    top_survivors = [
        {
            "combo_id": row.get("combo_id"),
            "decision": row.get("decision"),
            "return_delta": row.get("return_delta"),
            "drawdown_delta": row.get("drawdown_delta"),
            "failure_reasons": row.get("failure_reasons"),
        }
        for row in survivor_rows
        if row.get("decision") in {"KEEP_FOR_NEXT_RESEARCH", "MONITOR_ONLY"}
    ][:20]
    next_week_queue = [
        {
            "combo_id": row.get("combo_id"),
            "reason": "long_window_or_regime_slice_needed",
            "source_decision": row.get("decision"),
        }
        for row in survivor_rows
        if row.get("decision") == "MONITOR_ONLY"
    ][:20]
    pending_equivalence_inherited = pending_equivalence_inherited_count(
        queue_counts,
        burn_counts,
        processed_before=processed_before,
        materialization_mode=queue_contract.get("materialization_mode"),
    )
    active_representative_queue = int(queue_counts.get("REPRESENTATIVE_REPLAY", 0) or 0)
    representative_pending = int(inv_summary.get("representative_required_count") or 0)
    deferred_low_priority = max(0, representative_pending - active_representative_queue)
    rollup_counts = {
        "executed_replay_count": int(current_counts.get("EXECUTED_REPLAY", 0)),
        "equivalence_inherited_count": pending_equivalence_inherited,
        "rule_pruned_count": int(queue_counts.get("RULE_PRUNE", burn_counts.get("RULE_PRUNED", 0)) or 0),
        "unsupported_count": int(queue_counts.get("UNSUPPORTED", burn_counts.get("UNSUPPORTED_INPUT", 0)) or 0),
        "low_information_count": int(current_counts.get("LOW_INFORMATION", 0)),
        "next_stage_count": int(current_counts.get("NEXT_STAGE_CANDIDATE", 0)),
        "rejected_count": int(current_counts.get("REJECTED", 0)),
        "representative_replay_pending_count": representative_pending,
    }
    blockers = artifact_blocker_summary(date, unsupported_reason_top_counts)
    controlled_grid_drain = controlled_grid_drain_summary(date)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "inventory": repo_path(inventory_path),
            "queue": repo_path(queue_path),
            "representative_replay": repo_path(representative_path),
            "survivor_deep_replay": repo_path(survivor_path),
            "stage2": repo_path(latest_stage2_path(date)),
            "research_map": repo_path(MAP_PATH),
        },
        "summary": {
            "full_universe_total": full_total,
            "processed_before": processed_before,
            "processed_after": min(full_total, max(processed_before, map_processed)),
            "map_expanded_processed": map_processed,
            "queue_count": queue_summary.get("queue_count"),
            "active_representative_queue_count": active_representative_queue,
            "deferred_low_priority_count": deferred_low_priority,
            "latest_representative_batch_decision_counts": dict(sorted(rep_decisions.items())),
            **rollup_counts,
            "rollup_classified_total": sum(rollup_counts.values()),
            "unsupported_category_counts": unsupported_category_counts,
            "unsupported_reason_top_counts": unsupported_reason_top_counts,
            **blockers,
            "unsupported_unblockable_count": inv_summary.get("unsupported_unblockable_count"),
            "unsupported_non_unblockable_count": inv_summary.get("unsupported_non_unblockable_count"),
            "browser_qa": "NOT_RUN",
            "controlled_grid_drain_ready": controlled_grid_drain.get("controlled_grid_drain_ready"),
            "baseline_blocker_cleared": controlled_grid_drain.get("baseline_blocker_cleared"),
            "controlled_grid_drain_status": controlled_grid_drain.get("status"),
        },
        "controlled_grid_drain": controlled_grid_drain,
        "top_survivors": top_survivors,
        "top_failure_reasons": top_counts(failure_reasons),
        "next_week_research_queue": next_week_queue,
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_push_clawd": True,
            "no_promotion_ready": True,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Training Rollup",
        "",
        f"- full_universe_total: `{summary['full_universe_total']}`",
        f"- processed_before: `{summary['processed_before']}`",
        f"- processed_after: `{summary['processed_after']}`",
        f"- executed_replay_count: `{summary['executed_replay_count']}`",
        f"- equivalence_inherited_count: `{summary['equivalence_inherited_count']}`",
        f"- rule_pruned_count: `{summary['rule_pruned_count']}`",
        f"- unsupported_count: `{summary['unsupported_count']}`",
        f"- artifact_blocker_count: `{summary.get('artifact_blocker_count', 0)}`",
        f"- controlled_grid_drain_status: `{summary.get('controlled_grid_drain_status')}`",
        f"- baseline_blocker_cleared: `{summary.get('baseline_blocker_cleared')}`",
        f"- representative_replay_pending_count: `{summary['representative_replay_pending_count']}`",
        f"- active_representative_queue_count: `{summary['active_representative_queue_count']}`",
        f"- deferred_low_priority_count: `{summary['deferred_low_priority_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- browser_qa: `{summary['browser_qa']}`",
        "",
        "## Top Failure Reasons",
        "",
    ]
    for row in payload["top_failure_reasons"]:
        lines.append(f"- `{row['reason']}`: `{row['count']}`")
    lines.extend(["", "## Unsupported Category Counts", ""])
    for key, value in summary.get("unsupported_category_counts", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Artifact Blocker Counts", ""])
    for key, value in summary.get("artifact_blocker_category_counts", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Week Research Queue", ""])
    for row in payload["next_week_research_queue"][:20]:
        lines.append(f"- `{row['combo_id']}` / `{row['reason']}`")
    lines.extend(["", "No production ranking, model, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date)
    json_path, md_path = rollup_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "processed_after": payload["summary"]["processed_after"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
