from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.fog_runtime_time_authority import (
    EXPECTED_POLICY,
    TimeAuthorityError,
    build_run_context,
    canonical_json_hash,
    derive_market_run_date,
    format_utc_z,
    load_policy,
    parse_utc_z,
    validate_run_context,
    verify_freshness,
)


EXPECTED_HASH = "67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357"


def test_policy_hash_and_semantics_are_canonical() -> None:
    assert load_policy() == EXPECTED_POLICY
    assert canonical_json_hash(EXPECTED_POLICY) == EXPECTED_HASH
    reordered = dict(reversed(list(EXPECTED_POLICY.items())))
    assert canonical_json_hash(reordered) == EXPECTED_HASH
    mutated = copy.deepcopy(EXPECTED_POLICY)
    mutated["freshness"]["max_age_seconds"] = 901
    assert canonical_json_hash(mutated) != EXPECTED_HASH


@pytest.mark.parametrize(
    ("generated", "verified", "ok", "reason"),
    [
        ("2026-07-28T01:00:05Z", "2026-07-28T01:00:00Z", True, None),
        ("2026-07-28T01:00:05.001000Z", "2026-07-28T01:00:00Z", False, "FUTURE_RECEIPT"),
        ("2026-07-28T01:00:00Z", "2026-07-28T01:15:00Z", True, None),
        ("2026-07-28T01:00:00Z", "2026-07-28T01:15:00.001000Z", False, "STALE_RECEIPT"),
    ],
)
def test_signed_freshness_exact_boundaries(
    generated: str,
    verified: str,
    ok: bool,
    reason: str | None,
) -> None:
    result = verify_freshness(generated, verified)
    assert result["ok"] is ok
    if reason:
        assert reason in result["reason_codes"]


@pytest.mark.parametrize(
    "value",
    [
        "2026-07-28T01:00:00",
        "2026-07-28T01:00:00+00:00",
        "2026-07-28T01:00:00.0000000Z",
        "2026-07-28T25:00:00Z",
        "2026-07-28T01:00:60Z",
    ],
)
def test_parse_utc_z_rejects_noncanonical_timestamps(value: str) -> None:
    with pytest.raises(TimeAuthorityError):
        parse_utc_z(value)


def test_aware_datetime_round_trip_and_naive_rejection() -> None:
    instant = datetime(2026, 7, 27, 16, 30, tzinfo=UTC)
    assert format_utc_z(parse_utc_z(format_utc_z(instant))) == "2026-07-27T16:30:00Z"
    with pytest.raises(TimeAuthorityError, match="NAIVE_TIMESTAMP"):
        parse_utc_z(datetime(2026, 7, 27, 16, 30))


def test_taipei_projection_crosses_utc_date_boundary() -> None:
    assert derive_market_run_date("2026-07-27T16:30:00Z") == "2026-07-28"
    assert derive_market_run_date("2026-07-28T15:59:59.999999Z") == "2026-07-28"
    assert derive_market_run_date("2026-07-28T16:00:00Z") == "2026-07-29"


def test_host_timezone_and_locale_do_not_change_identity() -> None:
    original_tz = os.environ.get("TZ")
    results = []
    try:
        for host_tz in ("UTC", "Asia/Taipei", "America/Los_Angeles"):
            os.environ["TZ"] = host_tz
            time.tzset()
            results.append(derive_market_run_date("2026-07-27T16:30:00Z"))
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()
    assert results == ["2026-07-28"] * 3


def test_run_context_is_exact_and_immutable() -> None:
    context = build_run_context("2026-07-27T16:30:00Z")
    assert context["market_run_date"] == "2026-07-28"
    assert context["artifact_run_date"] == "2026-07-28"
    assert validate_run_context(context)["ok"]
    context["market_run_date"] = "2026-07-27"
    assert not validate_run_context(context)["ok"]
    context["receipt_override"] = 1
    assert validate_run_context(context)["reason_codes"] == ["RUN_CONTEXT_SCHEMA_REJECT"]


def test_repo_policy_cannot_be_overridden() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        policy_path = root / "config/fog_runtime_time_authority_v1.json"
        policy_path.parent.mkdir(parents=True)
        hostile = copy.deepcopy(EXPECTED_POLICY)
        hostile["market_timezone"] = "UTC"
        policy_path.write_text(json.dumps(hostile), encoding="utf-8")
        with pytest.raises(TimeAuthorityError, match="TIME_AUTHORITY_CONTRACT_DRIFT"):
            load_policy(project_root=root)
