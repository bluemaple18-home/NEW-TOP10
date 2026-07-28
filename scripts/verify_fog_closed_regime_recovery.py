#!/usr/bin/env python3
"""聚合 processed-ID、source lineage、trusted baseline 與 receipt gate。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fog_authority_contracts import (
    PROTECTED_PRODUCTION_ROLES,
    read_json_authority,
    verify_trusted_baseline,
)
from scripts.verify_closed_regime_runtime import verify_receipt
from scripts.verify_processed_id_authority import verify_processed_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def verify_recovery(
    *,
    root: str | Path,
    research_map_path: str,
    inventory_path: str,
    research_map_source_roles: dict[str, str],
    inventory_source_roles: dict[str, str],
    baseline_path: str,
    expected_source_identity: str,
    receipt_path: str,
    verification_time_utc: str | None = None,
    protected_roles: dict[str, str] = PROTECTED_PRODUCTION_ROLES,
) -> dict[str, Any]:
    processed = verify_processed_artifacts(
        root=root,
        research_map_path=research_map_path,
        inventory_path=inventory_path,
        research_map_source_roles=research_map_source_roles,
        inventory_source_roles=inventory_source_roles,
    )
    baseline = verify_trusted_baseline(
        root=root,
        baseline_path=baseline_path,
        protected_roles=protected_roles,
        expected_source_identity=expected_source_identity,
    )
    try:
        receipt_payload = read_json_authority(root, receipt_path)
        runtime = verify_receipt(
            receipt_payload,
            project_root=root,
            verification_time_utc=verification_time_utc,
        )
    except Exception as error:
        runtime = {
            "ok": False,
            "reason_codes": [
                error.reason_code
                if hasattr(error, "reason_code")
                else "RECEIPT_AUTHORITY_REJECT"
            ],
        }
    return {
        "ok": processed["ok"] and baseline["ok"] and runtime["ok"],
        "status": (
            "RECOVERY_AUTHORITY_VERIFIED"
            if processed["ok"] and baseline["ok"] and runtime["ok"]
            else "RECOVERY_DENIED"
        ),
        "processed_id_authority": processed,
        "trusted_baseline_authority": baseline,
        "runtime_receipt_authority": runtime,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify fog closed-regime recovery")
    parser.add_argument("--research-map", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--research-map-source-role", action="append", default=[])
    parser.add_argument("--inventory-source-role", action="append", default=[])
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output")
    return parser.parse_args()


def _roles(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        role, separator, path = value.partition("=")
        if not separator or not role or not path or role in result:
            raise ValueError(f"無效 role=path：{value}")
        result[role] = path
    return result


def main() -> int:
    args = parse_args()
    result = verify_recovery(
        root=PROJECT_ROOT,
        research_map_path=args.research_map,
        inventory_path=args.inventory,
        research_map_source_roles=_roles(args.research_map_source_role),
        inventory_source_roles=_roles(args.inventory_source_role),
        baseline_path=args.baseline,
        expected_source_identity=args.source_identity,
        receipt_path=args.receipt,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        output = PROJECT_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
