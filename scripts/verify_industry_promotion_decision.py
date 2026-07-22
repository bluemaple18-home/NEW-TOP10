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
NESTED_FIELDS = {
    "input": {"features_sha256", "features_size_bytes", "research_artifact_sha256"},
    "sample": {"rows", "stocks", "trade_days", "latest_labeled_trade_date", "horizon_trading_days"},
    "method": {"self_leakage_control", "top_n", "shadow_overlay_weight", "same_universe_dates_cost", "production_score_mutated"},
    "metrics": {
        "production_mean_return", "shadow_mean_return", "return_uplift",
        "production_hit_rate", "shadow_hit_rate", "hit_rate_uplift",
        "production_downside", "shadow_downside",
        "production_top_industry_concentration",
        "shadow_top_industry_concentration",
    },
    "gate": {"minimum_return_uplift", "minimum_hit_rate_uplift", "maximum_concentration_increase"},
}


class IndustryPromotionDecisionError(ValueError):
    """產業 promotion evidence 違反 fail-closed contract。"""


def validate_decision(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping) or set(payload) != TOP_LEVEL_FIELDS:
        raise IndustryPromotionDecisionError("decision top-level shape mismatch")
    if payload["schema_version"] != "industry-promotion-decision-v1":
        raise IndustryPromotionDecisionError("unsupported schema_version")
    for field, expected_fields in NESTED_FIELDS.items():
        value = payload[field]
        if not isinstance(value, Mapping) or set(value) != expected_fields:
            raise IndustryPromotionDecisionError(f"{field} shape mismatch")
    input_identity = payload["input"]
    for field in ("features_sha256", "research_artifact_sha256"):
        digest = input_identity[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise IndustryPromotionDecisionError(f"{field} must be sha256")
    if type(input_identity["features_size_bytes"]) is not int or input_identity["features_size_bytes"] <= 0:
        raise IndustryPromotionDecisionError("features_size_bytes must be positive")
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
    if qualifies:
        expected = "GO"
    elif metrics["return_uplift"] > 0:
        expected = "MONITOR_ONLY"
    else:
        expected = "REJECT"
    if payload["decision"] != expected:
        raise IndustryPromotionDecisionError(
            f"decision mismatch: expected {expected}"
        )
    expected_action = (
        "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
        if expected == "GO"
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
