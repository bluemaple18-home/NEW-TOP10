#!/usr/bin/env python3
"""以 committed production replay 重算產業 overlay promotion 決策。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISION = (
    PROJECT_ROOT / "docs" / "evidence" / "INDUSTRY-PROMOTION-20260722" / "decision.json"
)
DECISION_FIELDS = {
    "schema_version", "candidate", "replay_path", "replay_sha256", "gate",
    "decision", "production_action",
}
GATE_FIELDS = {
    "minimum_production_replay_days", "minimum_return_uplift",
    "minimum_hit_rate_uplift", "maximum_concentration_increase",
}


class IndustryPromotionDecisionError(ValueError):
    """產業 promotion evidence 違反 fail-closed contract。"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_replay(decision_path: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise IndustryPromotionDecisionError("replay_path must be relative")
    base = decision_path.parent.resolve()
    replay = (base / value).resolve()
    try:
        replay.relative_to(base)
    except ValueError as error:
        raise IndustryPromotionDecisionError("replay_path escapes evidence directory") from error
    if not replay.is_file():
        raise IndustryPromotionDecisionError("replay artifact is missing")
    return replay


def _validate_replay(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != "industry-momentum-production-replay-v1":
        raise IndustryPromotionDecisionError("replay is not a production baseline")
    if payload.get("status") != "OK":
        raise IndustryPromotionDecisionError("replay status is not OK")
    method = payload.get("method")
    if not isinstance(method, Mapping):
        raise IndustryPromotionDecisionError("replay method is missing")
    required_method = {
        "baseline_kind": "committed-production-ranking-artifacts",
        "production_score_unchanged": True,
        "writes_production_ranking": False,
        "cost_assumption": "NO_TRANSACTION_COST_APPLIED_TO_EITHER_ARM",
    }
    if any(method.get(key) != value for key, value in required_method.items()):
        raise IndustryPromotionDecisionError("replay method boundary mismatch")
    manifest = (payload.get("input") or {}).get("production_ranking_manifest")
    if not isinstance(manifest, Mapping) or set(manifest) != {"file_count", "files", "canonical_sha256"}:
        raise IndustryPromotionDecisionError("ranking manifest shape mismatch")
    files = manifest["files"]
    if not isinstance(files, list) or manifest["file_count"] != len(files):
        raise IndustryPromotionDecisionError("ranking manifest count mismatch")
    canonical = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if canonical != manifest["canonical_sha256"]:
        raise IndustryPromotionDecisionError("ranking manifest checksum mismatch")
    summary = payload.get("summary") or {}
    walkforward = payload.get("walkforward") or {}
    if summary.get("trade_days") != walkforward.get("days"):
        raise IndustryPromotionDecisionError("replay day count mismatch")
    daily = walkforward.get("daily")
    if not isinstance(daily, list) or len(daily) != walkforward.get("days"):
        raise IndustryPromotionDecisionError("replay daily evidence mismatch")
    metric_sources = {
        "production_mean_return": "production_mean_return",
        "shadow_mean_return": "shadow_mean_return",
        "production_hit_rate": "production_hit_rate",
        "shadow_hit_rate": "shadow_hit_rate",
        "production_top_industry_concentration": "production_top_industry_concentration",
        "shadow_top_industry_concentration": "shadow_top_industry_concentration",
        "average_overlap_count": "overlap_count",
    }
    for output_field, daily_field in metric_sources.items():
        values = [row[daily_field] for row in daily]
        recomputed = round(sum(values) / len(values), 4)
        if walkforward.get(output_field) != recomputed:
            raise IndustryPromotionDecisionError(
                f"replay aggregate mismatch: {output_field}"
            )
    derived_metrics = {
        "return_uplift": round(
            sum(row["shadow_mean_return"] - row["production_mean_return"] for row in daily)
            / len(daily),
            4,
        ),
        "hit_rate_uplift": round(
            sum(row["shadow_hit_rate"] - row["production_hit_rate"] for row in daily)
            / len(daily),
            4,
        ),
    }
    for field, recomputed in derived_metrics.items():
        if walkforward.get(field) != recomputed:
            raise IndustryPromotionDecisionError(f"replay aggregate mismatch: {field}")


def derive_decision(replay: Mapping[str, Any], gate: Mapping[str, Any]) -> str:
    if not isinstance(gate, Mapping) or set(gate) != GATE_FIELDS:
        raise IndustryPromotionDecisionError("gate shape mismatch")
    if any(type(value) not in {int, float} for value in gate.values()):
        raise IndustryPromotionDecisionError("gate values must be numeric")
    walkforward = replay["walkforward"]
    if walkforward["days"] < gate["minimum_production_replay_days"]:
        return "NO_GO_INSUFFICIENT_PRODUCTION_HISTORY"
    concentration_delta = (
        walkforward["shadow_top_industry_concentration"]
        - walkforward["production_top_industry_concentration"]
    )
    qualifies = (
        walkforward["return_uplift"] > gate["minimum_return_uplift"]
        and walkforward["hit_rate_uplift"] >= gate["minimum_hit_rate_uplift"]
        and concentration_delta <= gate["maximum_concentration_increase"]
    )
    if qualifies:
        return "GO"
    if walkforward["return_uplift"] > 0:
        return "MONITOR_ONLY"
    return "REJECT"


def validate_decision_file(path: Path = DEFAULT_DECISION) -> str:
    decision_path = Path(path)
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or set(payload) != DECISION_FIELDS:
        raise IndustryPromotionDecisionError("decision top-level shape mismatch")
    if payload["schema_version"] != "industry-promotion-decision-v2":
        raise IndustryPromotionDecisionError("unsupported decision schema")
    replay_path = _resolve_replay(decision_path, payload["replay_path"])
    if _sha256(replay_path) != payload["replay_sha256"]:
        raise IndustryPromotionDecisionError("replay SHA-256 mismatch")
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    _validate_replay(replay)
    expected = derive_decision(replay, payload["gate"])
    if payload["decision"] != expected:
        raise IndustryPromotionDecisionError(f"decision mismatch: expected {expected}")
    action = (
        "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
        if expected == "GO"
        else "NO_RANKING_OR_WEIGHT_CHANGE"
    )
    if payload["production_action"] != action:
        raise IndustryPromotionDecisionError("production action mismatch")
    return expected


def main() -> int:
    decision = validate_decision_file()
    print(f"INDUSTRY_PROMOTION_DECISION_OK decision={decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
