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
    """拒絕 manifest 自我簽發 production-equivalent 身分。

    目前 runner 尚未接上具外部信任根的 execution attestation，因此任何由
    workflow manifest 內嵌的 issuer／digest／command 宣告都只能算一般 shadow
    evidence，不能授權 production promotion。待受信任執行器完成後，應以新的
    schema 與獨立 verifier 取代此 fail-closed 實作。
    """

    del workflow_manifest
    return False
