#!/usr/bin/env python3
"""獨立重算 Fog time-authority architecture 的關鍵邊界。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from copy import deepcopy
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


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
RFC3339_UTC_Z = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_utc_z(value: str) -> datetime:
    if not RFC3339_UTC_Z.fullmatch(value):
        raise ValueError("timestamp 必須是 strict RFC3339 UTC Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp 不得為 naive")
    return parsed.astimezone(UTC)


def market_date(value: str, zone: str = "Asia/Taipei") -> str:
    return parse_utc_z(value).astimezone(ZoneInfo(zone)).date().isoformat()


def age_seconds(generated: str, verification: str) -> float:
    return (parse_utc_z(verification) - parse_utc_z(generated)).total_seconds()


def freshness(age: float) -> bool:
    return -5 <= age <= 900


def verify_claim(
    receipt: dict[str, object],
    *,
    verification_time_utc: str,
) -> tuple[bool, list[str]]:
    """模擬契約要求的 verifier trust boundary，不採信 receipt 結果或 policy。"""
    failures: list[str] = []
    authority = receipt["time_authority"]
    assert isinstance(authority, dict)
    expected_hash = canonical_hash(POLICY)
    if authority.get("contract_hash") != expected_hash:
        failures.append("CONTRACT_HASH_MISMATCH")
    generated = str(authority["generated_at_utc"])
    context_created = str(authority["run_context_created_at_utc"])
    computed_generated_date = market_date(generated)
    computed_context_date = market_date(context_created)
    claimed_date = str(authority["market_run_date"])
    if claimed_date not in {computed_generated_date, computed_context_date}:
        failures.append("MARKET_DATE_MISMATCH")
    if computed_generated_date != computed_context_date:
        failures.append("MARKET_DATE_ROLLOVER")
    if not freshness(age_seconds(generated, verification_time_utc)):
        failures.append("FRESHNESS_REJECT")
    return not failures, failures


def main() -> None:
    expected_hash = canonical_hash(POLICY)
    reordered = dict(reversed(list(POLICY.items())))
    mutated = deepcopy(POLICY)
    mutated["freshness"]["max_age_seconds"] = 901

    matrix = {
        "taipei_cross_utc": market_date("2026-07-27T16:30:00Z") == "2026-07-28"
        and freshness(age_seconds("2026-07-27T16:30:00Z", "2026-07-27T16:31:00Z")),
        "taipei_daytime": market_date("2026-07-28T01:00:00Z") == "2026-07-28"
        and freshness(age_seconds("2026-07-28T01:00:00Z", "2026-07-28T01:01:00Z")),
        "stale": not freshness(
            age_seconds("2026-07-28T01:00:00Z", "2026-07-28T01:15:01Z")
        ),
        "future": not freshness(
            age_seconds("2026-07-28T01:00:06Z", "2026-07-28T01:00:00Z")
        ),
        "naive": False,
        "wrong_market_date": False,
        "host_timezone_drift": False,
        "dst_fold": False,
    }
    try:
        parse_utc_z("2026-07-28T01:00:00")
    except ValueError:
        matrix["naive"] = True

    base_receipt: dict[str, object] = {
        "reported_result": "ACCEPT",
        "reported_policy": {"max_age_seconds": 999999},
        "time_authority": {
            "contract_hash": expected_hash,
            "run_context_created_at_utc": "2026-07-28T01:00:00Z",
            "generated_at_utc": "2026-07-28T01:00:00Z",
            "market_run_date": "2026-07-28",
        },
    }
    wrong_date_receipt = deepcopy(base_receipt)
    wrong_date_receipt["time_authority"]["market_run_date"] = "2026-07-27"
    matrix["wrong_market_date"] = not verify_claim(
        wrong_date_receipt,
        verification_time_utc="2026-07-28T01:01:00Z",
    )[0]

    host_results: dict[str, str] = {}
    original_tz = os.environ.get("TZ")
    try:
        for host_zone in ("UTC", "Asia/Taipei", "America/Los_Angeles"):
            os.environ["TZ"] = host_zone
            time.tzset()
            host_results[host_zone] = market_date("2026-07-27T16:30:00Z")
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()
    matrix["host_timezone_drift"] = set(host_results.values()) == {"2026-07-28"}

    new_york = ZoneInfo("America/New_York")
    fold_instants = [
        parse_utc_z("2026-11-01T05:30:00Z"),
        parse_utc_z("2026-11-01T06:30:00Z"),
    ]
    fold_locals = [instant.astimezone(new_york) for instant in fold_instants]
    matrix["dst_fold"] = (
        [local.hour for local in fold_locals] == [1, 1]
        and [local.fold for local in fold_locals] == [0, 1]
        and [local.astimezone(UTC) for local in fold_locals] == fold_instants
    )

    forged_hash_receipt = deepcopy(base_receipt)
    forged_hash_receipt["time_authority"]["contract_hash"] = "0" * 64
    stale_with_forged_policy = deepcopy(base_receipt)
    stale_with_forged_policy["time_authority"][
        "generated_at_utc"
    ] = "2026-07-28T01:00:00Z"
    stale_with_forged_policy["time_authority"][
        "run_context_created_at_utc"
    ] = "2026-07-28T01:00:00Z"

    midnight_before = market_date("2026-07-27T15:59:59.999999Z")
    midnight_after = market_date("2026-07-27T16:00:00Z")
    boundaries = {
        "-5": freshness(-5),
        "-5.001": freshness(-5.001),
        "900": freshness(900),
        "900.001": freshness(900.001),
        "midnight_identity_changes": midnight_before != midnight_after,
    }
    trust_boundary = {
        "valid_claim": verify_claim(
            base_receipt,
            verification_time_utc="2026-07-28T01:01:00Z",
        )[0],
        "forged_hash_rejected": not verify_claim(
            forged_hash_receipt,
            verification_time_utc="2026-07-28T01:01:00Z",
        )[0],
        "receipt_policy_cannot_freshen_stale": not verify_claim(
            stale_with_forged_policy,
            verification_time_utc="2026-07-28T01:15:01Z",
        )[0],
    }
    source_date_counterexample = {
        "market_run_date": "2026-08-08",
        "daily_source_date": "2026-08-07",
        "independent_dates_possible": True,
        "candidate_invariant_accepts": "2026-08-07" == "2026-08-08",
    }

    result = {
        "matrix": matrix,
        "boundaries": boundaries,
        "host_results": host_results,
        "dst_fold": [
            {
                "utc": instant.isoformat(),
                "local": local.isoformat(),
                "fold": local.fold,
            }
            for instant, local in zip(fold_instants, fold_locals, strict=True)
        ],
        "policy_hash": {
            "expected": expected_hash,
            "reordered_equal": canonical_hash(reordered) == expected_hash,
            "semantic_mutation_changes_hash": canonical_hash(mutated) != expected_hash,
        },
        "trust_boundary": trust_boundary,
        "source_date_counterexample": source_date_counterexample,
    }
    assert all(matrix.values()), matrix
    assert boundaries == {
        "-5": True,
        "-5.001": False,
        "900": True,
        "900.001": False,
        "midnight_identity_changes": True,
    }
    assert all(trust_boundary.values()), trust_boundary
    assert result["policy_hash"]["reordered_equal"] is True
    assert result["policy_hash"]["semantic_mutation_changes_hash"] is True
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
