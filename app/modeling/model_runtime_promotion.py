"""原子 promotion sklearn runtime migration candidate，失敗時自動回滾。"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any

from sklearn.exceptions import InconsistentVersionWarning

from app.modeling.model_runtime_migration import (
    MAX_CALIBRATOR_DIFFERENCE,
    MIN_GRID_POINTS,
    SCHEMA_VERSION as MIGRATION_SCHEMA_VERSION,
)


SCHEMA_VERSION = "model-runtime-promotion.v1"
EQUIVALENCE_FLAGS = (
    "payload_keys_equal",
    "model_string_equal",
    "feature_names_equal",
    "model_feature_names_equal",
    "payload_features_match_model",
    "metadata_equal",
    "horizon_equal",
    "calibrator_output_shape_equal",
    "calibrator_within_tolerance",
)


class PromotionError(RuntimeError):
    """promotion 被拒絕或已回滾。"""

    def __init__(self, message: str, *, status: str, report_path: Path) -> None:
        super().__init__(message)
        self.status = status
        self.report_path = report_path


def promote_model_runtime_candidate(
    project_root: Path,
    candidate_path: Path,
    verdict_path: Path,
    backup_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """驗證 migration verdict 後原子替換正式模型，失敗則回滾。"""
    root = Path(project_root).resolve()
    paths = _validated_paths(
        root,
        candidate_path=Path(candidate_path),
        verdict_path=Path(verdict_path),
        backup_path=Path(backup_path),
        report_path=Path(report_path),
    )
    production_path = paths["production"]
    candidate_path = paths["candidate"]
    verdict_path = paths["verdict"]
    backup_path = paths["backup"]
    report_path = paths["report"]

    before = _file_snapshot(production_path, root)
    candidate = _file_snapshot(candidate_path, root)
    verdict_file = _file_snapshot(verdict_path, root)
    verdict = _read_verdict(verdict_path)
    verdict_summary = {
        **verdict_file,
        "schema_version": verdict.get("schema_version"),
        "status": _mapping(verdict.get("verdict")).get("status"),
    }
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PENDING",
        "executed": False,
        "before": before,
        "candidate": candidate,
        "backup": None,
        "after": None,
        "rollback": None,
        "verdict": verdict_summary,
        "errors": [],
    }

    failures = _preflight_failures(
        verdict,
        source_sha256=before["sha256"],
        candidate_sha256=candidate["sha256"],
    )
    if failures:
        report["status"] = "NO-GO"
        report["errors"] = failures
        _write_json_exclusive(report_path, report)
        raise PromotionError(
            f"promotion preflight 未通過：{', '.join(failures)}",
            status="NO-GO",
            report_path=report_path,
        )

    _copy_exclusive(production_path, backup_path)
    backup = _file_snapshot(backup_path, root)
    report["backup"] = backup
    if backup["sha256"] != before["sha256"]:
        report["status"] = "NO-GO"
        report["errors"] = ["backup_sha256_mismatch"]
        _write_json_exclusive(report_path, report)
        raise PromotionError(
            "backup SHA-256 與正式模型不一致",
            status="NO-GO",
            report_path=report_path,
        )

    source_before_replace = _file_snapshot(production_path, root)
    if source_before_replace["sha256"] != before["sha256"]:
        report["status"] = "NO-GO"
        report["errors"] = ["source_sha256_changed_before_replace"]
        _write_json_exclusive(report_path, report)
        raise PromotionError(
            "正式模型在 backup 後發生變更，拒絕 promotion",
            status="NO-GO",
            report_path=report_path,
        )

    replaced = False
    try:
        _replace_from(candidate_path, production_path)
        replaced = True
        report["executed"] = True
        after = _file_snapshot(production_path, root)
        report["after"] = after
        if after["sha256"] != candidate["sha256"]:
            raise ValueError("promoted_model_sha256_mismatch")
        report["after"].update(_verify_promoted_model(production_path))
        report["status"] = "GO"
        _write_json_exclusive(report_path, report)
        return report
    except Exception as exc:
        if not replaced:
            report["status"] = "NO-GO"
            report["errors"] = [f"replace_failed: {exc}"]
            _write_json_exclusive(report_path, report)
            raise PromotionError(
                f"正式模型替換失敗：{exc}",
                status="NO-GO",
                report_path=report_path,
            ) from exc

        report["errors"] = [f"post_replace_validation_failed: {exc}"]
        try:
            _replace_from(backup_path, production_path)
            rollback = _file_snapshot(production_path, root)
            report["rollback"] = rollback
            if rollback["sha256"] != before["sha256"]:
                raise ValueError("rollback_sha256_mismatch")
        except Exception as rollback_exc:
            report["status"] = "ROLLBACK_FAILED"
            report["errors"].append(f"rollback_failed: {rollback_exc}")
            _write_json_exclusive(report_path, report)
            raise PromotionError(
                f"promotion 驗證失敗且 rollback 失敗：{rollback_exc}",
                status="ROLLBACK_FAILED",
                report_path=report_path,
            ) from rollback_exc

        report["status"] = "ROLLED_BACK"
        _write_json_exclusive(report_path, report)
        raise PromotionError(
            f"promotion 驗證失敗，已完成 rollback：{exc}",
            status="ROLLED_BACK",
            report_path=report_path,
        ) from exc


def _validated_paths(
    root: Path,
    *,
    candidate_path: Path,
    verdict_path: Path,
    backup_path: Path,
    report_path: Path,
) -> dict[str, Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"找不到 project root：{root}")

    production = root / "models" / "latest_lgbm.pkl"
    candidate = _project_path(root, candidate_path)
    verdict = _project_path(root, verdict_path)
    backup = _project_path(root, backup_path)
    report = _project_path(root, report_path)
    shadow_root = root / "artifacts" / "shadow" / "model_runtime_migration"
    backup_root = root / "models" / "backup"
    report_root = root / "artifacts" / "model_runtime_promotion"

    _require_regular_file(production, "production model")
    _require_regular_file(candidate, "candidate")
    _require_regular_file(verdict, "verdict")
    _require_within(candidate, shadow_root, "candidate")
    _require_within(verdict, shadow_root, "verdict")
    _require_within(backup, backup_root, "backup")
    _require_within(report, report_root, "report")
    for label, path in (("backup", backup), ("report", report)):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"{label} 已存在，拒絕覆寫：{path}")
    if len({path.resolve() for path in (production, candidate, verdict, backup, report)}) != 5:
        raise ValueError("production、candidate、verdict、backup、report 必須完全隔離")
    return {
        "production": production,
        "candidate": candidate,
        "verdict": verdict,
        "backup": backup,
        "report": report,
    }


def _project_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"找不到 regular {label}：{path}")


def _require_within(path: Path, allowed_root: Path, label: str) -> None:
    resolved_root = allowed_root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root:
        raise ValueError(f"{label} 必須是允許目錄下的檔案")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} 路徑逃逸：必須位於 {allowed_root}") from exc


def _read_verdict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("migration verdict 必須是 JSON object")
    return payload


def _preflight_failures(
    verdict: dict[str, Any],
    *,
    source_sha256: str,
    candidate_sha256: str,
) -> list[str]:
    source = _mapping(verdict.get("source"))
    candidate = _mapping(verdict.get("candidate"))
    warnings_payload = _mapping(verdict.get("warnings"))
    equivalence = _mapping(verdict.get("equivalence"))
    verdict_payload = _mapping(verdict.get("verdict"))
    failures: list[str] = []

    if verdict.get("schema_version") != MIGRATION_SCHEMA_VERSION:
        failures.append("migration_schema_version_invalid")
    if verdict_payload.get("status") != "GO":
        failures.append("verdict_not_go")
    if verdict_payload.get("failures") != []:
        failures.append("verdict_failures_not_empty")
    if source.get("sha256") != source_sha256:
        failures.append("source_sha256_stale")
    if candidate.get("sha256") != candidate_sha256:
        failures.append("candidate_sha256_mismatch")
    if candidate.get("shadow_only") is not True:
        failures.append("candidate_not_shadow_only")
    warning_count = warnings_payload.get("candidate_inconsistent_version_count")
    if type(warning_count) is not int or warning_count != 0:
        failures.append("candidate_inconsistent_version_warning_present")
    if warnings_payload.get("candidate_reload") != []:
        failures.append("candidate_reload_warning_present")

    failed_flags = {
        name for name in EQUIVALENCE_FLAGS if equivalence.get(name) is not True
    }
    failed_flags.update(
        name
        for name, value in equivalence.items()
        if isinstance(value, bool) and value is not True
    )
    failures.extend(f"equivalence.{name}" for name in sorted(failed_flags))

    grid_points = equivalence.get("calibrator_grid_points")
    tolerance = equivalence.get("calibrator_tolerance")
    max_difference = equivalence.get("calibrator_max_abs_difference")
    if type(grid_points) is not int or grid_points < MIN_GRID_POINTS:
        failures.append("calibrator_grid_points_invalid")
    if not _is_number(tolerance) or not 0 <= tolerance <= MAX_CALIBRATOR_DIFFERENCE:
        failures.append("calibrator_tolerance_invalid")
    if (
        not _is_number(max_difference)
        or not _is_number(tolerance)
        or max_difference < 0
        or max_difference > tolerance
    ):
        failures.append("calibrator_difference_out_of_tolerance")
    return failures


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_number(value: Any) -> bool:
    if type(value) is int:
        return True
    return type(value) is float and math.isfinite(value)


def _copy_exclusive(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with source.open("rb") as source_handle, destination.open("xb") as output:
            created = True
            shutil.copyfileobj(source_handle, output)
            os.fchmod(output.fileno(), source.stat().st_mode & 0o777)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def _replace_from(source: Path, destination: Path) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".model-runtime-promotion-",
            suffix=".pkl.tmp",
            dir=destination.parent,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            with source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, output)
            os.fchmod(output.fileno(), source.stat().st_mode & 0o777)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _verify_promoted_model(path: Path) -> dict[str, Any]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with path.open("rb") as handle:
            pickle.load(handle)
    inconsistent_count = sum(
        issubclass(item.category, InconsistentVersionWarning) for item in caught
    )
    if inconsistent_count:
        raise ValueError("promoted_model_inconsistent_version_warning_present")
    return {
        "loadable": True,
        "warning_count": len(caught),
        "inconsistent_version_warning_count": inconsistent_count,
    }


def _file_snapshot(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.resolve().relative_to(root).as_posix(),
        "sha256": _sha256(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with path.open("x", encoding="utf-8") as handle:
            created = True
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise
