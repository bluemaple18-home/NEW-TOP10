"""TSKG Theme membership snapshot 與法人資金聚合契約。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date
from typing import Any, Mapping

from app.tskg.flow_observation import SecurityFlowObservationFixture


SCHEMA_VERSION = "tskg-theme-membership-snapshot-v1"
FORMULA_VERSION = "theme-institutional-flow-v1"
ALLOCATION_POLICY = "EQUAL_SPLIT_ACROSS_ACTIVE_THEMES"
_REQUIRED = {
    "fixture_version", "schema_version", "formula_version", "as_of_date",
    "source", "version", "content_hash", "effective_interval",
    "evidence_locator", "venue_coverage", "memberships",
}
_MEMBERSHIP_FIELDS = {"security_id", "theme_id", "effective_from", "effective_to"}
_PROHIBITED = {
    "price", "return", "prediction", "recommendation", "rank", "score",
    "buy_signal", "sell_signal", "target_price", "weight",
}


class ThemeMembershipContractError(ValueError):
    """Theme membership snapshot 違反 closed-schema 或 provenance contract。"""


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ThemeMembershipContractError(f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ThemeMembershipContractError(f"{field} must be YYYY-MM-DD") from error


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


class ThemeMembershipSnapshot:
    """驗證並保存可重算、具版本與證據定位的 membership snapshot。"""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if not isinstance(payload, Mapping):
            raise ThemeMembershipContractError("snapshot must be an object")
        data = deepcopy(dict(payload))
        if _PROHIBITED.intersection(_all_keys(data)):
            raise ThemeMembershipContractError("strategy fields are prohibited")
        if set(data) != _REQUIRED:
            raise ThemeMembershipContractError("snapshot has an unexpected or missing field")
        if data["fixture_version"] != "theme-membership-v1" or data["schema_version"] != SCHEMA_VERSION:
            raise ThemeMembershipContractError("snapshot version mismatch")
        if data["formula_version"] != FORMULA_VERSION:
            raise ThemeMembershipContractError("formula_version mismatch")
        _date(data["as_of_date"], "as_of_date")
        for field in ("source", "version", "content_hash", "evidence_locator"):
            if not isinstance(data[field], str) or not data[field]:
                raise ThemeMembershipContractError(f"{field} must be non-empty")
        if len(data["content_hash"]) != 64 or any(c not in "0123456789abcdef" for c in data["content_hash"]):
            raise ThemeMembershipContractError("content_hash must be a sha256 hex digest")
        interval = data["effective_interval"]
        if not isinstance(interval, Mapping) or set(interval) != {"from", "to"}:
            raise ThemeMembershipContractError("effective_interval must contain from/to")
        if _date(interval["from"], "effective_interval.from") > _date(interval["to"], "effective_interval.to"):
            raise ThemeMembershipContractError("effective interval is inverted")
        coverage = data["venue_coverage"]
        if coverage != {"TWSE": "AVAILABLE", "TPEX": "BLOCKED"}:
            raise ThemeMembershipContractError("venue coverage must explicitly keep TPEx blocked")
        rows = data["memberships"]
        if not isinstance(rows, list):
            raise ThemeMembershipContractError("memberships must be a list")
        seen: set[tuple[str, str, str, str]] = set()
        intervals_by_pair: dict[tuple[str, str], list[tuple[date, date]]] = {}
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _MEMBERSHIP_FIELDS:
                raise ThemeMembershipContractError("invalid membership row")
            if not all(isinstance(row[field], str) and row[field] for field in _MEMBERSHIP_FIELDS):
                raise ThemeMembershipContractError("membership fields must be non-empty")
            start, end = _date(row["effective_from"], "effective_from"), _date(row["effective_to"], "effective_to")
            if start > end:
                raise ThemeMembershipContractError("membership interval is inverted")
            key = tuple(row[field] for field in ("security_id", "theme_id", "effective_from", "effective_to"))
            if key in seen:
                raise ThemeMembershipContractError("duplicate membership")
            seen.add(key)
            intervals_by_pair.setdefault((row["security_id"], row["theme_id"]), []).append((start, end))
        for pair, intervals in intervals_by_pair.items():
            ordered = sorted(intervals)
            if any(start <= previous_end for (_, previous_end), (start, _) in zip(ordered, ordered[1:])):
                raise ThemeMembershipContractError(
                    f"overlapping membership interval for {pair[0]}/{pair[1]}"
                )
        data["memberships"] = sorted(
            rows,
            key=lambda row: (
                row["security_id"], row["theme_id"],
                row["effective_from"], row["effective_to"],
            ),
        )
        hash_input = {
            field: data[field]
            for field in ("as_of_date", "effective_interval", "memberships", "source", "version")
        }
        if data["content_hash"] != _canonical_hash(hash_input):
            raise ThemeMembershipContractError("content_hash does not match snapshot content")
        self._payload = data

    def active_memberships(self, as_of_date: str) -> tuple[dict[str, str], ...]:
        target = _date(as_of_date, "as_of_date")
        interval = self._payload["effective_interval"]
        if not (_date(interval["from"], "effective_interval.from") <= target <= _date(interval["to"], "effective_interval.to")):
            raise ThemeMembershipContractError("membership snapshot is stale for requested date")
        return tuple(sorted(
            (dict(row) for row in self._payload["memberships"]
             if _date(row["effective_from"], "effective_from") <= target <= _date(row["effective_to"], "effective_to")),
            key=lambda row: (row["theme_id"], row["security_id"]),
        ))

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._payload)

    @classmethod
    def from_file(cls, path: Path) -> "ThemeMembershipSnapshot":
        return cls(json.loads(path.read_text(encoding="utf-8")))


def aggregate_theme_institutional_flow(
    snapshot: ThemeMembershipSnapshot,
    observations: SecurityFlowObservationFixture,
    *,
    as_of_date: str,
) -> dict[str, Any]:
    """以 exact date、明示 allocation policy 聚合，不改寫 raw observation。"""
    active = snapshot.active_memberships(as_of_date)
    by_security: dict[str, list[str]] = {}
    for row in active:
        by_security.setdefault(row["security_id"], []).append(row["theme_id"])
    flows = {
        row["security_id"]: row for row in observations.observations()
        if row["trade_date"] == as_of_date and row["investor_type"] == "ALL_INSTITUTIONAL"
    }
    themes = sorted({row["theme_id"] for row in active})
    items = []
    for theme in themes:
        securities = sorted({row["security_id"] for row in active if row["theme_id"] == theme})
        present = [security for security in securities if security in flows]
        missing = len(securities) - len(present)
        buy = sell = net = 0.0
        stale_count = 0
        for security in present:
            allocated = flows[security]["net_buy_value_1d"] / len(by_security[security])
            buy += max(allocated, 0)
            sell += max(-allocated, 0)
            net += allocated
            stale_count += int(flows[security]["is_stale"])
        items.append({
            "theme_id": theme,
            "security_count": len(securities),
            "observed_security_count": len(present),
            "missing_count": missing,
            "coverage": len(present) / len(securities) if securities else 0.0,
            "institutional_buy_value": int(buy) if buy.is_integer() else buy,
            "institutional_sell_value": int(sell) if sell.is_integer() else sell,
            "institutional_net_value": int(net) if net.is_integer() else net,
            "stale_observation_count": stale_count,
            "freshness": "STALE" if stale_count else "FRESH",
            "status": "ZERO_COVERAGE" if not present else "PARTIAL" if missing else "COMPLETE",
        })
    result = {
        "schema_version": "tskg-theme-institutional-flow-read-model-v1",
        "formula_version": FORMULA_VERSION,
        "as_of_date": as_of_date,
        "source": snapshot.as_dict()["source"],
        "venue_coverage": {"TWSE": "AVAILABLE", "TPEX": "BLOCKED"},
        "allocation_policy": ALLOCATION_POLICY,
        "membership_snapshot": {"version": snapshot.as_dict()["version"], "content_hash": snapshot.as_dict()["content_hash"]},
        "items": items,
    }
    return {**result, "canonical_hash": _canonical_hash(result)}


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | set().union(*(_all_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(child) for child in value)) if value else set()
    return set()
