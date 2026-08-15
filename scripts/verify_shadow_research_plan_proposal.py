#!/usr/bin/env python3
"""重算並驗證 shadow research plan proposal。"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.shadow_plan_proposal import (
    DEFAULT_CATALOG,
    DEFAULT_OUTPUT_RELATIVE,
    DEFAULT_POLICY,
    DEFAULT_PROJECTION,
    DEFAULT_VERIFICATION_RELATIVE,
    PROJECT_ROOT,
    ProposalBoundaryError,
    authorize_output_path,
    build_proposal,
    encode_proposal,
    load_json,
    validate_source_documents,
    verify_proposal,
    write_deterministic_output,
)


def self_test() -> dict:
    errors: list[str] = []
    first = build_proposal()
    second = build_proposal()
    if encode_proposal(first) != encode_proposal(second):
        errors.append("TWO_RUN_BYTES_DIFFER")
    report = verify_proposal(first)
    if report["status"] != "PASS":
        errors.extend(report["errors"])

    projection = load_json(DEFAULT_PROJECTION)
    policy = load_json(DEFAULT_POLICY)
    catalog = load_json(DEFAULT_CATALOG)
    negative_cases = {
        "NON_HIGH": ("priority_band", "OBSERVE", "SOURCE_ROW_0:PRIORITY_NOT_HIGH"),
        "UNSUPPORTED_ACTION": ("action", "EXECUTE_RESEARCH", "SOURCE_ROW_0:ACTION_NOT_SUPPORTED"),
    }
    for name, (field, value, expected_error) in negative_cases.items():
        mutated = copy.deepcopy(projection)
        mutated["rows"][0][field] = value
        observed = validate_source_documents(mutated, policy, catalog)
        if expected_error not in observed:
            errors.append(f"NEGATIVE_FIXTURE_NOT_CLOSED:{name}")

    return {
        "schema_version": "shadow-research-plan-proposal-self-test.v1",
        "status": "PASS" if not errors else "FAIL",
        "proposal_set_id": first.get("proposal_set_id"),
        "two_run_byte_equality": encode_proposal(first) == encode_proposal(second),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--proposal", type=Path, default=DEFAULT_OUTPUT_RELATIVE)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        else:
            proposal_path = authorize_output_path(
                args.proposal,
                expected_relative=DEFAULT_OUTPUT_RELATIVE,
                project_root=PROJECT_ROOT,
            )
            result = verify_proposal(load_json(proposal_path))
        if args.report_output is not None:
            report_path = authorize_output_path(
                args.report_output,
                expected_relative=DEFAULT_VERIFICATION_RELATIVE,
                project_root=PROJECT_ROOT,
            )
            write_deterministic_output(report_path, result)
    except (ProposalBoundaryError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"status": "FAIL", "reason_code": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
