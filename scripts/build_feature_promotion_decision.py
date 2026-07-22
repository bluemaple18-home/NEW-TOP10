#!/usr/bin/env python3
"""建立 FEATURE-PROMOTE-02 的 deterministic、fail-closed 決策 artifact。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "feature-promotion-decision.v1"
EVIDENCE_SCHEMA_VERSION = "feature-promotion-evidence.v1"
REVIEW_BASE_SHA = "b5a5e6394fa1bdb4f82124ffa5e1694844605f28"
REVIEW_CANDIDATE_SHA = "e057ff9e5256091c7825251c7a9e7e43ed324ebe"
REQUIRED = (
    ("sealed_oos", "sealed OOS report", "artifacts/sealed_oos_report_latest.json"),
    ("time_split_walk_forward", "time-split/walk-forward result", "artifacts/model_experiments/half_year_walkforward_validation_*.json"),
    ("same_universe_date_cost", "baseline/candidate same universe-date-cost comparison", "artifacts/model_experiments/feature_promotion_comparison_*.json"),
    ("leakage", "candidate leakage verification", "artifacts/model_experiments/feature_leakage_verification_*.json"),
    ("stability", "candidate stability evidence", "artifacts/model_experiments/feature_stability_*.json"),
    ("turnover", "candidate turnover evidence", "artifacts/model_experiments/feature_turnover_*.json"),
    ("drawdown", "candidate drawdown evidence", "artifacts/model_experiments/feature_drawdown_*.json"),
    ("concentration", "candidate concentration evidence", "artifacts/model_experiments/feature_concentration_*.json"),
    ("late_data", "late-data behavior evidence", "artifacts/model_experiments/feature_late_data_*.json"),
    ("data_manifest", "data manifest", "artifacts/model_experiments/feature_data_manifest_*.json"),
    ("candidate_manifest", "candidate manifest with code/data SHA", "artifacts/model_experiments/feature_candidate_manifest_*.json"),
    ("formal_code_review", "formal feature promotion code review", "docs/evidence/FEATURE-PROMOTE-02/review*.json"),
)
EVIDENCE_FIELDS = {
    "schema_version", "evidence_kind", "decision", "verdict", "base_sha", "candidate_sha",
    "data_sha256", "universe_id", "date_start", "date_end", "cost_model", "metrics",
    "thresholds", "freshness", "source_file_sha256",
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def is_repo_regular_file(path: Path) -> bool:
    """只列入 repo 內的實體 regular file；symlink 不可作 promotion evidence。"""
    try:
        return (
            not path.is_symlink()
            and path.is_file()
            and path.resolve().is_relative_to(PROJECT_ROOT.resolve())
        )
    except OSError:
        return False


def is_versioned_evidence(path: Path, evidence_kind: str) -> bool:
    """builder 只採信 closed schema 的 GO/PASS evidence，避免 placeholder 變成 GO。"""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        freshness = document.get("freshness")
        return (
            isinstance(document, dict)
            and set(document) == EVIDENCE_FIELDS
            and document["schema_version"] == EVIDENCE_SCHEMA_VERSION
            and document["evidence_kind"] == evidence_kind
            and document["decision"] == "GO"
            and document["verdict"] in {"GO", "PASS"}
            and document["base_sha"] == REVIEW_BASE_SHA
            and document["candidate_sha"] == REVIEW_CANDIDATE_SHA
            and isinstance(document["data_sha256"], str)
            and HEX64.fullmatch(document["data_sha256"])
            and isinstance(document["source_file_sha256"], str)
            and HEX64.fullmatch(document["source_file_sha256"])
            and isinstance(document["universe_id"], str)
            and isinstance(document["cost_model"], str)
            and isinstance(document["metrics"], dict)
            and bool(document["metrics"])
            and isinstance(document["thresholds"], dict)
            and isinstance(freshness, dict)
            and set(freshness) == {"as_of", "max_age_days"}
        )
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
        return False


def git_sha(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("SHA 必須是完整 40 字元 lowercase hexadecimal")
    return value


def evidence_row(key: str, label: str, pattern: str) -> dict[str, Any]:
    matches = sorted(PROJECT_ROOT.glob(pattern))
    files = [
        {"path": repo_path(path), "sha256": sha256(path)}
        for path in matches
        if is_repo_regular_file(path) and path.suffix == ".json" and is_versioned_evidence(path, key)
    ]
    return {"id": key, "label": label, "pattern": pattern, "present": bool(files), "files": files}


def build_payload(base_sha: str, candidate_sha: str) -> dict[str, Any]:
    if base_sha != REVIEW_BASE_SHA or candidate_sha != REVIEW_CANDIDATE_SHA:
        raise ValueError("promotion review SHA binding 不符合固定 review range")
    rows = [evidence_row(*item) for item in REQUIRED]
    graph_risk = {
        "graph_residual_tolerance_gt_1": {
            "status": "RISK",
            "source": "docs/evidence/REVIEW-TSKG-MFO-GRAPH-01/re-review-status.json",
            "attribution": "tolerance > 1 can suppress diffusion; must remain a promotion blocker/risk until bounded by contract",
        },
        "tpex": {
            "status": "KEEP_BLOCKED",
            "source": "docs/evidence/TSKG-MFO-THEME-01/verification.md",
            "attribution": "TWSE-only evidence; TPEx source/automation permission is not approved",
        },
    }
    missing = [row["id"] for row in rows if not row["present"]]
    source_files = sorted(
        (file for row in rows for file in row["files"]),
        key=lambda file: file["path"],
    )
    manifest_text = json.dumps(source_files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "NO_GO" if missing else "GO",
        "base_sha": git_sha(base_sha),
        "candidate_sha": git_sha(candidate_sha),
        "data_manifest_sha256": hashlib.sha256(manifest_text).hexdigest(),
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence": rows,
        "missing_required_evidence": missing,
        "attribution_and_risk": graph_risk,
        "contract": {
            "fail_closed": True,
            "checkpoint_pass_is_not_promotion": True,
            "production_mutation_allowed": False,
            "ranking_policy_mutation_allowed": False,
            "model_weight_mutation_allowed": False,
            "deploy_config_mutation_allowed": False,
            "reviewer_must_recompute": True,
        },
        "reproducible_commands": [
            "<repo-root>/.venv/bin/python scripts/build_feature_promotion_decision.py --help",
            "<repo-root>/.venv/bin/python scripts/verify_feature_promotion_decision.py --help",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 FEATURE-PROMOTE-02 deterministic promotion decision")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="artifacts/feature_promotion_decision_FEATURE-PROMOTE-02.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.base_sha, args.candidate_sha)
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "output": repo_path(output), "missing": payload["missing_required_evidence"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
