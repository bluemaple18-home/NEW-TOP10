from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from app.research.adaptive_shadow_queue import (
    DEFAULT_BUNDLE,
    DEFAULT_MANIFEST,
    build_projection,
    verify_projection,
)
from app.research.contracts import content_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bundle() -> dict:
    return json.loads(DEFAULT_BUNDLE.read_text(encoding="utf-8"))


def _write_bundle(tmp_path: Path, payload: dict) -> Path:
    payload["bundle_id"] = content_hash(payload, omit={"bundle_id", "generated_at"})
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def test_committed_bundle_builds_deterministic_shadow_projection() -> None:
    first = build_projection()
    second = build_projection()

    assert first["status"] == "PASS"
    assert first["projection_id"] == second["projection_id"]
    assert first["semantic_hash"] == second["semantic_hash"]
    assert [row["row_id"] for row in first["rows"]] == [row["row_id"] for row in second["rows"]]
    assert first["canonical_parity"]["unchanged"] is True
    assert first["counts"]["rows"] == 1
    assert first["rows"][0]["priority_band"] == "HIGH"
    assert first["rows"][0]["parameter"] == "horizon"
    assert first["rows"][0]["evidence_counts"]["matched_contrasts"] == 4
    assert first["rows"][0]["evidence_counts"]["distinct_lineages"] == 2
    assert verify_projection(first)["status"] == "PASS"


def test_negative_admission_fixtures_fail_closed(tmp_path: Path) -> None:
    base = _bundle()
    cases = []

    missing_cycle = copy.deepcopy(base)
    missing_cycle["cycles"].pop()
    missing_cycle["counts"]["cycles"] = 1
    cases.append(missing_cycle)

    sealed = copy.deepcopy(base)
    sealed["observations"][0]["sealed_usage_status"] = "SEALED"
    cases.append(sealed)

    unknown = copy.deepcopy(base)
    unknown["observations"][0]["sealed_usage_status"] = "UNKNOWN"
    cases.append(unknown)

    duplicate = copy.deepcopy(base)
    duplicate["observations"].append(copy.deepcopy(duplicate["observations"][0]))
    duplicate["counts"]["observations"] += 1
    cases.append(duplicate)

    low_contrast = copy.deepcopy(base)
    low_contrast["learning_projection"]["matched_contrasts"] = low_contrast["learning_projection"]["matched_contrasts"][:2]
    low_contrast["learning_projection"]["scope_evidence"][0]["matched_contrast_count"] = 2
    low_contrast["counts"]["matched_contrasts"] = 2
    cases.append(low_contrast)

    for index, payload in enumerate(cases):
        path = _write_bundle(tmp_path / str(index), payload)
        result = build_projection(bundle_path=path, manifest_path=DEFAULT_MANIFEST)
        assert result["status"] == "NO-GO"
        assert result["rows"] == []


def test_capacity_and_queue_drift_fail_closed(tmp_path: Path) -> None:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    capacity = copy.deepcopy(manifest)
    capacity["capacity"]["status"] = "FAIL"
    capacity_path = _write_manifest(tmp_path / "capacity", capacity)
    capacity_result = build_projection(manifest_path=capacity_path)
    assert capacity_result["status"] == "NO-GO"
    assert "CAPACITY_NOT_PASS" in capacity_result["reason_codes"]

    parity = copy.deepcopy(manifest)
    parity["parity"]["unchanged"] = False
    parity_path = _write_manifest(tmp_path / "parity", parity)
    parity_result = build_projection(manifest_path=parity_path)
    assert parity_result["status"] == "NO-GO"
    assert "PARITY_DRIFT" in parity_result["reason_codes"]


def test_high_priority_rejects_disqualified_flags() -> None:
    result = build_projection()
    row = copy.deepcopy(result["rows"][0])
    row["flags"] = ["SHARP_PEAK", "OVERFIT_RISK"]
    row["row_id"] = content_hash(row, omit={"row_id"})
    result["rows"] = [row]
    result["semantic_hash"] = content_hash(result, omit={"projection_id", "semantic_hash", "generated_at"})
    result["projection_id"] = content_hash(
        {
            "schema_version": result["schema_version"],
            "semantic_hash": result["semantic_hash"],
            "policy_hash": result["policy"]["policy_hash"],
        }
    )

    report = verify_projection(result)

    assert report["status"] == "FAIL"
    assert "ROW_0:DISQUALIFIED_HIGH_PRIORITY" in report["errors"]


def test_cli_self_test_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_adaptive_shadow_queue.py", "--self-test"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
