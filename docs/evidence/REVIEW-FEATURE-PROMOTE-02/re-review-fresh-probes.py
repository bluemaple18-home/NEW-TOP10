#!/usr/bin/env python3
"""FEATURE-PROMOTE-02 re-review fresh schema/semantic probes（繁中）。"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import scripts.build_feature_promotion_decision as builder
import scripts.verify_feature_promotion_decision as verifier


BASE = builder.REVIEW_BASE_SHA
CANDIDATE = builder.REVIEW_CANDIDATE_SHA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_document(kind: str) -> dict:
    today = dt.date.today().isoformat()
    return {
        "schema_version": builder.EVIDENCE_SCHEMA_VERSION,
        "evidence_kind": kind,
        "decision": "GO",
        "verdict": "PASS",
        "base_sha": BASE,
        "candidate_sha": CANDIDATE,
        "data_sha256": "a" * 64,
        "universe_id": "synthetic-universe",
        "date_start": "2026-01-01",
        "date_end": "2026-07-22",
        "cost_model": "synthetic-cost-v1",
        "metrics": {"metric": 1.0},
        "thresholds": {"metric": 0.0},
        "freshness": {"as_of": today, "max_age_days": 1},
        "source_file_sha256": "b" * 64,
    }


def refresh(payload: dict, root: Path) -> dict:
    refreshed = copy.deepcopy(payload)
    files = []
    for row in refreshed["evidence"]:
        for item in row["files"]:
            path = root / item["path"]
            item["sha256"] = sha(path)
            files.append({"path": item["path"], "sha256": item["sha256"]})
    manifest = json.dumps(sorted(files, key=lambda item: item["path"]), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    refreshed["data_manifest_sha256"] = hashlib.sha256(manifest).hexdigest()
    return refreshed


def result(name: str, rejected: bool, errors: list[str] | None = None) -> dict:
    return {"name": name, "rejected": rejected, "errors": errors or [], "pass": rejected}


def main() -> int:
    results: list[dict] = []
    actual_root = builder.PROJECT_ROOT
    actual_verifier_root = verifier.PROJECT_ROOT
    with tempfile.TemporaryDirectory(prefix="feature-promotion-re-review-") as temp:
        root = Path(temp)
        builder.PROJECT_ROOT = root
        verifier.PROJECT_ROOT = root
        for key, _, pattern in builder.REQUIRED:
            path = root / pattern.replace("*", f"{key}.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(valid_document(key), sort_keys=True), encoding="utf-8")
        payload = builder.build_payload(BASE, CANDIDATE)
        positive_errors = verifier.verify(payload)
        results.append({
            "name": "synthetic_complete_go_positive_control",
            "accepted": not positive_errors,
            "errors": positive_errors,
            "pass": not positive_errors,
        })
        sealed_path = root / payload["evidence"][0]["files"][0]["path"]
        sealed_document = json.loads(sealed_path.read_text(encoding="utf-8"))
        sealed_document["freshness"] = {"as_of": "2999-01-01", "max_age_days": 1}
        sealed_path.write_text(json.dumps(sealed_document, sort_keys=True), encoding="utf-8")
        builder_probe = builder.build_payload(BASE, CANDIDATE)
        results.append({
            "name": "builder_rejects_future_freshness",
            "decision": builder_probe["decision"],
            "pass": builder_probe["decision"] == "NO_GO",
        })
        sealed_document["freshness"] = valid_document("sealed_oos")["freshness"]
        sealed_path.write_text(json.dumps(sealed_document, sort_keys=True), encoding="utf-8")
        payload = builder.build_payload(BASE, CANDIDATE)

        def reject(name: str, mutate) -> None:
            candidate = copy.deepcopy(payload)
            mutate(candidate)
            errors = verifier.verify(candidate)
            results.append(result(name, bool(errors), errors))

        reject("wrong_base_sha", lambda p: p.__setitem__("base_sha", "0" * 40))
        reject("wrong_candidate_sha", lambda p: p.__setitem__("candidate_sha", "f" * 40))
        reject("decision_tamper", lambda p: p.__setitem__("decision", "NO_GO"))
        reject("missing_list_tamper", lambda p: p.__setitem__("missing_required_evidence", ["sealed_oos"]))
        reject("data_manifest_hash_tamper", lambda p: p.__setitem__("data_manifest_sha256", "0" * 64))
        reject("top_level_unknown", lambda p: p.__setitem__("unknown", True))
        reject("top_level_missing", lambda p: p.pop("contract"))
        reject("top_level_type", lambda p: p.__setitem__("evidence", {}))

        reject("row_unknown", lambda p: p["evidence"][0].__setitem__("unknown", True))
        reject("row_missing", lambda p: p["evidence"][0].pop("label"))
        reject("row_type", lambda p: p["evidence"].__setitem__(0, "bad-row"))
        reject("duplicate_id", lambda p: p["evidence"].__setitem__(1, dict(p["evidence"][0])))
        reject("unknown_id", lambda p: p["evidence"][0].__setitem__("id", "unknown"))
        reject("file_unknown", lambda p: p["evidence"][0]["files"][0].__setitem__("unknown", True))
        reject("file_missing", lambda p: p["evidence"][0]["files"][0].pop("sha256"))
        reject("file_type", lambda p: p["evidence"][0].__setitem__("files", "bad-files"))

        for key in (item[0] for item in builder.REQUIRED):
            def mutate_semantic(p, key=key):
                row = next(row for row in p["evidence"] if row["id"] == key)
                path = root / row["files"][0]["path"]
                document = json.loads(path.read_text(encoding="utf-8"))
                document["decision"] = "NO_GO"
                path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
                refreshed = refresh(p, root)
                p["evidence"] = refreshed["evidence"]
                p["data_manifest_sha256"] = refreshed["data_manifest_sha256"]
                return p
            reject(f"semantic_no_go:{key}", mutate_semantic)

        for key, field, value in (
            ("placeholder", "metrics", {}),
            ("semantic_no_go", "decision", "NO_GO"),
            ("semantic_bad_verdict", "verdict", "FAIL"),
            ("semantic_wrong_kind", "evidence_kind", "other"),
            ("wrong_data_sha", "data_sha256", "0" * 64),
            ("wrong_evidence_base", "base_sha", "0" * 40),
            ("wrong_evidence_candidate", "candidate_sha", "f" * 40),
            ("stale_freshness", "freshness", {"as_of": "2020-01-01", "max_age_days": 1}),
            ("future_freshness", "freshness", {"as_of": "2999-01-01", "max_age_days": 1}),
            ("invalid_freshness", "freshness", {"as_of": "not-a-date", "max_age_days": -1}),
        ):
            def mutate(p, field=field, value=value):
                path = root / p["evidence"][0]["files"][0]["path"]
                document = json.loads(path.read_text(encoding="utf-8"))
                document[field] = value
                path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
                p["evidence"][0]["files"][0]["sha256"] = sha(path)
                return p
            reject(key, mutate)

        reject("absolute_path", lambda p: p["evidence"][0]["files"][0].__setitem__("path", str((root / "outside.json").resolve())))
        reject("traversal_path", lambda p: p["evidence"][0]["files"][0].__setitem__("path", "../outside.json"))
        outside = root.parent / "feature-promotion-outside.json"
        outside.write_text("outside", encoding="utf-8")
        reject("out_of_repo_path", lambda p: p["evidence"][0]["files"][0].__setitem__("path", str(outside)))
        link = root / "link.json"
        link.symlink_to(outside)
        reject("symlink_path", lambda p: p["evidence"][0]["files"][0].__setitem__("path", "link.json"))
        reject("pattern_drift", lambda p: p["evidence"][0]["files"][0].__setitem__("path", p["evidence"][1]["files"][0]["path"]))
        reject("source_hash_tamper", lambda p: p["evidence"][0]["files"][0].__setitem__("sha256", "0" * 64))

        builder.PROJECT_ROOT = actual_root
        verifier.PROJECT_ROOT = actual_verifier_root
        actual = builder.build_payload(BASE, CANDIDATE)
        actual_errors = verifier.verify(actual)
        results.append({
            "name": "actual_repo_no_go_12_missing_risk_attribution",
            "decision": actual["decision"],
            "missing_count": len(actual["missing_required_evidence"]),
            "verify_errors": actual_errors,
            "graph": actual["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"],
            "tpex": actual["attribution_and_risk"]["tpex"]["status"],
            "pass": actual["decision"] == "NO_GO" and len(actual["missing_required_evidence"]) == 12 and not actual_errors and actual["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"] == "RISK" and actual["attribution_and_risk"]["tpex"]["status"] == "KEEP_BLOCKED",
        })
    print(json.dumps({"all_pass": all(item["pass"] for item in results), "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item["pass"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
