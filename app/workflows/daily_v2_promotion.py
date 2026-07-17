"""Daily V2 production promotion 的 fail-closed 決策契約。"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.workflows.daily_v2_parity import (
    PARITY_REPORT_SCHEMA_VERSION,
    verify_daily_v2_parity_report_from_files,
)


PROMOTION_DECISION_SCHEMA_VERSION = "top10.daily-v2.promotion-decision.v1"
PROMOTION_ACCEPTANCE_SCHEMA_VERSION = "top10.daily-v2.promotion-acceptance.v1"
INDEPENDENT_REVIEW_SCHEMA_VERSION = "top10.architecture-independent-review.v1"
SCRIPT_GOVERNANCE_SCHEMA_VERSION = "top10.script-governance.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FAILURE_SCENARIOS = frozenset({"timeout", "partial_output", "stale_input"})
ACCEPTANCE_EVIDENCE_SCHEMAS = {
    "failure_injection": "top10.daily-v2.failure-injection-evidence.v1",
    "persistent_resume": "top10.daily-v2.resume-evidence.v1",
    "wrapper_rollback": "top10.daily-v2.rollback-evidence.v1",
}
REVIEW_EVIDENCE_SCHEMA_VERSION = "top10.architecture-review-evidence.v1"


class DailyV2PromotionError(ValueError):
    """Promotion evidence 或決策違反契約。"""


def _blocker(code: str, message: str, evidence: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "evidence": evidence}


def _bound_evidence_valid(
    payload: Mapping[str, Any],
    *,
    kind: str,
    expected_base_sha: str,
    expected_candidate_sha: str,
) -> bool:
    """驗證 evidence 語意，但在外部信任根完成前永不授權。

    JSON schema、digest、Git SHA 與 exit code 都可由同一個本機作者自行產生，
    只能作為診斷資料，不能證明獨立 runner/reviewer 實際執行。未來必須以
    repo 外的可信簽發器與固定公鑰新增另一版 schema，不能用布林開關放行。
    """
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("base_sha") or "")):
        return False
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("candidate_sha") or "")):
        return False
    records = payload.get("evidence")
    if not isinstance(records, list) or not records:
        return False
    evidence_payloads: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            return False
        path = _resolve_portable_path(str(record.get("path") or ""))
        if not path.is_file() or _sha256(path) != record.get("sha256"):
            return False
        evidence_kind = str(record.get("kind") or "")
        try:
            parsed = _read_json(path)
        except (OSError, json.JSONDecodeError, DailyV2PromotionError):
            return False
        evidence_payloads[evidence_kind] = parsed
    base_sha = str(payload["base_sha"])
    candidate_sha = str(payload["candidate_sha"])
    if base_sha != expected_base_sha or candidate_sha != expected_candidate_sha:
        return False
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_sha, candidate_sha],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    if ancestry.returncode != 0:
        return False
    if kind == "acceptance":
        runner = payload.get("runner")
        if not isinstance(runner, Mapping) or not runner.get("id") or not runner.get("version"):
            return False
        if set(evidence_payloads) != set(ACCEPTANCE_EVIDENCE_SCHEMAS):
            return False
        for evidence_kind, schema in ACCEPTANCE_EVIDENCE_SCHEMAS.items():
            item = evidence_payloads[evidence_kind]
            if (
                item.get("schema_version") != schema
                or item.get("base_sha") != base_sha
                or item.get("candidate_sha") != candidate_sha
                or item.get("runner") != runner
            ):
                return False
        failure = evidence_payloads["failure_injection"]
        scenario_results = failure.get("scenarios")
        if not isinstance(scenario_results, Mapping) or any(
            scenario_results.get(name) != "GO" for name in REQUIRED_FAILURE_SCENARIOS
        ):
            return False
        resume = evidence_payloads["persistent_resume"]
        if not (
            resume.get("status") == "GO"
            and str(resume.get("checkpointer_backend") or "").lower() not in {"", "memory", "inmemory", "memorysaver"}
            and isinstance(resume.get("idempotency_keys"), list)
            and bool(resume.get("idempotency_keys"))
            and resume.get("completed_outputs_preserved") is True
        ):
            return False
        rollback = evidence_payloads["wrapper_rollback"]
        if not (
            rollback.get("status") == "GO"
            and rollback.get("tested") is True
            and rollback.get("entrypoint_before_sha256")
            and rollback.get("entrypoint_after_sha256") == rollback.get("entrypoint_before_sha256")
        ):
            return False
    elif kind == "review":
        reviewer = payload.get("reviewer")
        if not isinstance(reviewer, Mapping) or reviewer.get("independent") is not True or not reviewer.get("id"):
            return False
        if set(evidence_payloads) != {"review"}:
            return False
        review = evidence_payloads["review"]
        if not (
            review.get("schema_version") == REVIEW_EVIDENCE_SCHEMA_VERSION
            and review.get("base_sha") == base_sha
            and review.get("candidate_sha") == candidate_sha
            and review.get("reviewer") == reviewer
            and review.get("verdict") == payload.get("verdict")
            and isinstance(review.get("findings"), list)
            and isinstance(review.get("verification"), list)
            and bool(review.get("verification"))
            and all(isinstance(item, Mapping) and item.get("exit_code") == 0 for item in review["verification"])
        ):
            return False
    # 所有本機語意檢查通過仍不等於具有獨立信任根；目前刻意 fail closed。
    return False


def _build_daily_v2_promotion_decision(
    *,
    parity_reports: Iterable[Mapping[str, Any]],
    script_governance: Mapping[str, Any],
    acceptance: Mapping[str, Any] | None,
    independent_review: Mapping[str, Any] | None,
    expected_base_sha: str,
    expected_candidate_sha: str,
    evidence_files_verified: bool,
) -> dict[str, Any]:
    """只產生決策，不修改 wrapper、launchd、通知或任何 production artifact。"""

    parity = list(parity_reports)
    if not parity:
        raise DailyV2PromotionError("至少需要一份 parity report")
    if any(item.get("schema_version") != PARITY_REPORT_SCHEMA_VERSION for item in parity):
        raise DailyV2PromotionError("parity report schema 不支援")
    if script_governance.get("schema_version") != SCRIPT_GOVERNANCE_SCHEMA_VERSION:
        raise DailyV2PromotionError("script governance schema 不支援")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_base_sha):
        raise DailyV2PromotionError("expected base SHA 必須是完整 40 字元 SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_candidate_sha):
        raise DailyV2PromotionError("expected candidate SHA 必須是完整 40 字元 SHA")

    blockers: list[dict[str, Any]] = []
    if not evidence_files_verified:
        blockers.append(
            _blocker(
                "unverified_evidence_sources",
                "直接傳入的記憶體 payload 不得授權 promotion；必須使用 file-backed builder/verifier",
            )
        )
    parity_no_go = [item.get("run_date") for item in parity if item.get("status") != "GO"]
    if parity_no_go:
        blockers.append(_blocker("parity_no_go", "所有代表日期 parity 必須為 GO", parity_no_go))
    unsuccessful = [item.get("run_date") for item in parity if item.get("execution_outcome") != "succeeded"]
    if unsuccessful:
        blockers.append(_blocker("unsuccessful_execution", "promotion 只接受成功執行 evidence", unsuccessful))
    production_equivalent = [
        item
        for item in parity
        if (item.get("contract") or {}).get("workflow_profile") == "production-equivalent"
        and (item.get("production_switch") or {}).get("status") == "GO"
    ]
    equivalent_dates = sorted({str(item.get("run_date")) for item in production_equivalent if item.get("run_date")})
    if len(equivalent_dates) < 2:
        blockers.append(
            _blocker(
                "production_equivalent_parity_dates",
                "至少需要兩個不同日期的 production-equivalent parity GO",
                {"actual_dates": equivalent_dates, "required": 2},
            )
        )

    governance_strict = (script_governance.get("strict") or {}).get("passed") is True
    if not governance_strict:
        blockers.append(_blocker("script_governance_no_go", "script governance strict gate 必須通過"))
    unknown_edges = script_governance.get("unknown_references") or []
    if unknown_edges:
        blockers.append(
            _blocker(
                "unresolved_dynamic_imports",
                "production promotion 前必須處理或以獨立證據 disposition dynamic import unknown edges",
                unknown_edges,
            )
        )

    if acceptance is None:
        blockers.append(_blocker("promotion_acceptance_missing", "缺少 failure/resume/rollback acceptance evidence"))
    else:
        if acceptance.get("schema_version") != PROMOTION_ACCEPTANCE_SCHEMA_VERSION:
            raise DailyV2PromotionError("promotion acceptance schema 不支援")
        if not _bound_evidence_valid(
            acceptance,
            kind="acceptance",
            expected_base_sha=expected_base_sha,
            expected_candidate_sha=expected_candidate_sha,
        ):
            blockers.append(
                _blocker(
                    "promotion_acceptance_unbound",
                    "acceptance 必須綁定固定 SHA、原始 evidence 與 repo 外可信簽發器；目前信任根尚未建立",
                )
            )

    if independent_review is None:
        blockers.append(_blocker("independent_review_missing", "缺少固定 SHA 的獨立 review"))
    else:
        if independent_review.get("schema_version") != INDEPENDENT_REVIEW_SCHEMA_VERSION:
            raise DailyV2PromotionError("independent review schema 不支援")
        if not _bound_evidence_valid(
            independent_review,
            kind="review",
            expected_base_sha=expected_base_sha,
            expected_candidate_sha=expected_candidate_sha,
        ):
            blockers.append(
                _blocker(
                    "independent_review_unbound",
                    "independent review 必須綁定固定 SHA、review evidence 與 repo 外可信簽發器；目前信任根尚未建立",
                )
            )
        if independent_review.get("verdict") != "GO":
            blockers.append(_blocker("independent_review_no_go", "獨立 review verdict 必須為 GO"))

    status = "GO" if not blockers else "NO-GO"
    return {
        "schema_version": PROMOTION_DECISION_SCHEMA_VERSION,
        "status": status,
        "decision": "promote" if status == "GO" else "retain_current_production",
        "base_sha": expected_base_sha,
        "candidate_sha": expected_candidate_sha,
        "parity_dates": sorted({str(item.get("run_date")) for item in parity if item.get("run_date")}),
        "production_equivalent_dates": equivalent_dates,
        "blockers": blockers,
        "production_switch": {
            "authorized": status == "GO",
            "executed": False,
            "daily_entrypoint_modified": _git_path_modified(
                expected_base_sha,
                expected_candidate_sha,
                "scripts/run_automation.py",
            ),
            "live_notification_modified": False,
        },
    }


def build_daily_v2_promotion_decision(
    *,
    parity_reports: Iterable[Mapping[str, Any]],
    script_governance: Mapping[str, Any],
    acceptance: Mapping[str, Any] | None,
    independent_review: Mapping[str, Any] | None,
    expected_base_sha: str,
    expected_candidate_sha: str,
) -> dict[str, Any]:
    """建立不可授權的記憶體預覽；正式決策只接受 file-backed API。"""

    return _build_daily_v2_promotion_decision(
        parity_reports=parity_reports,
        script_governance=script_governance,
        acceptance=acceptance,
        independent_review=independent_review,
        expected_base_sha=expected_base_sha,
        expected_candidate_sha=expected_candidate_sha,
        evidence_files_verified=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DailyV2PromotionError(f"JSON root 必須是 object：{path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve_portable_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()


def _git_path_modified(base_sha: str, candidate_sha: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", base_sha, candidate_sha, "--", path],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise DailyV2PromotionError(f"無法比較 production entrypoint：{base_sha}..{candidate_sha}")
    return result.returncode == 1


def build_daily_v2_promotion_decision_from_files(
    *,
    parity_paths: Iterable[Path],
    script_governance_path: Path,
    acceptance_path: Path | None = None,
    independent_review_path: Path | None = None,
    expected_base_sha: str,
    expected_candidate_sha: str,
) -> dict[str, Any]:
    paths = [Path(path).expanduser().resolve() for path in parity_paths]
    governance_path = Path(script_governance_path).expanduser().resolve()
    optional = {
        "acceptance": Path(acceptance_path).expanduser().resolve() if acceptance_path else None,
        "independent_review": Path(independent_review_path).expanduser().resolve() if independent_review_path else None,
    }
    for path in [*paths, governance_path, *(value for value in optional.values() if value)]:
        if not path.is_file():
            raise FileNotFoundError(path)
    parity = [_read_json(path) for path in paths]
    for report in parity:
        verify_daily_v2_parity_report_from_files(report)
    decision = _build_daily_v2_promotion_decision(
        parity_reports=parity,
        script_governance=_read_json(governance_path),
        acceptance=_read_json(optional["acceptance"]) if optional["acceptance"] else None,
        independent_review=_read_json(optional["independent_review"]) if optional["independent_review"] else None,
        expected_base_sha=expected_base_sha,
        expected_candidate_sha=expected_candidate_sha,
        evidence_files_verified=True,
    )
    decision["source_files"] = {
        "parity_reports": [{"path": _portable_path(path), "sha256": _sha256(path)} for path in paths],
        "script_governance": {"path": _portable_path(governance_path), "sha256": _sha256(governance_path)},
        **{
            label: {"path": _portable_path(path), "sha256": _sha256(path)}
            for label, path in optional.items()
            if path is not None
        },
    }
    return decision


def verify_daily_v2_promotion_decision_from_files(
    decision: Mapping[str, Any],
    *,
    expected_base_sha: str,
    expected_candidate_sha: str,
) -> None:
    if decision.get("schema_version") != PROMOTION_DECISION_SCHEMA_VERSION:
        raise DailyV2PromotionError("promotion decision schema 不支援")
    if decision.get("base_sha") != expected_base_sha or decision.get("candidate_sha") != expected_candidate_sha:
        raise DailyV2PromotionError("promotion decision 未綁定 verifier 指定的 base/candidate SHA")
    sources = decision.get("source_files")
    if not isinstance(sources, Mapping):
        raise DailyV2PromotionError("promotion decision 缺少 source_files")
    parity_records = sources.get("parity_reports")
    if not isinstance(parity_records, list) or not parity_records:
        raise DailyV2PromotionError("source_files 缺少 parity reports")

    def checked_path(record: Mapping[str, Any]) -> Path:
        path = _resolve_portable_path(str(record.get("path")))
        if not path.is_file() or _sha256(path) != record.get("sha256"):
            raise DailyV2PromotionError(f"source digest 不一致：{path}")
        return path

    expected = build_daily_v2_promotion_decision_from_files(
        parity_paths=[checked_path(record) for record in parity_records],
        script_governance_path=checked_path(sources["script_governance"]),
        acceptance_path=checked_path(sources["acceptance"]) if "acceptance" in sources else None,
        independent_review_path=(
            checked_path(sources["independent_review"]) if "independent_review" in sources else None
        ),
        expected_base_sha=expected_base_sha,
        expected_candidate_sha=expected_candidate_sha,
    )
    if decision != expected:
        raise DailyV2PromotionError("promotion decision 與 evidence 重算結果不一致")
