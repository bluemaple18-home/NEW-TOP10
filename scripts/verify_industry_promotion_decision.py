#!/usr/bin/env python3
"""驗證產業 overlay promotion 決策為指標推導，而非人工改寫。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISION = (
    PROJECT_ROOT
    / "docs"
    / "evidence"
    / "INDUSTRY-PROMOTION-20260722"
    / "decision.json"
)
TOP_LEVEL_FIELDS = {
    "schema_version", "candidate", "evaluated_at", "input", "sample",
    "method", "metrics", "gate", "decision", "production_action",
}


class IndustryPromotionDecisionError(ValueError):
    """產業 promotion evidence 違反 fail-closed contract。"""


def validate_decision(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL_FIELDS:
        raise IndustryPromotionDecisionError("decision top-level shape mismatch")
    if payload["schema_version"] != "industry-promotion-decision-v1":
        raise IndustryPromotionDecisionError("unsupported schema_version")
    metrics = payload["metrics"]
    gate = payload["gate"]
    method = payload["method"]
    sample = payload["sample"]
    if not isinstance(metrics, Mapping) or not isinstance(gate, Mapping):
        raise IndustryPromotionDecisionError("metrics and gate must be objects")
    numeric_values = [*metrics.values(), *gate.values()]
    if any(type(value) not in {int, float} for value in numeric_values):
        raise IndustryPromotionDecisionError("metrics and gate must be numeric")
    if method.get("self_leakage_control") != "leave-one-out/ex-self":
        raise IndustryPromotionDecisionError("self leakage control is missing")
    if method.get("same_universe_dates_cost") is not True:
        raise IndustryPromotionDecisionError("comparison is not aligned")
    if method.get("production_score_mutated") is not False:
        raise IndustryPromotionDecisionError("shadow evidence mutated production")
    if sample.get("trade_days", 0) < 250 or sample.get("stocks", 0) < 1000:
        raise IndustryPromotionDecisionError("sample is below the acceptance floor")

    concentration_delta = (
        metrics["shadow_top_industry_concentration"]
        - metrics["production_top_industry_concentration"]
    )
    qualifies = (
        metrics["return_uplift"] > gate["minimum_return_uplift"]
        and metrics["hit_rate_uplift"] >= gate["minimum_hit_rate_uplift"]
        and concentration_delta <= gate["maximum_concentration_increase"]
    )
    expected = "GO" if qualifies else "REJECT"
    if payload["decision"] != expected:
        raise IndustryPromotionDecisionError(
            f"decision mismatch: expected {expected}"
        )
    expected_action = (
        "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
        if qualifies
        else "NO_RANKING_OR_WEIGHT_CHANGE"
    )
    if payload["production_action"] != expected_action:
        raise IndustryPromotionDecisionError("production action mismatch")
    return expected


def main() -> int:
    payload = json.loads(DEFAULT_DECISION.read_text(encoding="utf-8"))
    decision = validate_decision(payload)
    print(f"INDUSTRY_PROMOTION_DECISION_OK decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
