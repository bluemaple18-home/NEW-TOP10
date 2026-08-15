from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.research.adaptive_shadow_queue import (
    DEFAULT_BUNDLE,
    DEFAULT_BUNDLE_RELATIVE,
    DEFAULT_MANIFEST,
    DEFAULT_MANIFEST_RELATIVE,
    DEFAULT_POLICY,
    DEFAULT_POLICY_RELATIVE,
    ShadowQueueBoundaryError,
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
        with pytest.raises(
            ShadowQueueBoundaryError,
            match="INPUT_BUNDLE_NOT_COMMITTED_PATH",
        ):
            build_projection(bundle_path=path, manifest_path=DEFAULT_MANIFEST)


def test_capacity_and_queue_drift_fail_closed(tmp_path: Path) -> None:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    capacity = copy.deepcopy(manifest)
    capacity["capacity"]["status"] = "FAIL"
    capacity_path = _write_manifest(tmp_path / "capacity", capacity)
    with pytest.raises(
        ShadowQueueBoundaryError,
        match="INPUT_MANIFEST_NOT_COMMITTED_PATH",
    ):
        build_projection(manifest_path=capacity_path)

    parity = copy.deepcopy(manifest)
    parity["parity"]["unchanged"] = False
    parity_path = _write_manifest(tmp_path / "parity", parity)
    with pytest.raises(
        ShadowQueueBoundaryError,
        match="INPUT_MANIFEST_NOT_COMMITTED_PATH",
    ):
        build_projection(manifest_path=parity_path)


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


@pytest.mark.parametrize(
    "case",
    ["absolute", "traversal", "symlink_escape", "canonical_alias"],
)
def test_builder_rejects_invalid_output_root_before_side_effects(
    tmp_path: Path,
    case: str,
) -> None:
    if case == "absolute":
        argument = tmp_path / "absolute-output"
        target = argument
    elif case == "traversal":
        argument = Path("../traversal-output")
        target = tmp_path.parent / "traversal-output"
    elif case == "symlink_escape":
        target = tmp_path.parent / "symlink-output"
        argument = tmp_path / "output-link"
        argument.symlink_to(target, target_is_directory=True)
    else:
        argument = Path("artifacts/autonomous_research")
        target = tmp_path / argument

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/build_adaptive_shadow_queue.py"),
            "--output-root",
            str(argument),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2, completed.stderr
    assert not target.exists() or not any(target.iterdir())
    assert "OUTPUT_ROOT_" in completed.stderr


@pytest.mark.parametrize(
    ("flag", "source"),
    [
        ("--bundle", DEFAULT_BUNDLE),
        ("--manifest", DEFAULT_MANIFEST),
        ("--policy", DEFAULT_POLICY),
    ],
)
@pytest.mark.parametrize("path_kind", ["external", "traversal", "symlink"])
def test_clis_reject_uncommitted_input_authority(
    tmp_path: Path,
    flag: str,
    source: Path,
    path_kind: str,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    copied = tmp_path / source.name
    copied.write_bytes(source.read_bytes())
    if path_kind == "external":
        argument = copied
    elif path_kind == "traversal":
        argument = Path("..") / copied.name
    else:
        argument = work / f"linked-{copied.name}"
        argument.symlink_to(copied)

    for script in (
        "scripts/build_adaptive_shadow_queue.py",
        "scripts/verify_adaptive_shadow_queue.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / script), flag, str(argument)],
            cwd=work,
            text=True,
            capture_output=True,
            check=False,
        )

        assert completed.returncode == 2, (script, completed.stdout, completed.stderr)
        assert "INPUT_" in completed.stderr


@pytest.mark.parametrize(
    ("kind", "relative_path", "source"),
    [
        ("bundle", DEFAULT_BUNDLE_RELATIVE, DEFAULT_BUNDLE),
        ("manifest", DEFAULT_MANIFEST_RELATIVE, DEFAULT_MANIFEST),
        ("policy", DEFAULT_POLICY_RELATIVE, DEFAULT_POLICY),
    ],
)
def test_committed_path_content_drift_fails_closed(
    tmp_path: Path,
    kind: str,
    relative_path: Path,
    source: Path,
) -> None:
    sources = {
        DEFAULT_BUNDLE_RELATIVE: DEFAULT_BUNDLE,
        DEFAULT_MANIFEST_RELATIVE: DEFAULT_MANIFEST,
        DEFAULT_POLICY_RELATIVE: DEFAULT_POLICY,
    }
    for target_relative, committed_source in sources.items():
        target = tmp_path / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(committed_source.read_bytes())
    drifted = tmp_path / relative_path
    drifted.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(
        ShadowQueueBoundaryError,
        match=f"INPUT_{kind.upper()}_CONTENT_DRIFT",
    ):
        build_projection(
            bundle_path=tmp_path / DEFAULT_BUNDLE_RELATIVE,
            manifest_path=tmp_path / DEFAULT_MANIFEST_RELATIVE,
            policy_path=tmp_path / DEFAULT_POLICY_RELATIVE,
            canonical_queue_path=tmp_path / "artifacts/autonomous_research/next_action_queue.json",
            project_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("priority_band", "CRITICAL", "ROW_0:PRIORITY_BAND_NOT_COMMITTED"),
        ("action", "EXECUTE_PRODUCTION", "ROW_0:ACTION_NOT_COMMITTED"),
    ],
)
def test_projection_verifier_rejects_uncommitted_band_or_action_after_rehash(
    field: str,
    value: str,
    error: str,
) -> None:
    payload = build_projection()
    payload["rows"][0][field] = value
    payload["rows"][0]["row_id"] = content_hash(payload["rows"][0], omit={"row_id"})
    payload["semantic_hash"] = content_hash(
        payload,
        omit={"projection_id", "semantic_hash", "generated_at"},
    )
    payload["projection_id"] = content_hash(
        {
            "schema_version": payload["schema_version"],
            "semantic_hash": payload["semantic_hash"],
            "policy_hash": payload["policy"]["policy_hash"],
        }
    )

    report = verify_projection(payload)

    assert report["status"] == "FAIL"
    assert error in report["errors"]
