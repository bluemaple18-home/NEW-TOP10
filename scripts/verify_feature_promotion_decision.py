#!/usr/bin/env python3
"""驗證 FEATURE-PROMOTE-02 decision artifact，缺 evidence 時保持 NO_GO。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_feature_promotion_decision import REQUIRED, SCHEMA_VERSION


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    for field in ("base_sha", "candidate_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get(field) or "")):
            errors.append(field)
    rows = payload.get("evidence")
    if not isinstance(rows, list) or {row.get("id") for row in rows} != {item[0] for item in REQUIRED}:
        errors.append("required_evidence_rows")
        return errors
    for row in rows:
        if row.get("present") is not bool(row.get("files")):
            errors.append(f"presence:{row.get('id')}")
        for item in row.get("files", []):
            path = PROJECT_ROOT / str(item.get("path") or "")
            if not path.is_file() or sha256(path) != item.get("sha256"):
                errors.append(f"source_hash:{row.get('id')}")
    missing = sorted(row["id"] for row in rows if not row["present"])
    if sorted(payload.get("missing_required_evidence", [])) != missing:
        errors.append("missing_evidence_recomputed")
    expected = "NO_GO" if missing else "GO"
    if payload.get("decision") != expected:
        errors.append("decision_not_fail_closed")
    risks = payload.get("attribution_and_risk", {})
    if risks.get("graph_residual_tolerance_gt_1", {}).get("status") != "RISK":
        errors.append("graph_residual_risk_missing")
    if risks.get("tpex", {}).get("status") != "KEEP_BLOCKED":
        errors.append("tpex_keep_blocked_missing")
    contract = payload.get("contract", {})
    for field in ("fail_closed", "checkpoint_pass_is_not_promotion", "reviewer_must_recompute"):
        if contract.get(field) is not True:
            errors.append(f"contract:{field}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證 FEATURE-PROMOTE-02 decision artifact")
    parser.add_argument("--decision", required=True)
    args = parser.parse_args()
    path = Path(args.decision)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = verify(payload)
    if errors:
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps({"status": "OK", "decision": payload["decision"], "missing": payload["missing_required_evidence"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
