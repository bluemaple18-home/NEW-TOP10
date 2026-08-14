#!/usr/bin/env python3
"""驗證已通過的 native batch receipts 全部存在 Research Ledger。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.observation_ingest import ledger_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-verification", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch_verification.read_text(encoding="utf-8"))
    expected = set(batch.get("receipt_ids") or [])
    connection = duckdb.connect(str(args.ledger), read_only=True)
    try:
        found = {
            row[0] for row in connection.execute("SELECT receipt_id FROM run_receipts").fetchall()
            if row[0] in expected
        }
        snapshot = ledger_snapshot(connection)
    finally:
        connection.close()
    errors = [] if found == expected else ["LEDGER_BATCH_RECEIPT_SET_MISMATCH"]
    result = {
        "schema_version": "research-ledger-batch-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "research_batch_id": batch.get("research_batch_id"),
        "expected_receipt_ids": sorted(expected),
        "ledger_receipt_ids": sorted(found),
        "ledger_snapshot_hash": snapshot["snapshot_hash"],
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
