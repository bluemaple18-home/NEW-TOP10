"""正式資料與模型唯讀的 daily v2 shadow adapter。"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
from typing import Any
from uuid import uuid4
import warnings

from app.agent_b_ranking import StockRanker
from app.contracts.daily_v2 import validate_run_identity
from app.contracts.daily_v2_comparison import (
    REAL_SHADOW_MANIFEST_SCHEMA_VERSION,
    build_ranking_comparison,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RealShadowExecutionError(RuntimeError):
    """正式資料 shadow 執行失敗，且 manifest 已保留證據。"""


def run_real_shadow(
    *,
    run_id: str,
    run_date: str,
    workspace: Path,
    data_dir: Path,
    model_dir: Path,
    baseline_ranking: Path,
    model_filename: str = "latest_lgbm.pkl",
    config_path: Path | None = None,
    numeric_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """以 StockRanker 正式讀取路徑產生隔離 ranking 與比較證據。"""

    validate_run_identity(run_id, run_date)
    workspace = Path(workspace).expanduser().resolve()
    run_dir = (workspace / run_id).resolve()
    _assert_within(run_dir, workspace, "shadow run directory")

    data_dir = Path(data_dir).expanduser().resolve()
    model_dir = Path(model_dir).expanduser().resolve()
    baseline_ranking = Path(baseline_ranking).expanduser().resolve()
    config_path = Path(config_path or PROJECT_ROOT / "config" / "signals.yaml").expanduser().resolve()
    model_path = (model_dir / model_filename).resolve()
    expected_baseline_name = f"ranking_{run_date}.csv"
    if baseline_ranking.name != expected_baseline_name:
        raise ValueError(
            "baseline ranking date mismatch: "
            f"expected {expected_baseline_name}, got {baseline_ranking.name}"
        )
    if not _is_within(model_path, model_dir):
        raise ValueError(f"model path must stay within model_dir: {model_path}")
    if _is_within(run_dir, data_dir) or _is_within(run_dir, model_dir):
        raise ValueError("shadow run directory must not be inside data_dir or model_dir")

    source_specs = {
        "features": (data_dir / "features.parquet", True),
        "events": (data_dir / "events.parquet", False),
        "universe": (data_dir / "universe.parquet", False),
        "model": (model_path, True),
        "baseline_ranking": (baseline_ranking, True),
        "config": (config_path, True),
    }
    for label, (path, required) in source_specs.items():
        if required and not path.is_file():
            raise FileNotFoundError(f"required {label} input not found: {path}")
        if _is_within(path, run_dir):
            raise ValueError(f"source input must be outside shadow run directory: {path}")
    _validate_baseline_content_date(baseline_ranking, run_date)

    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    comparison_path = run_dir / "comparison.json"
    inputs_before = _snapshot_sources(source_specs)
    runtime_versions = collect_runtime_versions()
    model_compatibility = _model_compatibility([])
    manifest: dict[str, Any] = {
        "schema_version": REAL_SHADOW_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "run_date": run_date,
        "status": "started",
        "shadow_only": True,
        "live_send_enabled": False,
        "run_dir": str(run_dir),
        "runtime_versions": runtime_versions,
        "model_compatibility": model_compatibility,
        "inputs_before": inputs_before,
        "inputs_after": None,
        "inputs_unchanged": None,
        "outputs": {},
        "comparison_status": None,
        "production_switch": {
            "status": "NOT-EVALUATED",
            "executed": False,
            "reasons": [],
        },
        "started_at": _now(),
        "finished_at": None,
        "error": None,
    }
    _write_json(manifest_path, manifest)

    try:
        ranker = StockRanker(
            data_dir=str(data_dir),
            model_dir=str(model_dir),
            artifact_dir=str(run_dir),
            config_path=str(config_path),
            generate_report=False,
            explain_top_n=0,
        )
        model_load_error: Exception | None = None
        with warnings.catch_warnings(record=True) as caught_model_warnings:
            warnings.simplefilter("always")
            try:
                ranker.load_model(model_filename)
            except Exception as exc:
                model_load_error = exc
        model_compatibility = _model_compatibility(caught_model_warnings)
        manifest["model_compatibility"] = model_compatibility
        _write_json(manifest_path, manifest)
        if model_load_error is not None:
            raise RealShadowExecutionError(
                f"model load failed: {model_path}: {model_load_error}"
            ) from model_load_error

        try:
            ranking_result = ranker.run_ranking(run_date)
        except Exception as exc:
            raise RealShadowExecutionError(f"ranking failed: {exc}") from exc
        ranking_path = Path(ranking_result).expanduser().resolve()
        if not _is_within(ranking_path, run_dir):
            raise RealShadowExecutionError(
                f"ranking output is outside shadow run directory: {ranking_path}"
            )
        expected_name = f"ranking_{run_date}.csv"
        if ranking_path.name != expected_name or not ranking_path.is_file():
            raise RealShadowExecutionError(
                f"ranking output missing or date mismatch: expected {run_dir / expected_name}"
            )

        inputs_after = _snapshot_sources(source_specs)
        inputs_unchanged = _snapshots_equal(inputs_before, inputs_after)
        if not inputs_unchanged:
            raise RealShadowExecutionError("read-only source inputs changed during shadow execution")

        comparison = build_ranking_comparison(
            baseline_path=baseline_ranking,
            shadow_path=ranking_path,
            input_snapshots=inputs_before,
            numeric_tolerance=numeric_tolerance,
            runtime_versions=runtime_versions,
            model_compatibility=model_compatibility,
            run_date=run_date,
        )
        _write_json(comparison_path, comparison)
        manifest.update(
            {
                "status": "finished",
                "inputs_after": inputs_after,
                "inputs_unchanged": True,
                "outputs": {
                    "ranking": _snapshot(ranking_path, required=True),
                    "comparison": _snapshot(comparison_path, required=True),
                },
                "comparison_status": comparison["status"],
                "production_switch": comparison["production_switch"],
                "finished_at": _now(),
            }
        )
        _write_json(manifest_path, manifest)
        return {
            "status": comparison["status"],
            "production_switch_status": comparison["production_switch"]["status"],
            "run_id": run_id,
            "run_dir": str(run_dir),
            "ranking": str(ranking_path),
            "manifest": str(manifest_path),
            "comparison": str(comparison_path),
            "live_send_enabled": False,
        }
    except Exception as exc:
        inputs_after = _snapshot_sources(source_specs)
        manifest.update(
            {
                "status": "failed",
                "model_compatibility": model_compatibility,
                "inputs_after": inputs_after,
                "inputs_unchanged": _snapshots_equal(inputs_before, inputs_after),
                "finished_at": _now(),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        _write_json(manifest_path, manifest)
        if isinstance(exc, RealShadowExecutionError):
            raise
        raise RealShadowExecutionError(str(exc)) from exc


def collect_runtime_versions() -> dict[str, str]:
    """記錄能解釋模型 pickle 相容性的 runtime 版本。"""

    result = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }
    for package in ("scikit-learn", "pandas", "numpy", "lightgbm"):
        try:
            result[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return result


def _validate_baseline_content_date(path: Path, run_date: str) -> None:
    """若 baseline 已帶日期欄，內容日期也必須綁定本次 run_date。"""

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        date_columns = [
            column
            for column in ("run_date", "trade_date", "date")
            if column in (reader.fieldnames or [])
        ]
        if not date_columns:
            return
        values = {column: set() for column in date_columns}
        for row in reader:
            for column in date_columns:
                value = str(row.get(column) or "").strip()
                if value:
                    values[column].add(value)
    for column, column_values in values.items():
        if column_values != {run_date}:
            raise ValueError(
                "baseline ranking date mismatch: "
                f"column {column} expected {run_date}, got {sorted(column_values)}"
            )


def _model_compatibility(caught: list[warnings.WarningMessage]) -> dict[str, Any]:
    warning_records = [
        {
            "category": item.category.__name__,
            "message": str(item.message),
            "filename": str(item.filename),
            "lineno": item.lineno,
        }
        for item in caught
    ]
    version_mismatch = any(
        record["category"] == "InconsistentVersionWarning"
        or (
            "scikit-learn" in record["message"].lower()
            and "version" in record["message"].lower()
        )
        for record in warning_records
    )
    return {
        "status": "WARNING" if warning_records else "OK",
        "version_mismatch": version_mismatch,
        "warnings": warning_records,
    }


def _snapshot_sources(
    source_specs: dict[str, tuple[Path, bool]],
) -> dict[str, dict[str, Any]]:
    return {
        label: _snapshot(path, required=required)
        for label, (path, required) in source_specs.items()
    }


def _snapshot(path: Path, *, required: bool) -> dict[str, Any]:
    path = Path(path).resolve()
    if not path.is_file():
        return {
            "path": str(path),
            "required": required,
            "exists": False,
            "size_bytes": None,
            "mtime_ns": None,
            "sha256": None,
        }
    stat = path.stat()
    return {
        "path": str(path),
        "required": required,
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _sha256(path),
    }


def _snapshots_equal(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> bool:
    fields = ("exists", "size_bytes", "mtime_ns", "sha256")
    return before.keys() == after.keys() and all(
        all(before[label].get(field) == after[label].get(field) for field in fields)
        for label in before
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _assert_within(path: Path, parent: Path, label: str) -> None:
    if not _is_within(path, parent):
        raise ValueError(f"{label} must stay within workspace: {path}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
