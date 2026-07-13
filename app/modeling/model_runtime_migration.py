"""建立 sklearn runtime migration candidate 與等價證據。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import pickle
import platform
import tempfile
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.exceptions import InconsistentVersionWarning


SCHEMA_VERSION = "model-runtime-migration.v1"
MAX_CALIBRATOR_DIFFERENCE = 1e-12
MIN_GRID_POINTS = 1001


def build_migration_candidate(
    source_path: Path,
    candidate_path: Path,
    report_path: Path,
    *,
    grid_points: int = MIN_GRID_POINTS,
) -> dict[str, Any]:
    """重新序列化 candidate，通過等價檢查後才發布到指定輸出。"""
    source_path = Path(source_path)
    candidate_path = Path(candidate_path)
    report_path = Path(report_path)
    _validate_paths(source_path, candidate_path, report_path)
    if grid_points < MIN_GRID_POINTS:
        raise ValueError(f"grid_points 不得少於 {MIN_GRID_POINTS}")

    source_before = _file_snapshot(source_path)
    source_payload, source_warnings = _load_pickle(source_path)
    _require_model_payload(source_payload)

    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_candidate = _dump_temporary_pickle(source_payload, candidate_path.parent)
    try:
        candidate_payload, candidate_warnings = _load_pickle(temporary_candidate)
        _require_model_payload(candidate_payload)
        candidate_sha256 = _sha256(temporary_candidate)
        source_after = _file_snapshot(source_path)
        equivalence = _equivalence_metrics(
            source_payload,
            candidate_payload,
            grid_points=grid_points,
        )
        source_inconsistent = _inconsistent_warnings(source_warnings)
        candidate_inconsistent = _inconsistent_warnings(candidate_warnings)
        failures = _equivalence_failures(
            equivalence,
            source_inconsistent=source_inconsistent,
            candidate_inconsistent=candidate_inconsistent,
            source_unchanged=source_before == source_after,
        )
        status = "GO" if not failures else "NO-GO"
        report: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source": {
                "path": source_path.as_posix(),
                "sha256": source_before["sha256"],
                "mtime_ns_before": source_before["mtime_ns"],
                "mtime_ns_after": source_after["mtime_ns"],
                "unchanged": source_before == source_after,
            },
            "candidate": {
                "path": candidate_path.as_posix(),
                "sha256": candidate_sha256,
                "created": False,
                "shadow_only": True,
            },
            "runtime_versions": _runtime_versions(),
            "warnings": {
                "source_load": source_warnings,
                "candidate_reload": candidate_warnings,
                "source_inconsistent_version_count": len(source_inconsistent),
                "candidate_inconsistent_version_count": len(candidate_inconsistent),
            },
            "equivalence": equivalence,
            "verdict": {
                "status": status,
                "failures": failures,
                "production_model": False,
                "promotion_evaluated": False,
            },
        }
        candidate_published = False
        try:
            if status == "GO":
                candidate_published = True
                os.replace(temporary_candidate, candidate_path)
                report["candidate"]["created"] = True
            _write_json_atomic(report_path, report)
        except Exception:
            if candidate_published:
                candidate_path.unlink(missing_ok=True)
            report_path.unlink(missing_ok=True)
            raise
        return report
    finally:
        temporary_candidate.unlink(missing_ok=True)


def _validate_paths(source_path: Path, candidate_path: Path, report_path: Path) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"找不到 source model：{source_path}")
    resolved = {
        "source": source_path.resolve(),
        "candidate": candidate_path.resolve(),
        "report": report_path.resolve(),
    }
    if len(set(resolved.values())) != len(resolved):
        raise ValueError("source、candidate、report 路徑必須完全隔離")
    for label, path in (("candidate", candidate_path), ("report", report_path)):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"{label} 已存在，拒絕覆蓋：{path}")


def _require_model_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise TypeError("model payload 必須是 dict")
    missing = {"model", "calibrator", "feature_names", "metadata"} - set(payload)
    if missing:
        raise ValueError(f"model payload 缺少必要欄位：{sorted(missing)}")
    if not hasattr(payload["model"], "model_to_string"):
        raise TypeError("model 必須提供 model_to_string()")
    if not hasattr(payload["model"], "feature_name"):
        raise TypeError("model 必須提供 feature_name()")
    if not hasattr(payload["calibrator"], "predict"):
        raise TypeError("calibrator 必須提供 predict()")


def _equivalence_metrics(
    source: dict[str, Any],
    candidate: dict[str, Any],
    *,
    grid_points: int,
) -> dict[str, Any]:
    source_model_string = source["model"].model_to_string()
    candidate_model_string = candidate["model"].model_to_string()
    source_model_features = list(source["model"].feature_name())
    candidate_model_features = list(candidate["model"].feature_name())
    source_features = list(source["feature_names"])
    candidate_features = list(candidate["feature_names"])
    source_metadata = source["metadata"]
    candidate_metadata = candidate["metadata"]

    grid = np.linspace(0.0, 1.0, grid_points, dtype=float)
    source_probability = np.asarray(source["calibrator"].predict(grid), dtype=float)
    candidate_probability = np.asarray(candidate["calibrator"].predict(grid), dtype=float)
    same_shape = source_probability.shape == candidate_probability.shape
    max_difference: float | None = (
        float(np.max(np.abs(source_probability - candidate_probability)))
        if same_shape and source_probability.size
        else None
    )
    within_tolerance = (
        max_difference is not None and max_difference <= MAX_CALIBRATOR_DIFFERENCE
    )
    return {
        "payload_keys_equal": set(source) == set(candidate),
        "model_string_equal": source_model_string == candidate_model_string,
        "source_model_string_sha256": hashlib.sha256(
            source_model_string.encode("utf-8")
        ).hexdigest(),
        "candidate_model_string_sha256": hashlib.sha256(
            candidate_model_string.encode("utf-8")
        ).hexdigest(),
        "feature_names_equal": source_features == candidate_features,
        "model_feature_names_equal": source_model_features == candidate_model_features,
        "payload_features_match_model": source_features == source_model_features,
        "metadata_equal": source_metadata == candidate_metadata,
        "horizon_equal": _horizon(source_metadata) == _horizon(candidate_metadata),
        "calibrator_grid_points": grid_points,
        "calibrator_output_shape_equal": same_shape,
        "calibrator_max_abs_difference": max_difference,
        "calibrator_tolerance": MAX_CALIBRATOR_DIFFERENCE,
        "calibrator_within_tolerance": within_tolerance,
    }


def _equivalence_failures(
    metrics: dict[str, Any],
    *,
    source_inconsistent: list[dict[str, Any]],
    candidate_inconsistent: list[dict[str, Any]],
    source_unchanged: bool,
) -> list[str]:
    failures = [
        name
        for name in (
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
        if metrics[name] is not True
    ]
    if not source_inconsistent:
        failures.append("source_inconsistent_version_warning_missing")
    if candidate_inconsistent:
        failures.append("candidate_inconsistent_version_warning_present")
    if not source_unchanged:
        failures.append("source_changed")
    return failures


def _horizon(metadata: Any) -> Any:
    return metadata.get("horizon") if isinstance(metadata, dict) else None


def _load_pickle(path: Path) -> tuple[Any, list[dict[str, Any]]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    return payload, [_warning_record(item) for item in caught]


def _warning_record(item: warnings.WarningMessage) -> dict[str, Any]:
    message = item.message
    record = {
        "category": item.category.__name__,
        "message": str(message),
    }
    for name in ("estimator_name", "original_sklearn_version", "current_sklearn_version"):
        value = getattr(message, name, None)
        if value is not None:
            record[name] = str(value)
    return record


def _inconsistent_warnings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record["category"] == InconsistentVersionWarning.__name__
    ]


def _dump_temporary_pickle(payload: dict[str, Any], output_dir: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=".model-runtime-migration-",
        suffix=".pkl.tmp",
        dir=output_dir,
        delete=False,
    ) as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        handle.flush()
        os.fsync(handle.fileno())
        return Path(handle.name)


def _runtime_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for package in ("scikit-learn", "numpy", "lightgbm", "joblib"):
        versions[package] = importlib.metadata.version(package)
    return versions


def _file_snapshot(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"sha256": _sha256(path), "mtime_ns": stat.st_mtime_ns}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
