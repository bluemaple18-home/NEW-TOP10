#!/usr/bin/env python3
"""Repair 2/2 final freshness and decision_as_of probes（繁中）。"""

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
DECISION_AS_OF = "2026-07-22"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(kind: str, as_of: str = "2026-07-21", start: str = "2026-01-01", end: str = DECISION_AS_OF) -> dict:
    return {
        "schema_version": builder.EVIDENCE_SCHEMA_VERSION,
        "evidence_kind": kind,
        "decision": "GO",
        "verdict": "PASS",
        "base_sha": BASE,
        "candidate_sha": CANDIDATE,
        "data_sha256": "a" * 64,
        "universe_id": "synthetic-universe",
        "date_start": start,
        "date_end": end,
        "cost_model": "synthetic-cost-v1",
        "metrics": {"metric": 1.0},
        "thresholds": {"metric": 0.0},
        "freshness": {"as_of": as_of, "max_age_days": 1},
        "source_file_sha256": "b" * 64,
    }


def manifest(payload: dict, root: Path) -> dict:
    output = copy.deepcopy(payload)
    files = []
    for row in output["evidence"]:
        for item in row["files"]:
            path = root / item["path"]
            item["sha256"] = file_sha(path)
            files.append({"path": item["path"], "sha256": item["sha256"]})
    raw = json.dumps(sorted(files, key=lambda item: item["path"]), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    output["data_manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    return output


def main() -> int:
    results: list[dict] = []
    old_builder_root, old_verifier_root = builder.PROJECT_ROOT, verifier.PROJECT_ROOT
    with tempfile.TemporaryDirectory(prefix="feature-promotion-final-review-") as temp:
        root = Path(temp)
        builder.PROJECT_ROOT = root
        verifier.PROJECT_ROOT = root
        paths: dict[str, Path] = {}

        def reset(as_of: str = "2026-07-21", start: str = "2026-01-01", end: str = DECISION_AS_OF) -> None:
            paths.clear()
            for kind, _, pattern in builder.REQUIRED:
                path = root / pattern.replace("*", f"{kind}.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(document(kind, as_of, start, end), sort_keys=True), encoding="utf-8")
                paths[kind] = path

        def build(as_of: str = DECISION_AS_OF) -> dict:
            return builder.build_payload(BASE, CANDIDATE, as_of)

        reset()
        positive = build()
        results.append({"name": "synthetic_go_exact_boundary", "decision": positive["decision"], "verify": verifier.verify(positive), "pass": positive["decision"] == "GO" and not verifier.verify(positive)})

        for name, kwargs in (
            ("future_as_of", {"as_of": "2026-07-23"}),
            ("stale_as_of", {"as_of": "2026-07-20"}),
            ("invalid_as_of", {"as_of": "2026-02-30"}),
            ("reversed_interval", {"start": "2026-07-22", "end": "2026-07-21"}),
            ("over_window_interval", {"start": "2025-07-21"}),
            ("future_interval_end", {"end": "2026-07-23"}),
        ):
            reset(**kwargs)
            payload = build()
            results.append({"name": f"builder_{name}", "decision": payload["decision"], "pass": payload["decision"] == "NO_GO"})

        reset()
        for name, value in (
            ("decision_as_of_future", "2026-07-23"),
            ("decision_as_of_invalid", "2026-02-30"),
            ("decision_as_of_timezone", "2026-07-22T00:00:00Z"),
        ):
            try:
                build(value)
                results.append({"name": f"builder_{name}", "rejected": False, "pass": False})
            except ValueError:
                results.append({"name": f"builder_{name}", "rejected": True, "pass": True})

        reset()
        valid = build()
        for name, mutate in (
            ("verifier_decision_as_of_future", lambda p: p.__setitem__("decision_as_of", "2026-07-23")),
            ("verifier_decision_as_of_invalid", lambda p: p.__setitem__("decision_as_of", "2026-02-30")),
            ("verifier_decision_as_of_tamper", lambda p: p.__setitem__("decision_as_of", "2026-07-21")),
            ("verifier_decision_as_of_hash_tamper", lambda p: p.__setitem__("decision_as_of_sha256", "0" * 64)),
        ):
            candidate = copy.deepcopy(valid)
            mutate(candidate)
            errors = verifier.verify(candidate)
            results.append({"name": name, "errors": errors, "pass": bool(errors)})

        for name, as_of, start, end in (
            ("verifier_over_age", "2026-07-20", "2026-01-01", DECISION_AS_OF),
            ("verifier_future_evidence", "2026-07-23", "2026-01-01", DECISION_AS_OF),
            ("verifier_invalid_evidence_date", "2026-02-30", "2026-01-01", DECISION_AS_OF),
            ("verifier_reversed_interval", "2026-07-21", "2026-07-22", "2026-07-21"),
        ):
            reset(as_of, start, end)
            candidate = manifest(valid, root)
            item_path = paths["sealed_oos"]
            item_path.write_text(json.dumps(document("sealed_oos", as_of, start, end), sort_keys=True), encoding="utf-8")
            candidate = manifest(candidate, root)
            errors = verifier.verify(candidate)
            results.append({"name": name, "errors": errors, "pass": bool(errors)})

        builder.PROJECT_ROOT = old_builder_root
        verifier.PROJECT_ROOT = old_verifier_root
        actual = builder.build_payload(BASE, CANDIDATE, DECISION_AS_OF)
        results.append({
            "name": "actual_repo_no_go",
            "decision": actual["decision"],
            "missing_count": len(actual["missing_required_evidence"]),
            "graph": actual["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"],
            "tpex": actual["attribution_and_risk"]["tpex"]["status"],
            "pass": actual["decision"] == "NO_GO" and len(actual["missing_required_evidence"]) == 12 and actual["attribution_and_risk"]["graph_residual_tolerance_gt_1"]["status"] == "RISK" and actual["attribution_and_risk"]["tpex"]["status"] == "KEEP_BLOCKED" and not verifier.verify(actual),
        })
    print(json.dumps({"all_pass": all(item["pass"] for item in results), "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item["pass"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
