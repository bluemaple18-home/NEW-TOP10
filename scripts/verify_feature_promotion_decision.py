#!/usr/bin/env python3
"""以 closed schema 重算 FEATURE-PROMOTE-02 decision，所有錯誤均 typed FAILED。"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_feature_promotion_decision import (  # noqa: E402
    EVIDENCE_SCHEMA_VERSION,
    REQUIRED,
    REVIEW_BASE_SHA,
    REVIEW_CANDIDATE_SHA,
    SCHEMA_VERSION,
)

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
TOP_LEVEL = {
    "schema_version", "evidence_schema_version", "decision", "base_sha", "candidate_sha",
    "data_manifest_sha256", "evidence", "missing_required_evidence", "attribution_and_risk",
    "contract", "reproducible_commands",
}
ROW_FIELDS = {"id", "label", "pattern", "present", "files"}
FILE_FIELDS = {"path", "sha256"}
EVIDENCE_FIELDS = {
    "schema_version", "evidence_kind", "decision", "verdict", "base_sha", "candidate_sha",
    "data_sha256", "universe_id", "date_start", "date_end", "cost_model", "metrics",
    "thresholds", "freshness", "source_file_sha256",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def error(errors: list[str], name: str) -> None:
    errors.append(name)


def repo_regular_file(relative: object) -> tuple[Path | None, str | None]:
    """拒絕 absolute、traversal、out-of-repo、symlink 與非 regular file。"""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None, "path_not_portable"
    candidate = PROJECT_ROOT / Path(relative)
    try:
        lexical = candidate.relative_to(PROJECT_ROOT)
        real = candidate.resolve(strict=True)
        real.relative_to(PROJECT_ROOT.resolve())
    except (OSError, ValueError):
        return None, "path_out_of_repo"
    current = PROJECT_ROOT
    for part in lexical.parts:
        current /= part
        if current.is_symlink():
            return None, "path_symlink"
    if not real.is_file() or not candidate.is_file():
        return None, "path_not_regular_file"
    return candidate, None


def valid_evidence_file(path: Path, row_id: str, errors: list[str]) -> tuple[tuple[str, str, str, str, str] | None, bool]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        error(errors, f"evidence_schema:{row_id}")
        return None, False
    if not isinstance(document, dict) or set(document) != EVIDENCE_FIELDS:
        error(errors, f"evidence_schema:{row_id}")
        return None, False
    if document["schema_version"] != EVIDENCE_SCHEMA_VERSION or document["evidence_kind"] != row_id:
        error(errors, f"evidence_kind:{row_id}")
    if document["decision"] != "GO" or document["verdict"] not in {"PASS", "GO"}:
        error(errors, f"evidence_verdict:{row_id}")
    if document["base_sha"] != REVIEW_BASE_SHA or document["candidate_sha"] != REVIEW_CANDIDATE_SHA:
        error(errors, f"evidence_identity:{row_id}")
    for key in ("data_sha256", "source_file_sha256"):
        if not isinstance(document[key], str) or not HEX64.fullmatch(document[key]):
            error(errors, f"evidence_hash:{row_id}")
    if not all(isinstance(document[key], str) and document[key] for key in ("universe_id", "cost_model")):
        error(errors, f"evidence_identity:{row_id}")
    if not all(isinstance(document[key], str) and DATE.fullmatch(document[key]) for key in ("date_start", "date_end")):
        error(errors, f"evidence_dates:{row_id}")
    elif document["date_start"] > document["date_end"]:
        error(errors, f"evidence_dates:{row_id}")
    if not isinstance(document["metrics"], dict) or not document["metrics"] or not isinstance(document["thresholds"], dict):
        error(errors, f"evidence_metrics:{row_id}")
    freshness = document["freshness"]
    if not isinstance(freshness, dict) or set(freshness) != {"as_of", "max_age_days"}:
        error(errors, f"evidence_freshness:{row_id}")
    else:
        as_of = freshness["as_of"]
        max_age = freshness["max_age_days"]
        try:
            age = (dt.date.today() - dt.date.fromisoformat(as_of)).days
            if not isinstance(as_of, str) or not DATE.fullmatch(as_of) or not isinstance(max_age, int) or max_age < 0 or age < 0 or age > max_age:
                raise ValueError
        except (TypeError, ValueError):
            error(errors, f"evidence_freshness:{row_id}")
    identity = (document["universe_id"], document["date_start"], document["date_end"], document["cost_model"])
    return identity, True


def verify(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL:
        return ["top_level_schema"]
    if payload["schema_version"] != SCHEMA_VERSION or payload["evidence_schema_version"] != EVIDENCE_SCHEMA_VERSION:
        error(errors, "schema_version")
    if payload["base_sha"] != REVIEW_BASE_SHA:
        error(errors, "base_sha_binding")
    if payload["candidate_sha"] != REVIEW_CANDIDATE_SHA:
        error(errors, "candidate_sha_binding")
    rows = payload["evidence"]
    expected = {item[0]: item for item in REQUIRED}
    if not isinstance(rows, list) or len(rows) != len(REQUIRED) or any(not isinstance(row, dict) for row in rows):
        return sorted(set(errors + ["required_evidence_rows"]))
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        error(errors, "required_evidence_rows")
    identities: set[tuple[str, str, str, str]] = set()
    source_files: list[dict[str, str]] = []
    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, str) or row_id not in expected or set(row) != ROW_FIELDS:
            error(errors, f"row_schema:{row_id}")
            continue
        _, label, pattern = expected[row_id]
        if row["label"] != label or row["pattern"] != pattern or not isinstance(row["present"], bool) or not isinstance(row["files"], list):
            error(errors, f"row_schema:{row_id}")
            continue
        if row["present"] is not bool(row["files"]):
            error(errors, f"presence:{row_id}")
        for item in row["files"]:
            if not isinstance(item, dict) or set(item) != FILE_FIELDS:
                error(errors, f"file_schema:{row_id}")
                continue
            path, path_error = repo_regular_file(item["path"])
            if path_error or path is None:
                error(errors, f"{path_error}:{row_id}")
                continue
            relative = str(path.relative_to(PROJECT_ROOT))
            if not fnmatch.fnmatchcase(relative, pattern):
                error(errors, f"pattern:{row_id}")
            if not isinstance(item["sha256"], str) or not HEX64.fullmatch(item["sha256"]) or sha256(path) != item["sha256"]:
                error(errors, f"source_hash:{row_id}")
            identity, valid = valid_evidence_file(path, row_id, errors)
            if valid and identity:
                identities.add(identity)
            source_files.append({"path": relative, "sha256": item["sha256"]})
    if len(identities) > 1:
        error(errors, "evidence_identity_mismatch")
    manifest = json.dumps(sorted(source_files, key=lambda item: item["path"]), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if payload["data_manifest_sha256"] != hashlib.sha256(manifest).hexdigest():
        error(errors, "data_manifest_binding")
    missing = sorted(row["id"] for row in rows if isinstance(row, dict) and row.get("present") is False)
    if sorted(payload["missing_required_evidence"]) != missing:
        error(errors, "missing_evidence_recomputed")
    expected_decision = "NO_GO" if missing else "GO"
    if payload["decision"] != expected_decision:
        error(errors, "decision_not_fail_closed")
    risks = payload["attribution_and_risk"]
    if not isinstance(risks, dict) or risks.get("graph_residual_tolerance_gt_1", {}).get("status") != "RISK" or risks.get("tpex", {}).get("status") != "KEEP_BLOCKED":
        error(errors, "risk_attribution")
    contract = payload["contract"]
    required_contract = ("fail_closed", "checkpoint_pass_is_not_promotion", "reviewer_must_recompute")
    if not isinstance(contract, dict) or any(contract.get(field) is not True for field in required_contract):
        error(errors, "contract")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證 FEATURE-PROMOTE-02 feature promotion decision")
    parser.add_argument("--decision", required=True)
    args = parser.parse_args()
    try:
        path = Path(args.decision)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = verify(payload)
    except Exception as exc:  # noqa: BLE001 - CLI contract 必須回傳 typed FAILED
        errors = [f"input_failure:{type(exc).__name__}"]
    if errors:
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps({"status": "OK", "decision": payload["decision"], "missing": payload["missing_required_evidence"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
