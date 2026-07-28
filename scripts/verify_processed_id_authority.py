#!/usr/bin/env python3
"""獨立比較 research-map 與 weekend inventory 的 processed-ID authority。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fog_authority_contracts import (
    AuthorityContractError,
    read_json_authority,
    verify_declared_source_roles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPLETED_STATES = {"COMPLETED", "PARTIAL_NO_MORE_WORK"}


def _processed_ids(payload: dict[str, Any]) -> tuple[set[str], list[str]]:
    rows = payload.get("processed")
    if not isinstance(rows, list):
        return set(), ["PROCESSED_SCHEMA_REJECT"]
    ids: list[str] = []
    reasons: list[str] = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"topic_id", "status"}
            or not isinstance(row.get("topic_id"), str)
            or not row["topic_id"]
            or row.get("status") not in COMPLETED_STATES
        ):
            reasons.append("PROCESSED_ROW_REJECT")
            continue
        ids.append(row["topic_id"])
    if len(ids) != len(set(ids)):
        reasons.append("PROCESSED_ID_DUPLICATE")
    return set(ids), reasons


def verify_processed_artifacts(
    *,
    root: str | Path,
    research_map_path: str,
    inventory_path: str,
    research_map_source_roles: dict[str, str],
    inventory_source_roles: dict[str, str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    try:
        research_map = read_json_authority(root, research_map_path)
        inventory = read_json_authority(root, inventory_path)
    except AuthorityContractError as error:
        return {
            "ok": False,
            "reason_codes": [error.reason_code],
            "difference": {"map_only": [], "inventory_only": []},
            "artifacts_share_processed_source": False,
        }
    map_ids, map_reasons = _processed_ids(research_map)
    inventory_ids, inventory_reasons = _processed_ids(inventory)
    reason_codes.extend(map_reasons)
    reason_codes.extend(inventory_reasons)
    map_lineage = verify_declared_source_roles(
        root=root,
        declared=research_map.get("source_hashes"),
        expected_roles=research_map_source_roles,
    )
    inventory_lineage = verify_declared_source_roles(
        root=root,
        declared=inventory.get("source_hashes"),
        expected_roles=inventory_source_roles,
    )
    reason_codes.extend(map_lineage["reason_codes"])
    reason_codes.extend(inventory_lineage["reason_codes"])
    shared_sources = bool(
        set(map_lineage["resolved_paths"]) & set(inventory_lineage["resolved_paths"])
    )
    if shared_sources:
        reason_codes.append("PROCESSED_ARTIFACTS_SHARE_SOURCE")
    map_only = sorted(map_ids - inventory_ids)[:20]
    inventory_only = sorted(inventory_ids - map_ids)[:20]
    if map_only or inventory_only:
        reason_codes.append("PROCESSED_ID_SET_MISMATCH")
    return {
        "ok": not reason_codes,
        "reason_codes": sorted(set(reason_codes)),
        "difference": {
            "map_only": map_only,
            "inventory_only": inventory_only,
        },
        "map_count": len(map_ids),
        "inventory_count": len(inventory_ids),
        "artifacts_share_processed_source": shared_sources,
        "research_map": {
            "path": research_map_path,
            "source_lineage": map_lineage,
        },
        "inventory": {
            "path": inventory_path,
            "source_lineage": inventory_lineage,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify processed-ID authority")
    parser.add_argument("--research-map", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--research-map-source-role", action="append", default=[])
    parser.add_argument("--inventory-source-role", action="append", default=[])
    return parser.parse_args()


def _parse_roles(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        role, separator, path = value.partition("=")
        if not separator or not role or not path or role in result:
            raise ValueError(f"無效 role=path：{value}")
        result[role] = path
    return result


def main() -> int:
    args = parse_args()
    result = verify_processed_artifacts(
        root=PROJECT_ROOT,
        research_map_path=args.research_map,
        inventory_path=args.inventory,
        research_map_source_roles=_parse_roles(args.research_map_source_role),
        inventory_source_roles=_parse_roles(args.inventory_source_role),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
