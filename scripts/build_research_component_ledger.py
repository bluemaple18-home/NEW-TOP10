#!/usr/bin/env python3
"""建立研究元件治理 ledger。

這份 ledger 把現有 research artifact registry 與 runtime strategy registry
整理到同一張 runtime contract 表。它只做治理盤點，不升級任何元件到正式策略。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_strategy_component_registry import build_payload as build_strategy_registry_payload  # noqa: E402
from app.research.tskg_evidence_contract import (  # noqa: E402
    build_evidence_envelope,
    compact_adoption_summary,
)


SCHEMA_VERSION = "research-component-ledger.v1"

RESEARCH_STATUS_TO_LIFECYCLE = {
    "REUSABLE_CANDIDATE": "shadow",
    "CONDITIONAL_CANDIDATE": "shadow",
    "DIAGNOSTIC_ONLY": "diagnostic",
    "REJECTED": "rejected",
    "DATA_UNAVAILABLE": "blocked",
    "REFERENCE_AVAILABLE": "reference",
    "MESSAGE_AVAILABLE": "report_only",
    "NEEDS_TEST": "blocked",
}

DEFAULT_VERIFICATION_COMMANDS = {
    "research_registry": [
        "uv run scripts/verify_strategy_component_registry.py --artifact artifacts/model_experiments/strategy_component_registry_{date}.json",
    ],
    "runtime_contract": [
        "uv run scripts/verify_strategy_component_registry.py --artifact artifacts/model_experiments/strategy_component_registry_{date}.json",
    ],
}

EXTRA_VERIFICATION_COMMANDS = {
    "vwap_regime_gated_entry": [
        "uv run scripts/verify_vwap_cost_basis_features.py",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build research component ledger")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default=None)
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


def format_commands(commands: list[str], run_date: str) -> list[str]:
    return [command.format(date=run_date) for command in commands]


def lifecycle_for_research_status(status: str) -> str:
    return RESEARCH_STATUS_TO_LIFECYCLE.get(status, "blocked")


def research_row(row: dict[str, Any], run_date: str) -> dict[str, Any]:
    component_id = str(row["component_id"])
    status = str(row.get("status", "NEEDS_TEST"))
    verification_commands = format_commands(DEFAULT_VERIFICATION_COMMANDS["research_registry"], run_date)
    verification_commands.extend(EXTRA_VERIFICATION_COMMANDS.get(component_id, []))
    ledger_id = f"research:{component_id}"
    return {
        "ledger_id": ledger_id,
        "component_family": "research_registry",
        "component_id": component_id,
        "category": row.get("category"),
        "source_status": status,
        "lifecycle_status": lifecycle_for_research_status(status),
        "effect_type": "research_reference",
        "description": row.get("description", ""),
        "evidence": list(row.get("evidence", [])),
        "verification_commands": verification_commands,
        "where_it_helps": list(row.get("where_it_helps", [])),
        "where_it_hurts": list(row.get("where_it_hurts", [])),
        "allowed_next_use": list(row.get("allowed_next_use", [])),
        "blocked_uses": list(row.get("blocked_uses", [])),
        "promotion_gates": [],
        "changes_production_ranking": False,
        "production_baseline": False,
        "promotion_ready": False,
        "next_action": next_action_for_research(status),
        "tskg_adoption": tskg_adoption_summary(
            ledger_id=ledger_id,
            component_family="research_registry",
            lifecycle_status=lifecycle_for_research_status(status),
        ),
    }


def runtime_row(row: dict[str, Any], run_date: str) -> dict[str, Any]:
    component_id = str(row["component_id"])
    verification_commands = format_commands(DEFAULT_VERIFICATION_COMMANDS["runtime_contract"], run_date)
    verification_commands.extend(EXTRA_VERIFICATION_COMMANDS.get(component_id, []))
    runtime_status = str(row.get("runtime_status", "off"))
    ledger_id = f"runtime:{component_id}"
    return {
        "ledger_id": ledger_id,
        "component_family": "runtime_contract",
        "component_id": component_id,
        "label": row.get("label", ""),
        "category": row.get("category"),
        "source_status": runtime_status,
        "lifecycle_status": runtime_status,
        "effect_type": row.get("effect_type"),
        "description": row.get("description", ""),
        "evidence": list(row.get("evidence", [])),
        "verification_commands": verification_commands,
        "applies_to_regimes": list(row.get("applies_to_regimes", [])),
        "blocked_regimes": list(row.get("blocked_regimes", [])),
        "input_columns": list(row.get("input_columns", [])),
        "output_columns": list(row.get("output_columns", [])),
        "allowed_next_use": [],
        "blocked_uses": list(row.get("blocked_uses", [])),
        "promotion_gates": list(row.get("promotion_gates", [])),
        "changes_production_ranking": bool(row.get("can_change_production_ranking")),
        "production_baseline": runtime_status == "production",
        "promotion_ready": False,
        "next_action": next_action_for_runtime(runtime_status),
        "tskg_adoption": tskg_adoption_summary(
            ledger_id=ledger_id,
            component_family="runtime_contract",
            lifecycle_status=runtime_status,
        ),
    }


def tskg_adoption_summary(
    *, ledger_id: str, component_family: str, lifecycle_status: str
) -> dict[str, Any]:
    if lifecycle_status in {"rejected", "off"}:
        mode, intent = "GRANDFATHERED", "ARCHIVE_ONLY"
    elif lifecycle_status == "shadow":
        mode = "REQUIRED_NOW"
        intent = "PROMOTION" if component_family == "runtime_contract" else "RESEARCH_ONLY"
    elif lifecycle_status == "blocked":
        mode, intent = "REQUIRED_NOW", "RESEARCH_ONLY"
    elif lifecycle_status == "production":
        mode, intent = "CHECK_ON_REUSE", "REUSE"
    else:
        mode, intent = "CHECK_ON_REUSE", "ARCHIVE_ONLY"
    envelope = build_evidence_envelope(
        research_id=ledger_id,
        usage_intent=intent,
        adoption_mode=mode,
    )
    return compact_adoption_summary(envelope)


def next_action_for_research(status: str) -> str:
    if status in {"REUSABLE_CANDIDATE", "CONDITIONAL_CANDIDATE"}:
        return "keep_shadow_and_collect_regime_replay"
    if status == "DIAGNOSTIC_ONLY":
        return "keep_diagnostic_until_effectiveness_replay"
    if status in {"DATA_UNAVAILABLE", "NEEDS_TEST"}:
        return "fix_data_or_test_contract_before_any_promotion"
    if status == "REJECTED":
        return "archive_as_negative_evidence"
    if status in {"REFERENCE_AVAILABLE", "MESSAGE_AVAILABLE"}:
        return "use_for_context_only_until_alpha_replay_exists"
    return "manual_review_required"


def next_action_for_runtime(runtime_status: str) -> str:
    if runtime_status == "production":
        return "monitor_existing_baseline_and_keep_rollback_gate"
    if runtime_status == "shadow":
        return "collect_shadow_replay_before_promotion"
    if runtime_status == "report_only":
        return "keep_explanation_layer_and_verify_message_accuracy"
    return "keep_disabled_until_data_and_replay_gate_pass"


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "UNKNOWN"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    strategy_payload = build_strategy_registry_payload(argparse.Namespace(date=args.date, output=None))
    research_rows = [research_row(row, args.date) for row in strategy_payload["components"]]
    runtime_rows = [
        runtime_row(row, args.date)
        for row in strategy_payload["runtime_registry"]["components"]
    ]
    components = research_rows + runtime_rows
    production_mutators = [
        row["ledger_id"]
        for row in components
        if row["changes_production_ranking"] is True
    ]
    blocked_or_rejected = [
        row["ledger_id"]
        for row in components
        if row["lifecycle_status"] in {"blocked", "rejected", "off"}
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "ledger_only": True,
            "uses_existing_artifacts_only": True,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
            "runtime_router_available": True,
        },
        "source_registry": {
            "schema_version": strategy_payload["schema_version"],
            "component_count": strategy_payload["summary"]["component_count"],
            "runtime_component_count": strategy_payload["runtime_registry"]["component_count"],
        },
        "summary": {
            "component_count": len(components),
            "family_counts": count_by(components, "component_family"),
            "lifecycle_counts": count_by(components, "lifecycle_status"),
            "category_counts": count_by(components, "category"),
            "production_mutator_count": len(production_mutators),
            "blocked_or_rejected_count": len(blocked_or_rejected),
            "next_mainline": "regime_conditioned_shadow_replay_before_promotion",
        },
        "components": components,
        "route_preview": strategy_payload["route_preview"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Component Ledger",
        "",
        f"- status: `{payload['status']}`",
        f"- component_count: `{payload['summary']['component_count']}`",
        f"- production_mutator_count: `{payload['summary']['production_mutator_count']}`",
        f"- next_mainline: `{payload['summary']['next_mainline']}`",
        "",
        "| Ledger ID | Family | Category | Lifecycle | Production Impact | Next Action |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["components"]:
        impact = "yes" if row["changes_production_ranking"] else "no"
        lines.append(
            "| {ledger_id} | {family} | {category} | {lifecycle} | {impact} | {next_action} |".format(
                ledger_id=row["ledger_id"],
                family=row["component_family"],
                category=row["category"],
                lifecycle=row["lifecycle_status"],
                impact=impact,
                next_action=row["next_action"],
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 這份 ledger 只整理研究元件狀態，不改正式 ranking。",
            "- shadow / report_only / diagnostic / reference 元件不可影響正式排序。",
            "- blocked / rejected / off 元件不可被標成 promotion ready。",
            "- production mutator 只能是既有 baseline，且必須保留 evidence 與 promotion gate。",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"research_component_ledger_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "component_count": payload["summary"]["component_count"],
                "lifecycle_counts": payload["summary"]["lifecycle_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
