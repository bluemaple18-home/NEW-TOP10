from __future__ import annotations

import copy
import json
from pathlib import Path

from app.research.native_evidence_replay import verify_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = (
    PROJECT_ROOT
    / "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json"
)


def _bundle() -> dict:
    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


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
