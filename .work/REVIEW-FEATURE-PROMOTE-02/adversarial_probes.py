#!/usr/bin/env python3
"""Reviewer-owned FEATURE-PROMOTE-02 fail-closed probes（繁中紀錄）。"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_feature_promotion_decision import build_payload
from scripts.verify_feature_promotion_decision import verify


PYTHON = Path("/Users/mattkuo/TOP10new/.venv/bin/python")
BASE = "b5a5e6394fa1bdb4f82124ffa5e1694844605f28"
CANDIDATE = "e057ff9e5256091c7825251c7a9e7e43ed324ebe"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_go(source: Path) -> dict:
    payload = build_payload(BASE, CANDIDATE)
    for row in payload["evidence"]:
        row["present"] = True
        row["files"] = [{"path": str(source), "sha256": digest(source)}]
    payload["missing_required_evidence"] = []
    payload["decision"] = "GO"
    return payload


def check(name: str, payload: object, must_reject: bool) -> dict:
    try:
        errors = verify(payload)  # type: ignore[arg-type]
        rejected = bool(errors)
        return {"name": name, "errors": errors, "rejected": rejected, "pass": rejected == must_reject}
    except Exception as exc:
        return {"name": name, "exception": f"{type(exc).__name__}: {exc}", "rejected": True, "pass": must_reject}


def cli_reject(name: str, content: str, path: Path) -> dict:
    path.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [str(PYTHON), "scripts/verify_feature_promotion_decision.py", "--decision", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {"name": name, "returncode": result.returncode, "stdout": result.stdout.strip(), "pass": result.returncode != 0}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="feature-promote-probes-") as temp:
        temp_root = Path(temp)
        outside = temp_root / "outside.json"
        outside.write_text("placeholder", encoding="utf-8")
        source = ROOT / "docs/tasks/2026-07-22_REVIEW-FEATURE-PROMOTE-02.md"
        payload = fake_go(source)
        results = [
            cli_reject("empty_json", "{}", temp_root / "empty.json"),
            cli_reject("placeholder_json", '{"decision":"GO"}', temp_root / "placeholder.json"),
            check("wrong_candidate_sha", {**copy.deepcopy(payload), "candidate_sha": "0" * 40}, True),
            check("wrong_base_sha", {**copy.deepcopy(payload), "base_sha": "1" * 40}, True),
            check("wrong_candidate_data_identity", {**copy.deepcopy(payload), "candidate_sha": "f" * 40}, True),
            check("no_go_review_file_is_accepted", payload, True),
            check("stale_manifest_is_accepted", {**copy.deepcopy(payload), "data_manifest_sha256": "0" * 64}, True),
        ]

        unknown = copy.deepcopy(payload)
        unknown["evidence"].append(copy.deepcopy(unknown["evidence"][0]))
        unknown["evidence"][-1]["id"] = "unknown"
        results.append(check("unknown_id", unknown, True))

        missing = copy.deepcopy(payload)
        missing["evidence"] = missing["evidence"][1:]
        results.append(check("missing_id", missing, True))

        wrong_type = copy.deepcopy(payload)
        wrong_type["evidence"][0]["files"] = "not-a-list"
        results.append(check("wrong_type_files", wrong_type, True))

        duplicate = copy.deepcopy(payload)
        duplicate["evidence"].append(copy.deepcopy(duplicate["evidence"][0]))
        results.append(check("duplicate_id", duplicate, True))

        traversal = fake_go(outside)
        traversal["evidence"][0]["files"][0]["path"] = str(outside)
        results.append(check("out_of_repo_absolute_path", traversal, True))

        symlink = temp_root / "repo-link.json"
        symlink.symlink_to(outside)
        linked = fake_go(symlink)
        results.append(check("symlink_out_of_repo", linked, True))

        tampered_hash = copy.deepcopy(payload)
        tampered_hash["evidence"][0]["files"][0]["sha256"] = "0" * 64
        results.append(check("tampered_source_hash", tampered_hash, True))
        results.append(check("tampered_decision_flip", {**copy.deepcopy(payload), "decision": "NO_GO"}, True))

        print(json.dumps({"results": results, "all_pass": all(item["pass"] for item in results)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
