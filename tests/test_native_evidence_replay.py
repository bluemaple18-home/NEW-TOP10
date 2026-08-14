from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.research.contracts import content_hash
from app.research.native_evidence_replay import verify_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = (
    PROJECT_ROOT
    / "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json"
)


def _bundle() -> dict:
    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


def _rehash(payload: dict) -> dict:
    payload["bundle_id"] = content_hash(payload, omit={"bundle_id", "generated_at"})
    return payload


def test_committed_bundle_recomputes_deterministically() -> None:
    payload = _bundle()
    first = verify_bundle(payload, project_root=PROJECT_ROOT)
    second = verify_bundle(copy.deepcopy(payload), project_root=PROJECT_ROOT)

    assert first == second
    assert first["status"] == "PASS"
    assert first["recomputed_counts"] == {
        "cycles": 2,
        "execution_units": 8,
        "observations": 8,
        "adaptive_eligible": 8,
        "distinct_lineages": 4,
        "matched_contrasts": 4,
    }
    assert payload["admission"]["status"] == "PASS"


def test_bundle_tamper_missing_duplicate_and_sealed_fail_closed() -> None:
    base = _bundle()
    cases = []

    tampered = copy.deepcopy(base)
    tampered["observations"][0]["result"]["score"] += 1
    cases.append(tampered)

    missing = copy.deepcopy(base)
    missing["observations"].pop()
    cases.append(missing)

    duplicate = copy.deepcopy(base)
    duplicate["observations"].append(copy.deepcopy(duplicate["observations"][0]))
    cases.append(duplicate)

    sealed = copy.deepcopy(base)
    sealed["observations"][0]["sealed_usage_status"] = "SEALED"
    cases.append(sealed)

    unknown = copy.deepcopy(base)
    unknown["observations"][0]["sealed_usage_status"] = "UNKNOWN"
    cases.append(unknown)

    hash_mismatch = copy.deepcopy(base)
    hash_mismatch["policies"]["learning_policy_hash"] = "sha256:" + "0" * 64
    cases.append(hash_mismatch)

    for payload in cases:
        assert verify_bundle(payload, project_root=PROJECT_ROOT)["status"] == "FAIL"


@pytest.mark.parametrize("stage", ["COARSE_SCREEN", "SEALED_VALIDATION"])
def test_replay_verifier_rejects_non_development_stage_after_rehash(stage: str) -> None:
    payload = _bundle()
    payload["observations"][0]["research_stage"] = stage
    report = verify_bundle(_rehash(payload), project_root=PROJECT_ROOT)

    assert report["status"] == "FAIL"
    assert any("RESEARCH_STAGE" in error or "ELIGIBILITY" in error for error in report["errors"])


def test_replay_verifier_rejects_mixed_stage_after_rehash() -> None:
    payload = _bundle()
    payload["observations"][0]["research_stage"] = "COARSE_SCREEN"
    payload["observations"][1]["research_stage"] = "DEVELOPMENT_SCREEN"
    report = verify_bundle(_rehash(payload), project_root=PROJECT_ROOT)

    assert report["status"] == "FAIL"


@pytest.mark.parametrize(
    "boundary_patch",
    [
        {"development_only": False},
        {"production_promotion_allowed": True},
        {"canonical_queue_write_allowed": True},
    ],
)
def test_replay_verifier_rejects_production_boundary_after_rehash(
    boundary_patch: dict[str, bool],
) -> None:
    payload = _bundle()
    payload["boundary"].update(boundary_patch)
    report = verify_bundle(_rehash(payload), project_root=PROJECT_ROOT)

    assert report["status"] == "FAIL"
    assert "BOUNDARY_MISMATCH" in report["errors"]


@pytest.mark.parametrize(
    "path_factory",
    [
        lambda tmp_path: tmp_path / "absolute-outside",
        lambda tmp_path: tmp_path / "parent" / ".." / "traversal-outside",
    ],
)
def test_replay_cli_rejects_invalid_output_dir_before_write(
    tmp_path: Path,
    path_factory,
) -> None:
    output_dir = path_factory(tmp_path)
    resolved = output_dir.resolve(strict=False)
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/native_evidence_replay_bundle.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert not resolved.exists()
    assert "OUTPUT_DIR_" in completed.stderr
