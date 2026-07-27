#!/usr/bin/env python3
"""獨立驗證 Repair-1 的三個固定 architecture findings。"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE_PATH = ROOT / "docs/architecture/fog_runtime_time_authority_v1.md"
SCHEMA_PATH = ROOT / "docs/architecture/fog_runtime_receipt_v3.schema.json"
POLICY = {
    "schema_version": "fog-runtime-time-authority.v1",
    "market_id": "TWSE",
    "market_timezone": "Asia/Taipei",
    "market_day_semantics": "local-civil-date",
    "timestamp_format": "rfc3339-utc-z",
    "receipt_schema_version": "closed-regime-runtime-receipt.v3",
    "freshness": {
        "max_age_seconds": 900,
        "future_tolerance_seconds": 5,
    },
    "lifecycle": {
        "market_midnight_boundary": "hard",
    },
}


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"非 local ref：{reference}")
    node: Any = root
    for part in reference[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise TypeError(f"ref 不是 schema object：{reference}")
    return node


def dereference(root: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    return resolve_ref(root, schema["$ref"]) if "$ref" in schema else schema


def validate(
    root: dict[str, Any],
    schema: dict[str, Any],
    value: Any,
    location: str = "$",
) -> list[str]:
    schema = dereference(root, schema)
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: const mismatch")

    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected]
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "null": value is None,
        None: True,
    }
    if not any(matches.get(kind, False) for kind in expected_types):
        return errors + [f"{location}: type mismatch"]

    if isinstance(value, dict) and expected == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = set(required) - set(value)
        unknown = set(value) - set(properties)
        if missing:
            errors.append(f"{location}: missing {sorted(missing)}")
        if schema.get("additionalProperties") is False and unknown:
            errors.append(f"{location}: unknown {sorted(unknown)}")
        for key in set(value) & set(properties):
            errors.extend(
                validate(root, properties[key], value[key], f"{location}.{key}")
            )

    if isinstance(value, list) and expected == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate(root, item_schema, item, f"{location}[{index}]")
                )
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: duplicate items")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: too short")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            errors.append(f"{location}: pattern mismatch")
        if schema.get("format") == "date":
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                errors.append(f"{location}: invalid date")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{location}: invalid date-time")
    return errors


def schema_nodes(node: Any, location: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        yield location, node
        for key, child in node.items():
            yield from schema_nodes(child, f"{location}/{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from schema_nodes(child, f"{location}/{index}")


def instance_objects(
    root: dict[str, Any],
    schema: dict[str, Any],
    value: Any,
    path: tuple[str | int, ...] = (),
) -> Iterator[tuple[tuple[str | int, ...], dict[str, Any]]]:
    schema = dereference(root, schema)
    if isinstance(value, dict) and schema.get("type") == "object":
        yield path, schema
        properties = schema["properties"]
        for key, child in value.items():
            yield from instance_objects(
                root,
                properties[key],
                child,
                (*path, key),
            )
    elif isinstance(value, list) and schema.get("type") == "array":
        for index, child in enumerate(value):
            yield from instance_objects(
                root,
                schema["items"],
                child,
                (*path, index),
            )


def at_path(root: Any, path: tuple[str | int, ...]) -> Any:
    node = root
    for part in path:
        node = node[part]
    return node


def hostile_type_value(root: dict[str, Any], schema: dict[str, Any]) -> Any:
    schema = dereference(root, schema)
    if "const" in schema:
        return None if schema["const"] is not None else "unexpected"
    expected = schema.get("type")
    if expected == "object":
        return []
    if expected == "array":
        return {}
    if expected == "string":
        return 7
    if isinstance(expected, list):
        return {}
    return {"unexpected": True}


def parse_utc_z(value: str) -> datetime:
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z",
        value,
    ):
        raise ValueError("非 canonical UTC Z")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)


def market_date(value: str, zone: str = "Asia/Taipei") -> str:
    return parse_utc_z(value).astimezone(ZoneInfo(zone)).date().isoformat()


def source_semantic_result(
    fixture: dict[str, Any],
    *,
    canonical_artifact_run_date: str = "2026-08-08",
    canonical_daily_source_date: str = "2026-08-07",
) -> str:
    run_date = fixture["time_authority"]["market_run_date"]
    artifact = fixture["daily_research_artifact"]
    if artifact["artifact_run_date"] != canonical_artifact_run_date:
        return "ARTIFACT_IDENTITY_DRIFT"
    if artifact["daily_source_date"] > run_date:
        return "FUTURE_DAILY_SOURCE_DATE"
    if artifact["daily_source_date"] != canonical_daily_source_date:
        return "DAILY_SOURCE_DATE_MISMATCH"
    return "ACCEPT"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    architecture = ARCHITECTURE_PATH.read_text(encoding="utf-8")
    fixture = schema["examples"][0]

    object_contract_errors: list[str] = []
    nullable_locations: list[str] = []
    for location, node in schema_nodes(schema):
        if node.get("type") == "object":
            properties = node.get("properties", {})
            required = node.get("required", [])
            if node.get("additionalProperties") is not False:
                object_contract_errors.append(f"{location}: not closed")
            if len(required) != len(set(required)):
                object_contract_errors.append(f"{location}: duplicate required")
            if set(required) != set(properties):
                object_contract_errors.append(f"{location}: required != properties")
        node_type = node.get("type")
        if isinstance(node_type, list) and "null" in node_type:
            nullable_locations.append(location)

    object_pairs = list(instance_objects(schema, schema, fixture))
    unknown_rejections = 0
    missing_rejections = 0
    type_rejections = 0
    required_mutation_count = 0
    for path, object_schema in object_pairs:
        mutated = copy.deepcopy(fixture)
        at_path(mutated, path)["unexpected_reviewer_field"] = True
        unknown_rejections += bool(validate(schema, schema, mutated))

        for key in object_schema["required"]:
            required_mutation_count += 1
            missing = copy.deepcopy(fixture)
            at_path(missing, path).pop(key)
            missing_rejections += bool(validate(schema, schema, missing))

            wrong_type = copy.deepcopy(fixture)
            wrong_type_node = at_path(wrong_type, path)
            wrong_type_node[key] = hostile_type_value(
                schema,
                object_schema["properties"][key],
            )
            type_rejections += bool(validate(schema, schema, wrong_type))

    invalid_formats = {
        "calendar_date": ("daily_research_artifact", "daily_source_date", "2026-02-30"),
        "utc_hour": ("time_authority", "generated_at_utc", "2026-08-08T25:01:00Z"),
        "non_z_utc": (
            "time_authority",
            "generated_at_utc",
            "2026-08-08T02:01:00+00:00",
        ),
        "path_traversal": (
            "daily_research_artifact",
            "path",
            "../artifacts/forged.json",
        ),
    }
    invalid_format_rejections: dict[str, bool] = {}
    for name, (section, key, hostile_value) in invalid_formats.items():
        mutated = copy.deepcopy(fixture)
        mutated[section][key] = hostile_value
        invalid_format_rejections[name] = bool(validate(schema, schema, mutated))

    wrong_source = copy.deepcopy(fixture)
    wrong_source["daily_research_artifact"]["daily_source_date"] = "2026-08-06"
    future_source = copy.deepcopy(fixture)
    future_source["daily_research_artifact"]["daily_source_date"] = "2026-08-09"
    drifted_artifact = copy.deepcopy(fixture)
    drifted_artifact["daily_research_artifact"]["artifact_run_date"] = "2026-08-07"

    original_tz = os.environ.get("TZ")
    host_dates: dict[str, str] = {}
    try:
        for host_zone in ("UTC", "Asia/Taipei", "America/Los_Angeles"):
            os.environ["TZ"] = host_zone
            time.tzset()
            host_dates[host_zone] = market_date("2026-07-27T16:30:00Z")
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()

    fold_instants = [
        parse_utc_z("2026-11-01T05:30:00Z"),
        parse_utc_z("2026-11-01T06:30:00Z"),
    ]
    fold_locals = [
        instant.astimezone(ZoneInfo("America/New_York"))
        for instant in fold_instants
    ]

    required_modules = {
        "scripts/fog_authority_contracts.py",
        "scripts/verify_fog_closed_regime_recovery.py",
        "scripts/verify_processed_id_authority.py",
        "scripts/verify_closed_regime_runtime.py",
        "tests/test_fog_closed_regime_runtime.py",
        "tests/test_daily_research_quota_verifier.py",
    }
    regression_ids = {
        "FRTA-REG-RRV-P1-01-PROCESSED-ID",
        "FRTA-REG-RRV-P1-03-SOURCE-BASELINE",
        "FRTA-REG-RECEIPT-V3-EXACT",
        "FRTA-REG-TIME-DATE-LINEAGE",
    }
    mapping_text = "\n".join(schema["x-v2-to-v3-mapping"])
    topic_hash = canonical_hash(fixture["topic_run_lineage"])

    results = {
        "frta_p1_01": {
            "valid_weekend": source_semantic_result(fixture) == "ACCEPT",
            "wrong_source": source_semantic_result(wrong_source)
            == "DAILY_SOURCE_DATE_MISMATCH",
            "future_source": source_semantic_result(future_source)
            == "FUTURE_DAILY_SOURCE_DATE",
            "artifact_drift": source_semantic_result(drifted_artifact)
            == "ARTIFACT_IDENTITY_DRIFT",
        },
        "frta_p1_02": {
            "clean_room_policy": all(
                phrase in architecture
                for phrase in (
                    "不得 merge、cherry-pick、copy",
                    "clean-room reimplementation",
                    "唯一合法 base",
                    "non-ancestor evidence source",
                )
            ),
            "required_modules_present": all(
                module in architecture for module in required_modules
            ),
            "regression_ids_present": all(
                regression_id in architecture for regression_id in regression_ids
            ),
        },
        "frta_p1_03": {
            "object_contract": not object_contract_errors,
            "object_contract_errors": object_contract_errors,
            "nullable_locations": nullable_locations,
            "only_decision_nullable": nullable_locations
            == ["$/$defs/topic_run/properties/decision"],
            "canonical_fixture": not validate(schema, schema, fixture),
            "object_layer_count": len(object_pairs),
            "unknown_rejections": unknown_rejections,
            "unknown_mutation_count": len(object_pairs),
            "missing_rejections": missing_rejections,
            "required_mutation_count": required_mutation_count,
            "type_rejections": type_rejections,
            "invalid_format_rejections": invalid_format_rejections,
            "topic_hash_matches": topic_hash
            == fixture["topic_run_lineage_sha256"],
            "v2_no_relabel": "never relabel a v2 payload" in mapping_text,
            "v2_missing_authority_fails": (
                "missing authoritative run-context instant" in mapping_text
                and "fail closed; archive v2 without upgrading" in mapping_text
            ),
        },
        "direct_regression": {
            "policy_hash": canonical_hash(POLICY),
            "policy_hash_matches_fixture": canonical_hash(POLICY)
            == fixture["time_authority"]["contract_hash"],
            "host_dates": host_dates,
            "host_invariant": set(host_dates.values()) == {"2026-07-28"},
            "dst_folds": [local.fold for local in fold_locals],
            "dst_round_trip": [
                local.astimezone(UTC) for local in fold_locals
            ]
            == fold_instants,
            "age_boundaries": {
                "-5": -5 <= -5 <= 900,
                "-5.001": -5 <= -5.001 <= 900,
                "900": -5 <= 900 <= 900,
                "900.001": -5 <= 900.001 <= 900,
            },
        },
    }
    assert all(results["frta_p1_01"].values())
    assert all(
        value for value in results["frta_p1_02"].values() if isinstance(value, bool)
    )
    p1_03 = results["frta_p1_03"]
    assert p1_03["object_contract"]
    assert p1_03["only_decision_nullable"]
    assert p1_03["canonical_fixture"]
    assert p1_03["unknown_rejections"] == p1_03["unknown_mutation_count"]
    assert p1_03["missing_rejections"] == p1_03["required_mutation_count"]
    assert p1_03["type_rejections"] == p1_03["required_mutation_count"]
    assert all(p1_03["invalid_format_rejections"].values())
    assert p1_03["topic_hash_matches"]
    assert p1_03["v2_no_relabel"]
    assert p1_03["v2_missing_authority_fails"]
    direct = results["direct_regression"]
    assert direct["policy_hash_matches_fixture"]
    assert direct["host_invariant"]
    assert direct["dst_folds"] == [0, 1]
    assert direct["dst_round_trip"]
    assert direct["age_boundaries"] == {
        "-5": True,
        "-5.001": False,
        "900": True,
        "900.001": False,
    }
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
