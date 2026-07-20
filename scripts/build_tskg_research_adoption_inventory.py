#!/usr/bin/env python3
"""建立不重跑研究的 TSKG 概念採用清冊。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_research_component_ledger import build_payload as build_component_ledger  # noqa: E402


SCHEMA_VERSION = "tskg-research-adoption-inventory.v1"
_GRANDFATHERED = {"rejected", "off"}
_CHECK_ON_REUSE = {"diagnostic", "reference", "report_only", "production"}
_REQUIRED_NOW = {"shadow", "blocked"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build TSKG research adoption inventory")
    parser.add_argument("--date", required=True)
    parser.add_argument("--input", default=None)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def build_inventory(component_ledger: dict[str, Any], *, as_of: str) -> dict[str, Any]:
    items = [inventory_row(row) for row in component_ledger.get("components", [])]
    items.sort(key=lambda item: item["research_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of,
        "source_schema_version": component_ledger.get("schema_version"),
        "contract": {
            "read_only": True,
            "reruns_research": False,
            "changes_verdict": False,
            "changes_promotion": False,
            "uses_committed_or_injected_inputs_only": True,
        },
        "summary": {
            "item_count": len(items),
            "adoption_class_counts": count_by(items, "adoption_class"),
            "manual_review_count": sum(
                item["next_action"] == "MANUAL_REVIEW" for item in items
            ),
        },
        "items": items,
    }


def inventory_row(component: dict[str, Any]) -> dict[str, Any]:
    lifecycle = str(component.get("lifecycle_status") or "UNKNOWN")
    explicit = component.get("tskg_adoption")
    adoption_class = (
        str(explicit.get("adoption_mode"))
        if isinstance(explicit, dict) and explicit.get("adoption_mode")
        else adoption_class_for_lifecycle(lifecycle)
    )
    checkpoint_decision = (
        explicit.get("decision") if isinstance(explicit, dict) else "NOT_EVALUATED"
    )
    intent = (
        str(explicit.get("usage_intent"))
        if isinstance(explicit, dict) and explicit.get("usage_intent")
        else reuse_intent(component, adoption_class)
    )
    triggers = trigger_reasons(component, adoption_class)
    return {
        "research_id": str(component.get("ledger_id") or "UNKNOWN"),
        "component_family": component.get("component_family"),
        "current_status": lifecycle,
        "artifact_refs": sorted(set(component.get("evidence") or [])),
        "reuse_intent": intent,
        "adoption_class": adoption_class,
        "identity_risk": "NOT_EVALUATED",
        "source_risk": "NOT_EVALUATED",
        "temporal_risk": "NOT_EVALUATED",
        "conflict_risk": "NOT_EVALUATED",
        "promotion_or_model_path": lifecycle in {"shadow", "production"}
        or intent in {"REUSE", "PROMOTION", "MODEL_INPUT", "FORMAL_FACT"},
        "checkpoint_decision": checkpoint_decision,
        "trigger_reasons": triggers,
        "missing_dimensions": ["identity", "source", "temporal", "conflict"],
        "next_action": next_action(adoption_class),
    }


def adoption_class_for_lifecycle(lifecycle: str) -> str:
    if lifecycle in _GRANDFATHERED:
        return "GRANDFATHERED"
    if lifecycle in _CHECK_ON_REUSE:
        return "CHECK_ON_REUSE"
    if lifecycle in _REQUIRED_NOW:
        return "REQUIRED_NOW"
    return "UNKNOWN"


def reuse_intent(component: dict[str, Any], adoption_class: str) -> str:
    lifecycle = str(component.get("lifecycle_status") or "")
    if lifecycle == "production":
        return "REUSE"
    if lifecycle == "shadow" and component.get("component_family") == "runtime_contract":
        return "PROMOTION"
    if adoption_class == "REQUIRED_NOW":
        return "RESEARCH_ONLY"
    return "ARCHIVE_ONLY"


def trigger_reasons(component: dict[str, Any], adoption_class: str) -> list[str]:
    lifecycle = str(component.get("lifecycle_status") or "UNKNOWN")
    reasons = [f"lifecycle:{lifecycle}"]
    if lifecycle in {"shadow", "production"}:
        reasons.append("promotion_or_model_reuse_path")
    if component.get("changes_production_ranking") is True:
        reasons.append("production_ranking_boundary")
    if adoption_class == "UNKNOWN":
        reasons.append("manual_classification_required")
    return sorted(reasons)


def next_action(adoption_class: str) -> str:
    return {
        "GRANDFATHERED": "NO_RERUN",
        "CHECK_ON_REUSE": "VERIFY_AT_REUSE_CHECKPOINT",
        "REQUIRED_NOW": "ADD_EVIDENCE_ENVELOPE_AT_NEXT_CHECKPOINT",
    }.get(adoption_class, "MANUAL_REVIEW")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "UNKNOWN")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def main() -> int:
    args = parse_args()
    if args.input:
        component_ledger = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        component_ledger = build_component_ledger(
            argparse.Namespace(date=args.date, output=None)
        )
    payload = build_inventory(component_ledger, as_of=args.date)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
