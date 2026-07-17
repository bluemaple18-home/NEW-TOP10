"""合併 production status、Daily V2 與 real-shadow 的 parity 證據。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.automation.daily_contract import (
    DAILY_CORE_CONTRACT_VERSION,
    DAILY_CORE_STEPS,
    PRODUCTION_CORE_STEP_MAP,
    PRODUCTION_EQUIVALENT_PROFILE,
    has_production_equivalent_attestation,
)

PARITY_REPORT_SCHEMA_VERSION = "top10.daily-v2.parity-report.v1"
PRODUCTION_STATUS_SCHEMA_VERSION = "daily-run-status.v1"
WORKFLOW_MANIFEST_SCHEMA_VERSION = "top10.daily-workflow-v2.run-manifest.v1"
REAL_SHADOW_MANIFEST_SCHEMA_VERSION = "top10.daily-v2.real-shadow-manifest.v1"
RANKING_COMPARISON_SCHEMA_VERSION = "top10.daily-v2.ranking-comparison.v1"
WORKFLOW_PROFILES = frozenset({"fixture", PRODUCTION_EQUIVALENT_PROFILE})
MISMATCH_TYPES = frozenset(
    {
        "expected_difference",
        "contract_gap",
        "data_mismatch",
        "status_mismatch",
        "failure_semantics",
        "unsafe_side_effect",
    }
)
CORE_STEP_MAP = PRODUCTION_CORE_STEP_MAP
CORE_STEPS = DAILY_CORE_STEPS


class DailyV2ParityError(ValueError):
    """Parity input 或重算結果不符合契約。"""


def _require_schema(payload: Mapping[str, Any], expected: str, label: str) -> None:
    if payload.get("schema_version") != expected:
        raise DailyV2ParityError(f"{label} schema 不支援：{payload.get('schema_version')}")


def _mismatch(
    mismatch_type: str,
    code: str,
    message: str,
    *,
    blocking: bool,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mismatch_type not in MISMATCH_TYPES:
        raise DailyV2ParityError(f"不支援的 mismatch type：{mismatch_type}")
    return {
        "type": mismatch_type,
        "code": code,
        "blocking": blocking,
        "message": message,
        "evidence": evidence or {},
    }


def _normalize_production_status(status: str | None) -> str:
    return {
        "OK": "succeeded",
        "DRY_RUN": "planned",
        "FAILED": "failed",
        "SKIPPED": "skipped",
        "RUNNING": "running",
    }.get(str(status), "unknown")


def _normalize_workflow_status(status: str | None) -> str:
    return {
        "finished": "succeeded",
        "failed": "failed",
        "pending": "pending",
        "started": "running",
        "running": "running",
        "skipped": "skipped",
    }.get(str(status), "unknown")


def _production_core_steps(payload: Mapping[str, Any]) -> tuple[dict[str, str], list[str], list[str]]:
    normalized: dict[str, str] = {}
    order: list[str] = []
    duplicates: list[str] = []
    for step in payload.get("steps") or []:
        name = CORE_STEP_MAP.get(str(step.get("name")))
        if not name:
            continue
        if name in normalized:
            duplicates.append(name)
        normalized[name] = _normalize_production_status(step.get("status"))
        order.append(name)
    return normalized, order, sorted(set(duplicates))


def _workflow_core_steps(payload: Mapping[str, Any]) -> tuple[dict[str, str], list[str], list[str]]:
    normalized: dict[str, str] = {}
    order: list[str] = []
    duplicates: list[str] = []
    for step in payload.get("steps") or []:
        name = str(step.get("name"))
        if name not in CORE_STEPS:
            continue
        if name in normalized:
            duplicates.append(name)
        normalized[name] = _normalize_workflow_status(step.get("status"))
        order.append(name)
    return normalized, order, sorted(set(duplicates))


def _first_failed(steps: Mapping[str, str]) -> str | None:
    return next((name for name in CORE_STEPS if steps.get(name) == "failed"), None)


def _is_within(path: str | Path, parent: str | Path) -> bool:
    try:
        Path(path).expanduser().resolve().relative_to(Path(parent).expanduser().resolve())
    except ValueError:
        return False
    return True


def _outputs_preserved(workflow_manifest: Mapping[str, Any]) -> bool:
    for step in workflow_manifest.get("steps") or []:
        if _normalize_workflow_status(step.get("status")) != "succeeded":
            continue
        outputs = step.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            return False
        if any(not isinstance(output, dict) or output.get("exists") is not True for output in outputs):
            return False
    return True


def build_daily_v2_parity_report(
    *,
    production_status: dict[str, Any],
    workflow_manifest: dict[str, Any],
    real_shadow_manifest: dict[str, Any],
    ranking_comparison: dict[str, Any],
    shadow_root: Path,
    workflow_profile: str,
) -> dict[str, Any]:
    """建立不執行任何 production action 的 deterministic parity verdict。"""

    _require_schema(production_status, PRODUCTION_STATUS_SCHEMA_VERSION, "production status")
    _require_schema(workflow_manifest, WORKFLOW_MANIFEST_SCHEMA_VERSION, "workflow manifest")
    _require_schema(real_shadow_manifest, REAL_SHADOW_MANIFEST_SCHEMA_VERSION, "real-shadow manifest")
    _require_schema(ranking_comparison, RANKING_COMPARISON_SCHEMA_VERSION, "ranking comparison")
    if production_status.get("mode") != "daily":
        raise DailyV2ParityError("production status mode 必須是 daily")
    if workflow_profile not in WORKFLOW_PROFILES:
        raise DailyV2ParityError(f"workflow_profile 必須是 {sorted(WORKFLOW_PROFILES)}")

    shadow_root = Path(shadow_root).expanduser().resolve()
    mismatches: list[dict[str, Any]] = []
    if workflow_profile == PRODUCTION_EQUIVALENT_PROFILE and not has_production_equivalent_attestation(workflow_manifest):
        mismatches.append(
            _mismatch(
                "contract_gap",
                "production_equivalence_attestation_missing",
                "production-equivalent 必須由 workflow manifest 綁定共用核心契約，不接受 CLI 人工改標",
                blocking=True,
                evidence={"required_contract_version": DAILY_CORE_CONTRACT_VERSION},
            )
        )
    run_dates = {
        "production": production_status.get("run_date"),
        "workflow": workflow_manifest.get("run_date"),
        "real_shadow": real_shadow_manifest.get("run_date"),
    }
    if len(set(run_dates.values())) != 1 or None in run_dates.values():
        mismatches.append(
            _mismatch(
                "data_mismatch",
                "run_date_mismatch",
                "production、workflow 與 real-shadow 必須使用同一 run_date",
                blocking=True,
                evidence=run_dates,
            )
        )

    for label, manifest in (("workflow", workflow_manifest), ("real_shadow", real_shadow_manifest)):
        run_dir = manifest.get("run_dir")
        if not run_dir or not _is_within(str(run_dir), shadow_root):
            mismatches.append(
                _mismatch(
                    "unsafe_side_effect",
                    f"{label}_outside_shadow_root",
                    f"{label} run_dir 必須位於 shadow root 內",
                    blocking=True,
                    evidence={"run_dir": run_dir, "shadow_root": str(shadow_root)},
                )
            )

    production_steps, production_order, production_duplicates = _production_core_steps(production_status)
    workflow_steps, workflow_order, workflow_duplicates = _workflow_core_steps(workflow_manifest)
    if production_duplicates or workflow_duplicates:
        mismatches.append(
            _mismatch(
                "contract_gap",
                "duplicate_core_steps",
                "canonical core step 不得重複",
                blocking=True,
                evidence={"production": production_duplicates, "workflow": workflow_duplicates},
            )
        )

    production_failed = _first_failed(production_steps)
    workflow_failed = _first_failed(workflow_steps)
    production_outcome = _normalize_production_status(production_status.get("status"))
    workflow_outcome = _normalize_workflow_status(workflow_manifest.get("status"))
    execution_outcome = "failed" if "failed" in {production_outcome, workflow_outcome} else "succeeded"

    if production_failed != workflow_failed:
        mismatches.append(
            _mismatch(
                "failure_semantics",
                "first_failed_step_mismatch",
                "production 與 workflow 的第一個失敗步驟不一致",
                blocking=True,
                evidence={"production": production_failed, "workflow": workflow_failed},
            )
        )
    if production_outcome != workflow_outcome:
        mismatches.append(
            _mismatch(
                "status_mismatch",
                "workflow_outcome_mismatch",
                "production 與 workflow 最終狀態不一致",
                blocking=True,
                evidence={"production": production_outcome, "workflow": workflow_outcome},
            )
        )

    if production_failed and workflow_failed and production_failed == workflow_failed:
        required_steps = CORE_STEPS[: CORE_STEPS.index(production_failed) + 1]
    else:
        required_steps = CORE_STEPS
    for name in required_steps:
        production_value = production_steps.get(name)
        workflow_value = workflow_steps.get(name)
        if production_value is None or workflow_value is None:
            mismatches.append(
                _mismatch(
                    "contract_gap",
                    f"missing_core_step:{name}",
                    f"canonical step {name} 在 production 或 workflow 缺漏",
                    blocking=True,
                    evidence={"production": production_value, "workflow": workflow_value},
                )
            )
        elif production_value != workflow_value:
            mismatches.append(
                _mismatch(
                    "status_mismatch",
                    f"core_step_status:{name}",
                    f"canonical step {name} 狀態不一致",
                    blocking=True,
                    evidence={"production": production_value, "workflow": workflow_value},
                )
            )

    expected_order = list(required_steps)
    if [name for name in production_order if name in required_steps] != expected_order:
        mismatches.append(
            _mismatch(
                "contract_gap",
                "production_core_order",
                "production canonical steps 順序不符",
                blocking=True,
                evidence={"actual": production_order, "expected": expected_order},
            )
        )
    if [name for name in workflow_order if name in required_steps] != expected_order:
        mismatches.append(
            _mismatch(
                "contract_gap",
                "workflow_core_order",
                "Daily V2 canonical steps 順序不符",
                blocking=True,
                evidence={"actual": workflow_order, "expected": expected_order},
            )
        )

    completed_outputs_preserved = _outputs_preserved(workflow_manifest)
    if not completed_outputs_preserved:
        mismatches.append(
            _mismatch(
                "contract_gap",
                "completed_output_missing",
                "finished step 必須保留可驗證 output snapshot",
                blocking=True,
            )
        )

    if real_shadow_manifest.get("shadow_only") is not True:
        mismatches.append(_mismatch("unsafe_side_effect", "shadow_only_false", "real-shadow 必須標記 shadow_only=true", blocking=True))
    if real_shadow_manifest.get("live_send_enabled") is not False:
        mismatches.append(_mismatch("unsafe_side_effect", "live_send_enabled", "parity run 禁止 live send", blocking=True))
    if real_shadow_manifest.get("inputs_unchanged") is not True:
        mismatches.append(_mismatch("unsafe_side_effect", "source_input_mutated", "real-shadow source inputs 發生變更", blocking=True))
    for label, payload in (("real_shadow", real_shadow_manifest), ("ranking_comparison", ranking_comparison)):
        production_switch = payload.get("production_switch") or {}
        if production_switch.get("executed") is not False:
            mismatches.append(
                _mismatch(
                    "unsafe_side_effect",
                    f"{label}_production_switch_executed",
                    "parity evidence 不得執行 production switch",
                    blocking=True,
                )
            )

    data_statuses = {
        "real_shadow": real_shadow_manifest.get("comparison_status"),
        "ranking_comparison": ranking_comparison.get("status"),
        "ranking_production_switch": (ranking_comparison.get("production_switch") or {}).get("status"),
    }
    if any(value != "GO" for value in data_statuses.values()):
        mismatches.append(
            _mismatch(
                "data_mismatch",
                "ranking_parity_no_go",
                "real-shadow ranking comparison 未通過",
                blocking=True,
                evidence=data_statuses,
            )
        )

    production_extra_steps = [
        str(step.get("name"))
        for step in production_status.get("steps") or []
        if str(step.get("name")) not in CORE_STEP_MAP
    ]
    if production_extra_steps:
        mismatches.append(
            _mismatch(
                "expected_difference",
                "production_auxiliary_steps",
                "production 保留 V2 core 之外的輔助／研究步驟",
                blocking=False,
                evidence={"steps": production_extra_steps},
            )
        )
    if workflow_profile == "fixture":
        mismatches.append(
            _mismatch(
                "expected_difference",
                "fixture_workflow_profile",
                "fixture 只能證明 control-flow contract，不能授權 production switch",
                blocking=False,
            )
        )

    blocking = [item for item in mismatches if item["blocking"]]
    status = "GO" if not blocking else "NO-GO"
    promotion_blockers: list[str] = []
    if status != "GO":
        promotion_blockers.append("parity_no_go")
    if execution_outcome != "succeeded":
        promotion_blockers.append("successful_execution_evidence")
    if workflow_profile != "production-equivalent":
        promotion_blockers.append("production_equivalent_workflow")
    if data_statuses["ranking_production_switch"] != "GO":
        promotion_blockers.append("ranking_comparison_go")

    return {
        "schema_version": PARITY_REPORT_SCHEMA_VERSION,
        "status": status,
        "execution_outcome": execution_outcome,
        "run_date": run_dates["production"],
        "contract": {
            "version": DAILY_CORE_CONTRACT_VERSION,
            "core_steps": list(CORE_STEPS),
            "workflow_profile": workflow_profile,
            "shadow_root": str(shadow_root),
            "live_send_allowed": False,
            "automatic_full_fallback_allowed": False,
        },
        "step_parity": {
            "production": production_steps,
            "workflow": workflow_steps,
            "production_first_failed": production_failed,
            "workflow_first_failed": workflow_failed,
        },
        "resume": {
            "resume_count": int(workflow_manifest.get("resume_count") or 0),
            "completed_outputs_preserved": completed_outputs_preserved,
        },
        "data_parity": data_statuses,
        "mismatches": mismatches,
        "summary": {
            "blocking_count": len(blocking),
            "mismatch_type_counts": {
                mismatch_type: sum(item["type"] == mismatch_type for item in mismatches)
                for mismatch_type in sorted(MISMATCH_TYPES)
            },
        },
        "production_switch": {
            "status": "GO" if not promotion_blockers else "NO-GO",
            "executed": False,
            "blockers": promotion_blockers,
        },
    }


def verify_daily_v2_parity_report(
    report: dict[str, Any],
    *,
    production_status: dict[str, Any],
    workflow_manifest: dict[str, Any],
    real_shadow_manifest: dict[str, Any],
    ranking_comparison: dict[str, Any],
    shadow_root: Path,
    workflow_profile: str,
) -> None:
    """重算 parity report，拒絕狀態文案或刪除 blocker 自證。"""

    _require_schema(report, PARITY_REPORT_SCHEMA_VERSION, "parity report")
    expected = build_daily_v2_parity_report(
        production_status=production_status,
        workflow_manifest=workflow_manifest,
        real_shadow_manifest=real_shadow_manifest,
        ranking_comparison=ranking_comparison,
        shadow_root=shadow_root,
        workflow_profile=workflow_profile,
    )
    source_files = report.get("source_files")
    if source_files is not None:
        expected["source_files"] = source_files
    if report != expected:
        raise DailyV2ParityError("parity report 與輸入重算結果不一致")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DailyV2ParityError(f"JSON root 必須是 object：{path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_daily_v2_parity_report_from_files(
    *,
    production_status_path: Path,
    workflow_manifest_path: Path,
    real_shadow_manifest_path: Path,
    ranking_comparison_path: Path,
    shadow_root: Path,
    workflow_profile: str,
) -> dict[str, Any]:
    """從四份 evidence 檔案建立具 digest 的 parity report。"""

    paths = {
        "production_status": Path(production_status_path).expanduser().resolve(),
        "workflow_manifest": Path(workflow_manifest_path).expanduser().resolve(),
        "real_shadow_manifest": Path(real_shadow_manifest_path).expanduser().resolve(),
        "ranking_comparison": Path(ranking_comparison_path).expanduser().resolve(),
    }
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{label} evidence 不存在：{path}")
    report = build_daily_v2_parity_report(
        production_status=_read_json(paths["production_status"]),
        workflow_manifest=_read_json(paths["workflow_manifest"]),
        real_shadow_manifest=_read_json(paths["real_shadow_manifest"]),
        ranking_comparison=_read_json(paths["ranking_comparison"]),
        shadow_root=shadow_root,
        workflow_profile=workflow_profile,
    )
    report["source_files"] = {
        label: {"path": str(path), "sha256": _sha256(path)} for label, path in paths.items()
    }
    return report


def verify_daily_v2_parity_report_from_files(report: dict[str, Any]) -> None:
    """依 report 綁定的 evidence paths/digests 重算。"""

    source_files = report.get("source_files")
    if not isinstance(source_files, dict):
        raise DailyV2ParityError("file-backed parity report 缺少 source_files")
    paths: dict[str, Path] = {}
    for label in ("production_status", "workflow_manifest", "real_shadow_manifest", "ranking_comparison"):
        record = source_files.get(label)
        if not isinstance(record, dict):
            raise DailyV2ParityError(f"source_files 缺少 {label}")
        path = Path(str(record.get("path"))).expanduser().resolve()
        if not path.is_file() or _sha256(path) != record.get("sha256"):
            raise DailyV2ParityError(f"source evidence digest 不一致：{label}")
        paths[label] = path
    expected = build_daily_v2_parity_report_from_files(
        production_status_path=paths["production_status"],
        workflow_manifest_path=paths["workflow_manifest"],
        real_shadow_manifest_path=paths["real_shadow_manifest"],
        ranking_comparison_path=paths["ranking_comparison"],
        shadow_root=Path(report["contract"]["shadow_root"]),
        workflow_profile=str(report["contract"]["workflow_profile"]),
    )
    if report != expected:
        raise DailyV2ParityError("file-backed parity report 與 evidence 重算結果不一致")
