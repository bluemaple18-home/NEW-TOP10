#!/usr/bin/env python3
"""Verify Card B adaptive shadow queue projection and deterministic rebuild."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.adaptive_shadow_queue import (
    DEFAULT_BUNDLE,
    DEFAULT_CANONICAL_QUEUE,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_POLICY,
    PROJECT_ROOT,
    build_projection,
    load_json,
    verify_projection,
)
from app.research.contracts import content_hash


def _self_test() -> dict:
    errors: list[str] = []
    first = build_projection()
    second = build_projection()
    if first["projection_id"] != second["projection_id"]:
        errors.append("PROJECTION_ID_NOT_DETERMINISTIC")
    if first["semantic_hash"] != second["semantic_hash"]:
        errors.append("SEMANTIC_HASH_NOT_DETERMINISTIC")
    if [row["row_id"] for row in first["rows"]] != [row["row_id"] for row in second["rows"]]:
        errors.append("ROW_ORDER_NOT_DETERMINISTIC")
    report = verify_projection(first)
    if report["status"] != "PASS":
        errors.extend(report["errors"])

    bundle = load_json(DEFAULT_BUNDLE)
    with tempfile.TemporaryDirectory(prefix="asq-negative-") as tmp:
        tmp_path = Path(tmp)
        cases = []
        missing_cycle = copy.deepcopy(bundle)
        missing_cycle["cycles"].pop()
        missing_cycle["counts"]["cycles"] = 1
        missing_cycle["bundle_id"] = content_hash(missing_cycle, omit={"bundle_id", "generated_at"})
        cases.append(("MISSING_TWO_REAL_CYCLES", missing_cycle))

        sealed = copy.deepcopy(bundle)
        sealed["observations"][0]["sealed_usage_status"] = "SEALED"
        sealed["bundle_id"] = content_hash(sealed, omit={"bundle_id", "generated_at"})
        cases.append(("SEALED", sealed))

        unknown = copy.deepcopy(bundle)
        unknown["observations"][0]["sealed_usage_status"] = "UNKNOWN"
        unknown["bundle_id"] = content_hash(unknown, omit={"bundle_id", "generated_at"})
        cases.append(("UNKNOWN", unknown))

        single_lineage = copy.deepcopy(bundle)
        for row in single_lineage["learning_projection"]["matched_contrasts"]:
            row["lineage_id"] = single_lineage["learning_projection"]["matched_contrasts"][0]["lineage_id"]
        single_lineage["counts"]["distinct_lineages"] = 1
        single_lineage["bundle_id"] = content_hash(single_lineage, omit={"bundle_id", "generated_at"})
        cases.append(("SINGLE_LINEAGE", single_lineage))

        for name, payload in cases:
            path = tmp_path / f"{name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            candidate = build_projection(bundle_path=path)
            if candidate["status"] != "NO-GO" or candidate["rows"]:
                errors.append(f"NEGATIVE_FIXTURE_DID_NOT_FAIL_CLOSED:{name}")

        manifest = load_json(DEFAULT_MANIFEST)
        capacity = copy.deepcopy(manifest)
        capacity["capacity"]["status"] = "FAIL"
        capacity_path = tmp_path / "CAPACITY_DRIFT.json"
        capacity_path.write_text(
            json.dumps(capacity, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        capacity_candidate = build_projection(manifest_path=capacity_path)
        if "CAPACITY_NOT_PASS" not in capacity_candidate["reason_codes"]:
            errors.append("NEGATIVE_FIXTURE_DID_NOT_FAIL_CLOSED:CAPACITY_DRIFT")

        parity = copy.deepcopy(manifest)
        parity["parity"]["unchanged"] = False
        parity_path = tmp_path / "QUEUE_PARITY_DRIFT.json"
        parity_path.write_text(
            json.dumps(parity, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        parity_candidate = build_projection(manifest_path=parity_path)
        if "PARITY_DRIFT" not in parity_candidate["reason_codes"]:
            errors.append("NEGATIVE_FIXTURE_DID_NOT_FAIL_CLOSED:QUEUE_PARITY_DRIFT")

    return {
        "schema_version": "adaptive-shadow-queue-self-test.v1",
        "status": "PASS" if not errors else "FAIL",
        "projection_id": first.get("projection_id"),
        "semantic_hash": first.get("semantic_hash"),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--projection", type=Path, default=DEFAULT_OUTPUT_ROOT / "adaptive_shadow_queue_projection.json")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--canonical-queue", type=Path, default=DEFAULT_CANONICAL_QUEUE)
    args = parser.parse_args()
    if args.self_test:
        result = _self_test()
    elif args.projection.is_file():
        result = verify_projection(load_json(args.projection))
    else:
        result = verify_projection(
            build_projection(
                bundle_path=args.bundle,
                manifest_path=args.manifest,
                policy_path=args.policy,
                canonical_queue_path=args.canonical_queue,
                project_root=PROJECT_ROOT,
            )
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
