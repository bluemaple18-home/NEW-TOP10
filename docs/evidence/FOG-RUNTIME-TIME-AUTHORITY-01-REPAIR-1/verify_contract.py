#!/usr/bin/env python3
"""唯讀驗證 receipt v3 architecture contract。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "docs/architecture/fog_runtime_receipt_v3.schema.json"


def resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"只允許 local ref：{reference}")
    node: Any = root
    for part in reference[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise TypeError(f"ref不是 schema object：{reference}")
    return node


def validate(
    root: dict[str, Any],
    schema: dict[str, Any],
    value: Any,
    path: str = "$",
) -> list[str]:
    if "$ref" in schema:
        return validate(root, resolve_ref(root, schema["$ref"]), value, path)

    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const mismatch")

    expected = schema.get("type")
    allowed = expected if isinstance(expected, list) else [expected]
    type_ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "null": value is None,
        None: True,
    }
    if not any(type_ok.get(kind, False) for kind in allowed):
        return [f"{path}: type mismatch"]

    if isinstance(value, dict) and expected == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = set(required) - set(value)
        unknown = set(value) - set(properties)
        if missing:
            errors.append(f"{path}: missing {sorted(missing)}")
        if schema.get("additionalProperties") is False and unknown:
            errors.append(f"{path}: unknown {sorted(unknown)}")
        for key in set(value) & set(properties):
            errors.extend(validate(root, properties[key], value[key], f"{path}.{key}"))

    if isinstance(value, list) and expected == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate(root, item_schema, item, f"{path}[{index}]"))
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(f"{path}: duplicate items")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: too short")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: pattern mismatch")
        if schema.get("format") == "date":
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                errors.append(f"{path}: invalid date")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{path}: invalid date-time")
    return errors


def schema_contract_errors(node: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            if node.get("additionalProperties") is not False:
                errors.append(f"{path}: object not closed")
            required = node.get("required", [])
            properties = node.get("properties", {})
            if len(required) != len(set(required)):
                errors.append(f"{path}: duplicate required key")
            missing = set(required) - set(properties)
            if missing:
                errors.append(f"{path}: required absent from properties {sorted(missing)}")
        for key, value in node.items():
            errors.extend(schema_contract_errors(value, f"{path}/{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            errors.extend(schema_contract_errors(value, f"{path}/{index}"))
    return errors


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fixture = schema["examples"][0]
    contract_errors = schema_contract_errors(schema)
    fixture_errors = validate(schema, schema, fixture)
    topic_lineage_hash = hashlib.sha256(
        json.dumps(
            fixture["topic_run_lineage"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    fixture_semantics = {
        "topic_lineage_hash": topic_lineage_hash
        == fixture["topic_run_lineage_sha256"],
        "artifact_identity": fixture["daily_research_artifact"]["artifact_run_date"]
        == fixture["time_authority"]["market_run_date"],
        "weekend_daily_source_precedes_run": (
            fixture["daily_research_artifact"]["daily_source_date"]
            < fixture["time_authority"]["market_run_date"]
        ),
        "weekend_regime_source_precedes_run": (
            fixture["market_regime_history"]["source_trade_date"]
            < fixture["time_authority"]["market_run_date"]
        ),
    }

    hostile = {
        "unknown_top_level": lambda item: item.update({"unexpected": True}),
        "missing_queue_owner": lambda item: item.pop("queue_owner"),
        "runner_identity_type": lambda item: item.update({"runner_identity": 7}),
        "null_production_impact": lambda item: item.update({"production_impact": None}),
        "unknown_nested_time": lambda item: item["time_authority"].update({"host_tz": "UTC"}),
    }
    hostile_results: dict[str, bool] = {}
    for name, mutate in hostile.items():
        candidate = copy.deepcopy(fixture)
        mutate(candidate)
        hostile_results[name] = bool(validate(schema, schema, candidate))

    results = {
        "schema_object_contract": not contract_errors,
        "schema_object_contract_errors": contract_errors,
        "canonical_fixture": not fixture_errors,
        "canonical_fixture_errors": fixture_errors,
        "canonical_fixture_semantics": fixture_semantics,
        "hostile_schema_mutations_rejected": hostile_results,
        "v2_mapping_present": bool(schema.get("x-v2-to-v3-mapping")),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(
        [
            results["schema_object_contract"],
            results["canonical_fixture"],
            all(fixture_semantics.values()),
            all(hostile_results.values()),
            results["v2_mapping_present"],
        ]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
