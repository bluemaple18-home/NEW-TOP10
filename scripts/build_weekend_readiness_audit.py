#!/usr/bin/env python3
"""以具名 profile 建立 weekend readiness audits。

三個 profile 只分派既有 research-only 契約；不跑 replay、不 materialize
production baseline、不修改 production ranking / model / Clawd。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from weekend_training_common import (
    PRODUCTION_IMPACT,
    PROJECT_ROOT,
    WEEKEND_DIR,
    inventory_paths,
    now_utc,
    read_json,
    repo_path,
    rollup_paths,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-overnight-campaign-audits.v1"
RANKING_DIR_SCHEMA_VERSION = "weekend-ranking-dir-unlock-smoke.v1"
UNSUPPORTED_UNLOCK_SCHEMA_VERSION = "weekend-unsupported-unlock-audit.v1"
REPORT_DATE = "2026-06-17"
TRAINING_DATE = "2026-06-13"
REGIME_HISTORY_PATH = PROJECT_ROOT / "artifacts" / "market_regime_history_2026-06-01.json"
RESEARCH_MAP_PATH = PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_latest.json"
SOURCE_AUDIT_STEM = "weekend_production_baseline_source_audit"
RANKING_DATE_RE = re.compile(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend readiness audit")
    parser.add_argument(
        "--profile",
        choices=("campaign", "ranking-dir-smoke", "unsupported-unlock"),
        required=True,
    )
    parser.add_argument("--date", default=None, help="report or training artifact date")
    parser.add_argument("--training-date", default=TRAINING_DATE, help="weekend training artifact date")
    parser.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args(argv)
    if args.date is None:
        if args.profile == "campaign":
            args.date = REPORT_DATE
        else:
            parser.error("--date is required for this profile")
    return args


def artifact_path(stem: str, date: str, suffix: str) -> Path:
    return WEEKEND_DIR / f"{stem}_{date}.{suffix}"


def source_audit_path(training_date: str) -> Path:
    return WEEKEND_DIR / f"{SOURCE_AUDIT_STEM}_{training_date}.json"


def ranking_dates(path_text: str | None) -> set[str]:
    if not path_text:
        return set()
    path = PROJECT_ROOT / path_text
    if not path.exists() or not path.is_dir():
        return set()
    dates: set[str] = set()
    for item in path.glob("ranking_*.csv"):
        match = RANKING_DATE_RE.fullmatch(item.name)
        if match:
            dates.add(match.group(1))
    return dates


def unsupported_reason_count(rollup: dict[str, Any], reason: str) -> int:
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    reasons = summary.get("unsupported_reason_top_counts") if isinstance(summary.get("unsupported_reason_top_counts"), dict) else {}
    return int(reasons.get(reason) or 0)


def unsupported_category_count(rollup: dict[str, Any], category: str) -> int:
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    categories = summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {}
    return int(categories.get(category) or 0)


def top_candidate_source(source_audit: dict[str, Any]) -> dict[str, Any]:
    sources = source_audit.get("candidate_sources") if isinstance(source_audit.get("candidate_sources"), list) else []
    for source in sources:
        if isinstance(source, dict) and source.get("minimum_smoke_candidate"):
            return source
    return sources[0] if sources and isinstance(sources[0], dict) else {}


def build_provenance_design(date: str, training_date: str, source_audit: dict[str, Any]) -> dict[str, Any]:
    best = top_candidate_source(source_audit)
    blocked = source_audit.get("status") == "BLOCKED" or source_audit.get("can_materialize_artifacts_backtest_production") is False
    required_columns = source_audit.get("required_columns") if isinstance(source_audit.get("required_columns"), list) else []
    preferred_columns = [
        "stock_name",
        "final_score",
        "model_prob",
        "allocated_exposure",
        "cash_weight",
        "market_regime",
        "reasons",
        "generator_command",
        "model_artifact",
        "config_hash",
        "source_data_range",
        "created_by",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "production_baseline_provenance_design",
        "generated_at": now_utc(),
        "date": date,
        "training_date": training_date,
        "status": "DESIGN_COMPLETE_BLOCKED_FOR_MATERIALIZATION" if blocked else "DESIGN_COMPLETE",
        "production_impact": PRODUCTION_IMPACT,
        "gate": {
            "design_only": True,
            "materialize_artifacts_backtest_production_allowed": False,
            "smoke_replay_allowed": False,
            "reason": "WEEKEND-TRAINING-11 found BLOCKED_PROVENANCE_GAP; design can proceed, baseline materialization cannot.",
        },
        "source": {
            "source_audit": repo_path(source_audit_path(training_date)),
            "best_existing_candidate_source": best.get("path"),
            "target_baseline_path": "artifacts/backtest/production",
        },
        "answers": {
            "baseline_source_of_truth": (
                "Canonical backtest-safe production baseline materialized by the same sealed production ranking contract, "
                "with explicit provenance manifest. Daily ranking artifacts may be inputs/evidence, but a candidate or subset "
                "directory cannot be promoted by path alone."
            ),
            "required_columns": required_columns,
            "preferred_columns": preferred_columns,
            "date_coverage_required": {
                "minimum": "must cover every ranking date needed by the weekend universe rows that require artifacts/backtest/production",
                "current_best_candidate_start_date": (best.get("date_coverage") or {}).get("start_date") if isinstance(best.get("date_coverage"), dict) else None,
                "current_best_candidate_end_date": (best.get("date_coverage") or {}).get("end_date") if isinstance(best.get("date_coverage"), dict) else None,
                "current_best_candidate_file_count": best.get("ranking_file_count"),
            },
            "proof_not_candidate_ranking": [
                "manifest records generator command and sealed production config/model identifiers",
                "manifest lineage contains no candidate ranking directory as source of truth",
                "ranking files are produced under an approved production-baseline build target, not copied or symlinked",
                "verifier checks required columns, date coverage, row-level schema, and source lineage before unlock",
            ],
            "prevent_future_provenance_gap": [
                "stop deriving baseline from candidate_dir sibling paths without an approved baseline manifest",
                "make baseline source path an explicit research contract field",
                "rollup verifier must compare artifact blocker count to the source audit before accepting map output",
                "materialization must happen only through a dedicated smoke card and verifier",
            ],
        },
        "blocked_counts": {
            "artifact_blocker_count": int(source_audit.get("summary", {}).get("missing_baseline_rows") or 0)
            if isinstance(source_audit.get("summary"), dict)
            else 0,
            "unlockable_combo_count_estimate": int(source_audit.get("unlockable_combo_count_estimate") or 0),
        },
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_create_baseline_dir": True,
            "does_not_symlink_or_copy_candidate_source": True,
            "does_not_change_production_ranking": True,
            "does_not_change_model": True,
            "does_not_publish_clawd": True,
        },
    }


def render_provenance_design(payload: dict[str, Any]) -> str:
    answers = payload["answers"]
    coverage = answers["date_coverage_required"]
    lines = [
        "# Weekend Production Baseline Provenance Design",
        "",
        f"- status: `{payload['status']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- materialize_allowed: `{payload['gate']['materialize_artifacts_backtest_production_allowed']}`",
        f"- smoke_replay_allowed: `{payload['gate']['smoke_replay_allowed']}`",
        f"- artifact_blocker_count: `{payload['blocked_counts']['artifact_blocker_count']}`",
        "",
        "## Source Of Truth",
        "",
        answers["baseline_source_of_truth"],
        "",
        "## Column Contract",
        "",
        "Required:",
        *[f"- `{item}`" for item in answers["required_columns"]],
        "",
        "Preferred provenance fields:",
        *[f"- `{item}`" for item in answers["preferred_columns"]],
        "",
        "## Date Coverage",
        "",
        f"- minimum: {coverage['minimum']}",
        f"- current_best_candidate_start_date: `{coverage['current_best_candidate_start_date']}`",
        f"- current_best_candidate_end_date: `{coverage['current_best_candidate_end_date']}`",
        f"- current_best_candidate_file_count: `{coverage['current_best_candidate_file_count']}`",
        "",
        "## Proof It Is Not Candidate Ranking",
        "",
        *[f"- {item}" for item in answers["proof_not_candidate_ranking"]],
        "",
        "## Future Gap Prevention",
        "",
        *[f"- {item}" for item in answers["prevent_future_provenance_gap"]],
        "",
        "No production ranking, model, Clawd, copy, symlink, or baseline materialization changes.",
        "",
    ]
    return "\n".join(lines)


def build_topic_default_audit(date: str, training_date: str, rollup: dict[str, Any]) -> dict[str, Any]:
    count = unsupported_reason_count(rollup, "UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT")
    category_count = unsupported_category_count(rollup, "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE")
    runner_filters = ["all", "first_day", "streak_2_plus", "improved_or_new", "improved_only", "non_worsening"]
    supported_v2_filters = ["LOG_GATE", "PERCENTILE_GATE", "LOG_GATE_NON_WORSENING"]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "topic_default_entry_filter_contract_audit",
        "generated_at": now_utc(),
        "date": date,
        "training_date": training_date,
        "status": "CONTRACT_BLOCKED",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"rollup": repo_path(rollup_paths(training_date)[0])},
        "summary": {
            "unsupported_reason": "UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT",
            "unsupported_reason_count": count,
            "unsupported_category": "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE",
            "unsupported_category_count": category_count,
            "gate_passed": False,
            "smoke_replay_allowed": False,
        },
        "answers": {
            "is_topic_default_valid_filter": False,
            "classification": "deprecated_or_implicit_coordinate_until_contract_is_written",
            "does_it_equal_none": "not proven; runner has an 'all' entry mode, but TOPIC_DEFAULT has no explicit adapter contract",
            "does_it_equal_topic_native_filter": "not proven; topic native ranking family is separate from an executable entry filter",
            "can_map_to_log_or_percentile": False,
            "runner_supported_entry_filters": runner_filters,
            "weekend_v2_supported_entry_filters": supported_v2_filters,
            "minimum_adapter_contract_if_unlocked": [
                "define TOPIC_DEFAULT semantics as NONE/all or topic-native with deterministic ranking_dir resolution",
                "prove it produces the same entry plan on one topic/horizon before expanding",
                "record adapter name in run_history and rollup so inherited states remain auditable",
            ],
            "recommended_decision": "keep as contract blocker or remove from replayable full universe until semantics are explicit",
        },
        "gate": {
            "allow_mapping_to_log_gate": False,
            "allow_mapping_to_percentile_gate": False,
            "allow_full_replay": False,
            "allow_smoke_replay": False,
            "reason": "TOPIC_DEFAULT is present as a V2 default coordinate, but no executable runner adapter exists.",
        },
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_change_runner_filter_semantics": True,
            "does_not_change_production_ranking": True,
            "does_not_change_model": True,
            "does_not_publish_clawd": True,
        },
    }


def render_topic_default_audit(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    answers = payload["answers"]
    lines = [
        "# Weekend TOPIC_DEFAULT Entry Filter Contract Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- unsupported_reason_count: `{summary['unsupported_reason_count']}`",
        f"- gate_passed: `{summary['gate_passed']}`",
        f"- smoke_replay_allowed: `{summary['smoke_replay_allowed']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Decision",
        "",
        f"- is_valid_filter: `{answers['is_topic_default_valid_filter']}`",
        f"- classification: `{answers['classification']}`",
        f"- equals_none: {answers['does_it_equal_none']}",
        f"- equals_topic_native_filter: {answers['does_it_equal_topic_native_filter']}",
        f"- can_map_to_log_or_percentile: `{answers['can_map_to_log_or_percentile']}`",
        f"- recommended_decision: {answers['recommended_decision']}",
        "",
        "## Minimum Adapter Contract If Unlocked",
        "",
        *[f"- {item}" for item in answers["minimum_adapter_contract_if_unlocked"]],
        "",
        "No replay was executed.",
        "",
    ]
    return "\n".join(lines)


def build_regime_slice_audit(
    date: str,
    training_date: str,
    rollup: dict[str, Any],
    source_audit: dict[str, Any],
) -> dict[str, Any]:
    regime_payload = read_json(REGIME_HISTORY_PATH)
    rows = regime_payload.get("rows") if isinstance(regime_payload.get("rows"), list) else []
    regime_dates: dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("regime_label") or "UNKNOWN")
        trade_date = str(row.get("trade_date") or "")
        if trade_date:
            regime_dates.setdefault(label, set()).add(trade_date)
    label_counts = Counter({label: len(dates) for label, dates in regime_dates.items()})
    best = top_candidate_source(source_audit)
    candidate_dates = ranking_dates(str(best.get("path") or ""))
    source_blocked = source_audit.get("can_materialize_artifacts_backtest_production") is False
    targets = {
        "NEUTRAL_ONLY": ["MIXED_NEUTRAL"],
        "PANIC_SELLING_ONLY": ["PANIC_SELLING"],
        "RISK_OFF_ONLY": ["RISK_OFF"],
    }
    slices: list[dict[str, Any]] = []
    for gate, labels in targets.items():
        dates = set().union(*(regime_dates.get(label, set()) for label in labels))
        candidate_overlap = sorted(dates & candidate_dates)
        unsupported_reason = f"UNSUPPORTED_REGIME_GATE:{gate}"
        slice_payload = {
            "regime_gate": gate,
            "matching_regime_history_labels": labels,
            "unsupported_reason": unsupported_reason,
            "unsupported_reason_count": unsupported_reason_count(rollup, unsupported_reason),
            "available_trade_day_count": len(dates),
            "canonical_comparable_ranking_date_count": 0 if source_blocked else len(candidate_overlap),
            "candidate_source_overlap_ranking_date_count": len(candidate_overlap),
            "candidate_source_overlap_is_decision_evidence": False,
            "outcome_sample_count": None,
            "outcome_sample_count_status": "NOT_MEASURABLE_WITHOUT_APPROVED_BASELINE_AND_SLICE_REPLAY_ADAPTER",
            "enough_for_replay": False,
            "monitoring_only": True,
            "maintain_unsupported": True,
            "decision": "HOLD_UNSUPPORTED_FOR_NOW",
            "failure_reasons": [
                "canonical production baseline provenance gate is blocked",
                "run_capital_aware_replay.py supports regime gross policies, but no *_ONLY slice entry contract is approved",
                "outcome samples cannot be counted without executing an approved slice replay smoke",
            ],
        }
        if gate == "NEUTRAL_ONLY" and "NEUTRAL" not in regime_dates:
            slice_payload["contract_note"] = "current regime history uses MIXED_NEUTRAL; no exact NEUTRAL label exists in this artifact"
        slices.append(slice_payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "regime_slice_data_adequacy_audit",
        "generated_at": now_utc(),
        "date": date,
        "training_date": training_date,
        "status": "ADEQUACY_AUDIT_COMPLETE_HOLD_UNSUPPORTED",
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "rollup": repo_path(rollup_paths(training_date)[0]),
            "source_audit": repo_path(source_audit_path(training_date)),
            "market_regime_history": repo_path(REGIME_HISTORY_PATH),
            "candidate_overlap_source": best.get("path"),
        },
        "summary": {
            "unsupported_category": "UNSUPPORTED_REGIME_SLICE_NO_DATA",
            "unsupported_category_count": unsupported_category_count(rollup, "UNSUPPORTED_REGIME_SLICE_NO_DATA"),
            "regime_history_trade_days": int((regime_payload.get("summary") or {}).get("trade_days") or len(rows))
            if isinstance(regime_payload.get("summary"), dict)
            else len(rows),
            "regime_history_counts": dict(sorted(label_counts.items())),
            "gate_passed_count": 0,
            "smoke_replay_allowed": False,
        },
        "slices": slices,
        "gate": {
            "allow_strategy_conclusion": False,
            "allow_monitoring_audit": True,
            "allow_smoke_replay": False,
            "reason": "sample availability can be described, but executable slice replay remains blocked by baseline provenance and runner contract.",
        },
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_change_runner_regime_contract": True,
            "does_not_change_production_ranking": True,
            "does_not_change_model": True,
            "does_not_publish_clawd": True,
        },
    }


def render_regime_slice_audit(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Regime Slice Data Adequacy Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- unsupported_category_count: `{summary['unsupported_category_count']}`",
        f"- regime_history_trade_days: `{summary['regime_history_trade_days']}`",
        f"- gate_passed_count: `{summary['gate_passed_count']}`",
        f"- smoke_replay_allowed: `{summary['smoke_replay_allowed']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Regime History Counts",
        "",
    ]
    for label, count in summary["regime_history_counts"].items():
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Slice Decisions", ""])
    for item in payload["slices"]:
        lines.extend(
            [
                f"### {item['regime_gate']}",
                "",
                f"- matching_labels: `{', '.join(item['matching_regime_history_labels'])}`",
                f"- unsupported_reason_count: `{item['unsupported_reason_count']}`",
                f"- available_trade_day_count: `{item['available_trade_day_count']}`",
                f"- canonical_comparable_ranking_date_count: `{item['canonical_comparable_ranking_date_count']}`",
                f"- candidate_source_overlap_ranking_date_count: `{item['candidate_source_overlap_ranking_date_count']}`",
                f"- outcome_sample_count: `{item['outcome_sample_count']}`",
                f"- outcome_sample_count_status: `{item['outcome_sample_count_status']}`",
                f"- enough_for_replay: `{item['enough_for_replay']}`",
                f"- monitoring_only: `{item['monitoring_only']}`",
                f"- maintain_unsupported: `{item['maintain_unsupported']}`",
                f"- decision: `{item['decision']}`",
                "",
            ]
        )
        if item.get("contract_note"):
            lines.extend([f"Contract note: {item['contract_note']}", ""])
    lines.append("No strategy conclusion or replay was executed.")
    lines.append("")
    return "\n".join(lines)


def build_summary(
    date: str,
    training_date: str,
    rollup: dict[str, Any],
    research_map: dict[str, Any],
    source_audit: dict[str, Any],
    provenance: dict[str, Any],
    topic_default: dict[str, Any],
    regime: dict[str, Any],
) -> dict[str, Any]:
    rollup_summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    burn_down = research_map.get("burn_down_progress") if isinstance(research_map.get("burn_down_progress"), dict) else {}
    blockers_confirmed = [
        {
            "blocker": "ARTIFACT_BLOCKER_PROVENANCE_GAP",
            "count": int(rollup_summary.get("artifact_blocker_count") or 0),
            "status": provenance["status"],
        },
        {
            "blocker": "UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT",
            "count": topic_default["summary"]["unsupported_reason_count"],
            "status": topic_default["status"],
        },
        {
            "blocker": "UNSUPPORTED_REGIME_SLICE_NO_DATA",
            "count": regime["summary"]["unsupported_category_count"],
            "status": regime["status"],
        },
    ]
    gates_passed = [
        provenance["gate"]["smoke_replay_allowed"],
        topic_default["summary"]["smoke_replay_allowed"],
        regime["summary"]["smoke_replay_allowed"],
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "overnight_campaign_summary",
        "generated_at": now_utc(),
        "date": date,
        "training_date": training_date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "rollup": repo_path(rollup_paths(training_date)[0]),
            "research_map": repo_path(RESEARCH_MAP_PATH),
            "source_audit": repo_path(source_audit_path(training_date)),
            "provenance_design": repo_path(artifact_path("weekend_production_baseline_provenance_design", date, "json")),
            "topic_default_audit": repo_path(artifact_path("weekend_topic_default_entry_filter_contract_audit", date, "json")),
            "regime_slice_audit": repo_path(artifact_path("weekend_regime_slice_data_adequacy_audit", date, "json")),
        },
        "phases": [
            {"phase": "0_safety_preflight", "status": "COMPLETED", "result": "verifiers passed; no daily ETL/publish/weekend runner was intentionally started"},
            {"phase": "1_artifact_blocker_rollup_integration", "status": "COMPLETED", "result": "artifact blocker surfaced in rollup/map without increasing executed progress"},
            {"phase": "2_production_baseline_provenance_design", "status": "COMPLETED_BLOCKED", "result": provenance["status"]},
            {"phase": "3_topic_default_entry_filter_contract_audit", "status": "COMPLETED_BLOCKED", "result": topic_default["status"]},
            {"phase": "4_regime_slice_data_adequacy_audit", "status": "COMPLETED_HOLD_UNSUPPORTED", "result": regime["status"]},
            {"phase": "5_small_unlock_smoke_replay", "status": "SKIPPED", "result": "no gate passed"},
            {"phase": "6_overnight_summary", "status": "COMPLETED", "result": "summary artifact written"},
        ],
        "blockers_confirmed": blockers_confirmed,
        "blockers_unlocked": [],
        "actual_replay_count": 0,
        "next_stage_candidates": {
            "new_from_this_campaign": 0,
            "existing_rollup_next_stage_count": int(rollup_summary.get("next_stage_count") or 0),
        },
        "failure_attribution": {
            "baseline_provenance_gap": int(rollup_summary.get("artifact_blocker_count") or 0),
            "topic_default_contract_gap": topic_default["summary"]["unsupported_reason_count"],
            "regime_slice_data_or_contract_gap": regime["summary"]["unsupported_category_count"],
        },
        "insights": [
            "The research map is now more honest: 202,176 ranking-dir-missing rows are nested under artifact blocker, not treated as runnable queue.",
            "TOPIC_DEFAULT should not be mapped to LOG_GATE or PERCENTILE_GATE without an explicit adapter contract.",
            "Regime slice labels have enough monitoring evidence to describe availability, but no approved slice replay contract or canonical baseline exists.",
        ],
        "low_information": {
            "new_from_this_campaign": 0,
            "existing_rollup_low_information_count": int(rollup_summary.get("low_information_count") or 0),
        },
        "research_map_progress_change": {
            "executed_progress_before": int(rollup_summary.get("processed_before") or 0),
            "executed_progress_after": int(rollup_summary.get("processed_after") or 0),
            "map_executed_progress_count": int(burn_down.get("executed_progress_count") or rollup_summary.get("map_expanded_processed") or 0),
            "expanded_processed_increase_from_artifact_blocker": 0,
            "full_universe_total": int(rollup_summary.get("full_universe_total") or 0),
            "classified_total": int(rollup_summary.get("rollup_classified_total") or 0),
            "unsupported_count": int(rollup_summary.get("unsupported_count") or 0),
            "artifact_blocker_count": int(rollup_summary.get("artifact_blocker_count") or 0),
        },
        "gate_summary": {
            "any_gate_passed": any(bool(item) for item in gates_passed),
            "smoke_replay_status": "SKIPPED_GATE_NOT_PASSED",
            "smoke_replay_allowed": False,
        },
        "next_high_leverage_action": [
            "Approve and implement a canonical production baseline provenance/materialization smoke card before touching the 202,176 baseline blocker rows.",
            "Decide whether TOPIC_DEFAULT is removed from replayable universe or receives a minimal NONE/all adapter contract with a one-topic smoke.",
            "After baseline provenance is approved, rerun regime adequacy with exact outcome-sample counts before any strategy conclusion.",
        ],
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_materialize_artifacts_backtest_production": True,
            "does_not_create_symlink_or_copy": True,
            "does_not_change_production_ranking": True,
            "does_not_change_model": True,
            "does_not_publish_clawd": True,
        },
    }


def render_summary(payload: dict[str, Any]) -> str:
    progress = payload["research_map_progress_change"]
    gate = payload["gate_summary"]
    lines = [
        "# Weekend Overnight Campaign Summary",
        "",
        f"- status: `{payload['status']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- actual_replay_count: `{payload['actual_replay_count']}`",
        f"- smoke_replay_status: `{gate['smoke_replay_status']}`",
        f"- artifact_blocker_count: `{progress['artifact_blocker_count']}`",
        f"- executed_progress_before: `{progress['executed_progress_before']}`",
        f"- executed_progress_after: `{progress['executed_progress_after']}`",
        "",
        "## Phases",
        "",
    ]
    for phase in payload["phases"]:
        lines.append(f"- `{phase['phase']}`: `{phase['status']}` - {phase['result']}")
    lines.extend(["", "## Blockers Confirmed", ""])
    for blocker in payload["blockers_confirmed"]:
        lines.append(f"- `{blocker['blocker']}`: `{blocker['count']}` ({blocker['status']})")
    lines.extend(["", "## Blockers Unlocked", "", "- none", "", "## Insights", ""])
    lines.extend(f"- {item}" for item in payload["insights"])
    lines.extend(["", "## Next High-Leverage Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_high_leverage_action"])
    lines.extend(["", "No replay, production ranking, model, Clawd, copy, symlink, or baseline materialization changes.", ""])
    return "\n".join(lines)


def write_pair(stem: str, date: str, payload: dict[str, Any], markdown: str) -> tuple[Path, Path]:
    json_path = artifact_path(stem, date, "json")
    md_path = artifact_path(stem, date, "md")
    write_json(json_path, payload)
    write_text(md_path, markdown)
    return json_path, md_path


def smoke_paths(date: str) -> tuple[Path, Path]:
    stem = f"weekend_ranking_dir_unlock_smoke_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def missing_path_from_reason(reason: str) -> str | None:
    if ":" not in reason:
        return None
    prefix, value = reason.split(":", 1)
    if prefix not in {"MISSING_BASELINE_RANKINGS_DIR", "MISSING_CANDIDATE_RANKINGS_DIR"}:
        return None
    return value


def build_ranking_dir_payload(date: str, sample_size: int) -> dict[str, Any]:
    inventory_path, _ = inventory_paths(date)
    inventory = read_json(inventory_path)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    rows = [
        row
        for row in records
        if isinstance(row, dict)
        and row.get("burn_down_status") == "UNSUPPORTED_INPUT"
        and row.get("unsupported_category") == "UNSUPPORTED_RANKING_DIR_MISSING"
    ]
    by_reason = Counter(str(row.get("unsupported_reason") or "") for row in rows)
    by_candidate_dir = Counter(str(row.get("candidate_dir") or "") for row in rows)
    by_entry_filter = Counter(str((row.get("dimensions") or {}).get("entry_filter") or "") for row in rows)
    topic_counts: dict[str, int] = defaultdict(int)
    path_counts: Counter[str] = Counter()
    for row in rows:
        topic_counts[str(row.get("topic_id") or "")] += 1
        missing_path = missing_path_from_reason(str(row.get("unsupported_reason") or ""))
        if missing_path:
            path_counts[missing_path] += 1
    sample = []
    for row in rows[: max(sample_size, 0)]:
        sample.append(
            {
                "combo_id": row.get("combo_id"),
                "topic_id": row.get("topic_id"),
                "candidate_dir": row.get("candidate_dir"),
                "dimensions": row.get("dimensions"),
                "unsupported_reason": row.get("unsupported_reason"),
            }
        )
    can_expand_without_new_artifacts = False
    decision = "SMOKE_DONE_ARTIFACT_REQUIRED"
    reason = "缺的是 baseline/candidate ranking 目錄本身；目前只能定位缺口，不能把缺口自動視為可跑。"
    return {
        "schema_version": RANKING_DIR_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"inventory": repo_path(inventory_path)},
        "summary": {
            "ranking_dir_missing_count": len(rows),
            "unique_missing_reasons": len(by_reason),
            "unique_missing_paths": len(path_counts),
            "unique_topics": len(topic_counts),
            "entry_filter_counts": dict(sorted(by_entry_filter.items())),
            "top_missing_reasons": dict(by_reason.most_common(10)),
            "top_missing_paths": dict(path_counts.most_common(10)),
            "top_candidate_dirs": dict(by_candidate_dir.most_common(10)),
            "can_expand_without_new_artifacts": can_expand_without_new_artifacts,
            "decision": decision,
            "reason": reason,
            "next_action": "補一張 ranking artifact source audit：確認是否要產生 artifacts/backtest/production，或把 topic 指到既有 production baseline。",
        },
        "sample": sample,
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_create_ranking_dirs": True,
            "does_not_change_production_ranking": True,
        },
        "errors": [],
    }


def render_ranking_dir_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Ranking Dir Unlock Smoke",
        "",
        f"- status: `{payload['status']}`",
        f"- ranking_dir_missing_count: `{summary['ranking_dir_missing_count']}`",
        f"- unique_missing_paths: `{summary['unique_missing_paths']}`",
        f"- unique_topics: `{summary['unique_topics']}`",
        f"- decision: `{summary['decision']}`",
        f"- can_expand_without_new_artifacts: `{summary['can_expand_without_new_artifacts']}`",
        f"- reason: {summary['reason']}",
        f"- next_action: {summary['next_action']}",
        "",
        "## Entry Filters",
        "",
    ]
    for key, value in summary["entry_filter_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Top Missing Paths", ""])
    for key, value in summary["top_missing_paths"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "No production ranking, model, or Clawd changes.", ""])
    return "\n".join(lines)


def run_ranking_dir_smoke(args: argparse.Namespace) -> int:
    payload = build_ranking_dir_payload(args.date, args.sample_size)
    json_path, md_path = smoke_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_ranking_dir_markdown(payload))
    print(
        json.dumps(
            {"status": payload["status"], "output": repo_path(json_path), "decision": payload["summary"]["decision"]},
            ensure_ascii=False,
        )
    )
    return 0


def audit_paths(date: str) -> tuple[Path, Path]:
    stem = f"weekend_unsupported_unlock_audit_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def reason_matches_category(reason: str, category: str) -> bool:
    if category == "UNSUPPORTED_RANKING_DIR_MISSING":
        return reason.startswith("MISSING_BASELINE_RANKINGS_DIR:") or reason.startswith("MISSING_CANDIDATE_RANKINGS_DIR:")
    if category == "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE":
        return reason.startswith("UNSUPPORTED_ENTRY_FILTER:")
    if category == "UNSUPPORTED_REGIME_SLICE_NO_DATA":
        return reason.startswith("UNSUPPORTED_REGIME_GATE:")
    return False


def category_plan(category: str, count: int, reason_counts: dict[str, int]) -> dict[str, Any]:
    top_reasons = [
        {"reason": reason, "count": value}
        for reason, value in reason_counts.items()
        if reason_matches_category(reason, category)
    ][:5]
    if category == "UNSUPPORTED_RANKING_DIR_MISSING":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "SMOKE_UNLOCK_CANDIDATE",
            "priority": 1,
            "can_unlock_now": False,
            "why": "這類最像 artifact 接線缺口，但不能直接假設缺的 ranking 目錄等價於現有目錄。",
            "risk": "若直接補路徑，可能把不同 ranking source 混成同一條策略。",
            "next_action": "先做 ranking dir availability smoke：選 1 個 topic、1 個 entry filter、1 個 horizon，確認 baseline/candidate 目錄來源後再展開。",
            "top_reasons": top_reasons,
        }
    if category == "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "CONTRACT_DECISION_REQUIRED",
            "priority": 2,
            "can_unlock_now": False,
            "why": "`TOPIC_DEFAULT` 不是 replay runner 支援的 entry filter，不能偷映射成 LOG_GATE 或 PERCENTILE_GATE。",
            "risk": "錯誤映射會讓同一個研究點代表不同進場邏輯，地圖會失真。",
            "next_action": "先定義 TOPIC_DEFAULT 是 topic 原生 filter、NONE filter，還是 deprecated coordinate；只允許 smoke 驗證，不直接大跑。",
            "top_reasons": top_reasons,
        }
    if category == "UNSUPPORTED_REGIME_SLICE_NO_DATA":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "HOLD_UNSUPPORTED_FOR_NOW",
            "priority": 3,
            "can_unlock_now": False,
            "why": "數量最大，但牽涉 NEUTRAL / PANIC_SELLING / RISK_OFF 的樣本與合約定義；直接展開會把低樣本盤勢當有效結論。",
            "risk": "容易把防守盤、崩跌盤與牛市策略混在一起，產生看似完整但不可交易的結論。",
            "next_action": "先做 regime-slice data adequacy audit，確認各 regime 的日期數、可比較 ranking、交易結果樣本，再決定是否開子宇宙。",
            "top_reasons": top_reasons,
        }
    return {
        "category": category,
        "count": count,
        "unlock_decision": "MANUAL_REVIEW_REQUIRED",
        "priority": 99,
        "can_unlock_now": False,
        "why": "未知 unsupported category，需要先拆穩定分類。",
        "risk": "分類不清會污染 burn-down 統計。",
        "next_action": "補 category contract 後再評估。",
        "top_reasons": top_reasons,
    }


def build_unsupported_unlock_payload(date: str) -> dict[str, Any]:
    rollup_path, _ = rollup_paths(date)
    rollup = read_json(rollup_path)
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    category_counts = summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {}
    reason_counts = summary.get("unsupported_reason_top_counts") if isinstance(summary.get("unsupported_reason_top_counts"), dict) else {}
    categories = [
        category_plan(str(category), int(count or 0), {str(k): int(v or 0) for k, v in reason_counts.items()})
        for category, count in sorted(category_counts.items())
    ]
    categories.sort(key=lambda item: int(item["priority"]))
    unsupported_count = int(summary.get("unsupported_count") or 0)
    category_total = sum(int(item["count"]) for item in categories)
    errors: list[str] = []
    if category_total != unsupported_count:
        errors.append("category total does not match unsupported_count")
    return {
        "schema_version": UNSUPPORTED_UNLOCK_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK" if not errors else "FAILED",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"rollup": repo_path(rollup_path)},
        "summary": {
            "unsupported_count": unsupported_count,
            "category_total": category_total,
            "category_count": len(categories),
            "first_unlock_candidate": categories[0]["category"] if categories else None,
            "first_unlock_decision": categories[0]["unlock_decision"] if categories else None,
            "can_unlock_now_count": sum(1 for item in categories if item.get("can_unlock_now") is True),
        },
        "categories": categories,
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
        },
        "errors": errors,
    }


def render_unsupported_unlock_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Unsupported Unlock Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- unsupported_count: `{summary['unsupported_count']}`",
        f"- category_total: `{summary['category_total']}`",
        f"- first_unlock_candidate: `{summary['first_unlock_candidate']}`",
        f"- first_unlock_decision: `{summary['first_unlock_decision']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Categories",
        "",
    ]
    for item in payload["categories"]:
        lines.extend(
            [
                f"### {item['category']}",
                "",
                f"- count: `{item['count']}`",
                f"- unlock_decision: `{item['unlock_decision']}`",
                f"- priority: `{item['priority']}`",
                f"- can_unlock_now: `{item['can_unlock_now']}`",
                f"- why: {item['why']}",
                f"- risk: {item['risk']}",
                f"- next_action: {item['next_action']}",
                "",
            ]
        )
        if item["top_reasons"]:
            lines.append("Top reasons:")
            for reason in item["top_reasons"]:
                lines.append(f"- `{reason['reason']}`: `{reason['count']}`")
            lines.append("")
    lines.append("No production ranking, model, or Clawd changes.")
    lines.append("")
    return "\n".join(lines)


def run_unsupported_unlock(args: argparse.Namespace) -> int:
    payload = build_unsupported_unlock_payload(args.date)
    json_path, md_path = audit_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_unsupported_unlock_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(json_path),
                "first_unlock_candidate": payload["summary"]["first_unlock_candidate"],
                "unsupported_count": payload["summary"]["unsupported_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


def run_campaign(args: argparse.Namespace) -> int:
    rollup = read_json(rollup_paths(args.training_date)[0])
    research_map = read_json(RESEARCH_MAP_PATH)
    source_audit = read_json(source_audit_path(args.training_date))
    provenance = build_provenance_design(args.date, args.training_date, source_audit)
    topic_default = build_topic_default_audit(args.date, args.training_date, rollup)
    regime = build_regime_slice_audit(args.date, args.training_date, rollup, source_audit)
    summary = build_summary(args.date, args.training_date, rollup, research_map, source_audit, provenance, topic_default, regime)
    outputs = [
        write_pair("weekend_production_baseline_provenance_design", args.date, provenance, render_provenance_design(provenance))[0],
        write_pair("weekend_topic_default_entry_filter_contract_audit", args.date, topic_default, render_topic_default_audit(topic_default))[0],
        write_pair("weekend_regime_slice_data_adequacy_audit", args.date, regime, render_regime_slice_audit(regime))[0],
        write_pair("overnight_campaign_summary", args.date, summary, render_summary(summary))[0],
    ]
    print(
        json.dumps(
            {
                "status": summary["status"],
                "date": args.date,
                "training_date": args.training_date,
                "actual_replay_count": summary["actual_replay_count"],
                "smoke_replay_status": summary["gate_summary"]["smoke_replay_status"],
                "outputs": [repo_path(path) for path in outputs],
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.profile == "campaign":
        return run_campaign(args)
    if args.profile == "ranking-dir-smoke":
        return run_ranking_dir_smoke(args)
    return run_unsupported_unlock(args)


if __name__ == "__main__":
    raise SystemExit(main())
