"""每日自動化與 Daily V2 共用的核心契約。"""

from __future__ import annotations


DAILY_CORE_CONTRACT_VERSION = "top10.daily-core-contract.v1"
PRODUCTION_CORE_STEP_MAP = {
    "etl": "etl",
    "data.validate": "validate",
    "ranking": "rank",
    "daily.report": "report",
    "clawd.payload": "publish-ready",
}
DAILY_CORE_STEPS = tuple(PRODUCTION_CORE_STEP_MAP.values())
PRODUCTION_EQUIVALENT_PROFILE = "production-equivalent"


def has_production_equivalent_attestation(workflow_manifest: dict) -> bool:
    """只有 manifest 自身宣告且綁定共用契約時，才視為 production-equivalent。"""

    attestation = workflow_manifest.get("production_equivalence")
    return bool(
        isinstance(attestation, dict)
        and attestation.get("profile") == PRODUCTION_EQUIVALENT_PROFILE
        and attestation.get("contract_version") == DAILY_CORE_CONTRACT_VERSION
        and attestation.get("attested") is True
    )
