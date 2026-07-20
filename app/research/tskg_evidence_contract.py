"""Research Team 採用 TSKG 概念的 additive evidence contract。"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping


SCHEMA_VERSION = "research-evidence-tskg-adoption.v1"
ADOPTION_MODES = {"GRANDFATHERED", "CHECK_ON_REUSE", "REQUIRED_NOW"}
USAGE_INTENTS = {
    "ARCHIVE_ONLY",
    "RESEARCH_ONLY",
    "REUSE",
    "PROMOTION",
    "MODEL_INPUT",
    "FORMAL_FACT",
}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "research_id",
    "usage_intent",
    "adoption_mode",
    "identity_assessment",
    "source_assessment",
    "temporal_scope",
    "conflict_assessment",
    "evidence_refs",
    "decision",
    "hard_block",
    "blocking_reasons",
}
_ASSESSMENT_FIELDS = {
    "identity_assessment": {"status", "entity_refs", "resolver_version"},
    "source_assessment": {"status", "source_refs", "policy_receipt_refs"},
    "temporal_scope": {"status", "as_of", "valid_from", "valid_to"},
    "conflict_assessment": {"status", "conflict_refs"},
}
_STATUS_VALUES = {
    "identity_assessment": {
        "NOT_EVALUATED",
        "RESOLVED",
        "AMBIGUOUS",
        "NOT_FOUND",
        "UNKNOWN",
    },
    "source_assessment": {
        "NOT_EVALUATED",
        "APPROVED",
        "SYNTHETIC_ONLY",
        "BLOCKED",
        "EXPIRED",
        "UNKNOWN",
    },
    "temporal_scope": {"NOT_EVALUATED", "BOUNDED", "OPEN", "UNKNOWN"},
    "conflict_assessment": {
        "NOT_EVALUATED",
        "NONE",
        "OPEN",
        "RESOLVED",
        "UNKNOWN",
    },
}
_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$"
)


def build_evidence_envelope(
    *,
    research_id: str,
    usage_intent: str,
    adoption_mode: str,
    identity_assessment: Mapping[str, Any] | None = None,
    source_assessment: Mapping[str, Any] | None = None,
    temporal_scope: Mapping[str, Any] | None = None,
    conflict_assessment: Mapping[str, Any] | None = None,
    evidence_refs: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """建立不改變既有 workflow 控制流的 research evidence envelope。"""

    if not isinstance(research_id, str) or not research_id.strip():
        raise ValueError("research_id must be a non-empty string")
    if usage_intent not in USAGE_INTENTS:
        raise ValueError("unsupported usage_intent")
    if adoption_mode not in ADOPTION_MODES:
        raise ValueError("unsupported adoption_mode")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "research_id": research_id,
        "usage_intent": usage_intent,
        "adoption_mode": adoption_mode,
        "identity_assessment": _assessment(
            identity_assessment,
            {"status": "NOT_EVALUATED", "entity_refs": [], "resolver_version": None},
        ),
        "source_assessment": _assessment(
            source_assessment,
            {
                "status": "NOT_EVALUATED",
                "source_refs": [],
                "policy_receipt_refs": [],
            },
        ),
        "temporal_scope": _assessment(
            temporal_scope,
            {
                "status": "NOT_EVALUATED",
                "as_of": None,
                "valid_from": None,
                "valid_to": None,
            },
        ),
        "conflict_assessment": _assessment(
            conflict_assessment,
            {"status": "NOT_EVALUATED", "conflict_refs": []},
        ),
        "evidence_refs": sorted(set(evidence_refs)),
    }
    decision, hard_block, reasons = _evaluate(payload)
    payload.update(
        decision=decision,
        hard_block=hard_block,
        blocking_reasons=reasons,
    )
    report = verify_evidence_envelope(payload)
    if report["status"] != "OK":
        raise ValueError(f"invalid evidence envelope: {report['failed_checks']}")
    return payload


def verify_evidence_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    """以 deterministic checks 驗證 envelope，不執行研究或外部 I/O。"""

    failed: list[str] = []
    if not isinstance(payload, Mapping):
        return {"status": "FAILED", "failed_checks": ["top_level_shape"]}
    value = dict(payload)
    if set(value) != _TOP_LEVEL_FIELDS:
        failed.append("top_level_shape")
    if value.get("schema_version") != SCHEMA_VERSION:
        failed.append("schema_version")
    if not isinstance(value.get("research_id"), str) or not value["research_id"].strip():
        failed.append("research_id")
    if value.get("usage_intent") not in USAGE_INTENTS:
        failed.append("usage_intent")
    if value.get("adoption_mode") not in ADOPTION_MODES:
        failed.append("adoption_mode")
    for name, fields in _ASSESSMENT_FIELDS.items():
        assessment = value.get(name)
        if not isinstance(assessment, dict) or set(assessment) != fields:
            failed.append(f"{name}_shape")
            continue
        if assessment.get("status") not in _STATUS_VALUES[name]:
            failed.append(f"{name}_status")
        for key in fields - {"status", "resolver_version", "as_of", "valid_from", "valid_to"}:
            if not _is_string_list(assessment.get(key)):
                failed.append(f"{name}_{key}")
    if not _is_string_list(value.get("evidence_refs")):
        failed.append("evidence_refs")
    elif not all(_is_repo_relative_ref(item) for item in value["evidence_refs"]):
        failed.append("evidence_refs_repo_relative")
    source_assessment = value.get("source_assessment")
    if isinstance(source_assessment, dict) and _is_string_list(
        source_assessment.get("policy_receipt_refs")
    ):
        if not all(
            _is_repo_relative_ref(item)
            for item in source_assessment["policy_receipt_refs"]
        ):
            failed.append("policy_receipt_refs_repo_relative")
    conflict_assessment = value.get("conflict_assessment")
    if isinstance(conflict_assessment, dict) and _is_string_list(
        conflict_assessment.get("conflict_refs")
    ):
        if not all(
            _is_repo_relative_ref(item) for item in conflict_assessment["conflict_refs"]
        ):
            failed.append("conflict_refs_repo_relative")
    temporal_scope = value.get("temporal_scope")
    if isinstance(temporal_scope, dict) and temporal_scope.get("status") in {
        "BOUNDED",
        "OPEN",
    }:
        timestamps = [temporal_scope.get("as_of")]
        if temporal_scope["status"] == "BOUNDED":
            timestamps.extend(
                [temporal_scope.get("valid_from"), temporal_scope.get("valid_to")]
            )
        else:
            timestamps.extend(
                item
                for item in (
                    temporal_scope.get("valid_from"),
                    temporal_scope.get("valid_to"),
                )
                if item is not None
            )
        if not all(_is_utc_timestamp(item) for item in timestamps):
            failed.append("temporal_scope_timestamp")

    if not any(
        name in failed
        for name in (
            "usage_intent",
            "adoption_mode",
            "identity_assessment_shape",
            "source_assessment_shape",
            "temporal_scope_shape",
            "conflict_assessment_shape",
        )
    ):
        expected = _evaluate(value)
        if value.get("decision") != expected[0]:
            failed.append("decision_matches_recomputed")
        if value.get("hard_block") is not expected[1]:
            failed.append("hard_block_matches_recomputed")
        if value.get("blocking_reasons") != expected[2]:
            failed.append("blocking_reasons_match_recomputed")
    return {
        "status": "OK" if not failed else "FAILED",
        "failed_checks": sorted(set(failed)),
    }


def compact_adoption_summary(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """供既有 artifacts 附加概念摘要；不複製完整 evidence。"""

    report = verify_evidence_envelope(envelope)
    if report["status"] != "OK":
        raise ValueError("cannot summarize invalid evidence envelope")
    return {
        "schema_version": envelope["schema_version"],
        "adoption_mode": envelope["adoption_mode"],
        "usage_intent": envelope["usage_intent"],
        "decision": envelope["decision"],
        "hard_block": envelope["hard_block"],
    }


def _assessment(value: Mapping[str, Any] | None, default: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(value)) if value is not None else deepcopy(default)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _is_repo_relative_ref(value: str) -> bool:
    if value.startswith(("/", "\\")) or "://" in value:
        return False
    return ".." not in value.replace("\\", "/").split("/")


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _evaluate(payload: Mapping[str, Any]) -> tuple[str, bool, list[str]]:
    mode = payload["adoption_mode"]
    intent = payload["usage_intent"]
    if mode == "GRANDFATHERED" and intent == "ARCHIVE_ONLY":
        return "GRANDFATHERED", False, []
    if mode == "CHECK_ON_REUSE" and intent == "ARCHIVE_ONLY":
        return "DEFERRED", False, []

    reasons: list[str] = []
    identity = payload["identity_assessment"]["status"]
    source = payload["source_assessment"]["status"]
    temporal = payload["temporal_scope"]["status"]
    conflict = payload["conflict_assessment"]["status"]
    if identity != "RESOLVED":
        reasons.append(
            "identity_not_evaluated"
            if identity == "NOT_EVALUATED"
            else f"identity_{identity.casefold()}"
        )
    if source not in {"APPROVED", "SYNTHETIC_ONLY"}:
        reasons.append(
            "source_not_evaluated"
            if source == "NOT_EVALUATED"
            else f"source_{source.casefold()}"
        )
    if temporal not in {"BOUNDED", "OPEN"}:
        reasons.append(
            "temporal_scope_not_evaluated"
            if temporal == "NOT_EVALUATED"
            else "temporal_scope_unknown"
        )
    if conflict not in {"NONE", "RESOLVED"}:
        reasons.append(
            "conflict_not_evaluated"
            if conflict == "NOT_EVALUATED"
            else f"conflict_{conflict.casefold()}"
        )
    if not payload["evidence_refs"]:
        reasons.append("evidence_refs_missing")
    reasons = sorted(reasons)
    if not reasons:
        return "READY", False, []
    if intent == "RESEARCH_ONLY":
        return "NEEDS_EVIDENCE", False, reasons
    return "BLOCKED", True, reasons
