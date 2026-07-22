"""TSKG-MFO-THEME-01 membership 與 deterministic aggregation tests。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.tskg.flow_observation import SecurityFlowObservationFixture
from app.tskg.theme_membership import (
    ThemeMembershipContractError,
    ThemeMembershipSnapshot,
    aggregate_theme_institutional_flow,
)


ROOT = Path(__file__).resolve().parents[1]


def _snapshot_payload() -> dict:
    return json.loads((ROOT / "data/fixtures/tskg/theme_membership_v1.json").read_text())


def _flow() -> SecurityFlowObservationFixture:
    return SecurityFlowObservationFixture.from_file(ROOT / "data/fixtures/tskg/security_flow_observations_v1.json")


def test_aggregation_is_deterministic_and_allocates_multi_membership_once() -> None:
    snapshot = ThemeMembershipSnapshot(_snapshot_payload())
    result = aggregate_theme_institutional_flow(snapshot, _flow(), as_of_date="2026-07-17")
    assert result == aggregate_theme_institutional_flow(snapshot, _flow(), as_of_date="2026-07-17")
    by_theme = {item["theme_id"]: item for item in result["items"]}
    assert by_theme["theme-ai"]["institutional_net_value"] == 67000000
    assert by_theme["theme-semiconductor"]["institutional_net_value"] == -136000000
    assert result["allocation_policy"] == "EQUAL_SPLIT_ACROSS_ACTIVE_THEMES"
    assert result["venue_coverage"] == {"TWSE": "AVAILABLE", "TPEX": "BLOCKED"}


def test_mutated_snapshot_hash_fails_closed() -> None:
    payload = _snapshot_payload()
    payload["memberships"].append({
        "security_id": "security-missing-xtai",
        "theme_id": "theme-empty",
        "effective_from": "2026-07-01",
        "effective_to": "2026-07-31",
    })
    with pytest.raises(ThemeMembershipContractError, match="content_hash"):
        ThemeMembershipSnapshot(payload)


def test_zero_coverage_is_explicit() -> None:
    raw = json.loads((ROOT / "data/fixtures/tskg/security_flow_observations_v1.json").read_text())
    for index, row in enumerate(raw["observations"]):
        row["security_id"] = f"security-unmatched-{index}-xtai"
        row["observation_id"] = f"unmatched-{index}"
    snapshot = ThemeMembershipSnapshot(_snapshot_payload())
    result = aggregate_theme_institutional_flow(
        snapshot,
        SecurityFlowObservationFixture.from_mapping(raw),
        as_of_date="2026-07-17",
    )
    assert all(item["status"] == "ZERO_COVERAGE" for item in result["items"])
    assert all(item["coverage"] == 0.0 for item in result["items"])
    assert all(item["institutional_net_value"] == 0 for item in result["items"])


def test_stale_snapshot_and_duplicate_membership_fail_closed() -> None:
    payload = _snapshot_payload()
    payload["effective_interval"]["to"] = "2026-07-16"
    with pytest.raises(ThemeMembershipContractError, match="content_hash"):
        ThemeMembershipSnapshot(payload)
    payload = _snapshot_payload()
    payload["memberships"].append(deepcopy(payload["memberships"][0]))
    with pytest.raises(ThemeMembershipContractError, match="duplicate"):
        ThemeMembershipSnapshot(payload)


def test_cross_date_observations_do_not_leak_into_target_date() -> None:
    snapshot = ThemeMembershipSnapshot(_snapshot_payload())
    target = aggregate_theme_institutional_flow(snapshot, _flow(), as_of_date="2026-07-16")
    assert all(item["observed_security_count"] == 0 for item in target["items"])
    assert all(item["status"] == "ZERO_COVERAGE" for item in target["items"])


def test_stale_requested_date_fails_closed() -> None:
    snapshot = ThemeMembershipSnapshot(_snapshot_payload())
    with pytest.raises(ThemeMembershipContractError, match="stale"):
        aggregate_theme_institutional_flow(snapshot, _flow(), as_of_date="2026-08-01")
