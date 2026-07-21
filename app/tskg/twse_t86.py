"""TWSE T86 單日逐證券法人買賣超股數 snapshot。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from app.tskg.identity import parse_utc_instant


SCHEMA_VERSION = "tskg-twse-t86-snapshot-v1"
SOURCE_ID = "twse-t86"
ENDPOINT = "https://www.twse.com.tw/rwd/zh/fund/T86"
SELECT_TYPE = "ALLBUT0999"
REQUEST_HEADERS = {"User-Agent": "TOP10new-TSKG/1.0 (scheduled-local-research)"}

FIELD_MAP = {
    "證券代號": "stock_id",
    "證券名稱": "stock_name",
    "外陸資買進股數(不含外資自營商)": "foreign_ex_dealer_buy_shares",
    "外陸資賣出股數(不含外資自營商)": "foreign_ex_dealer_sell_shares",
    "外陸資買賣超股數(不含外資自營商)": "foreign_ex_dealer_net_shares",
    "外資自營商買進股數": "foreign_dealer_buy_shares",
    "外資自營商賣出股數": "foreign_dealer_sell_shares",
    "外資自營商買賣超股數": "foreign_dealer_net_shares",
    "投信買進股數": "investment_trust_buy_shares",
    "投信賣出股數": "investment_trust_sell_shares",
    "投信買賣超股數": "investment_trust_net_shares",
    "自營商買賣超股數": "dealer_total_net_shares",
    "自營商買進股數(自行買賣)": "dealer_self_buy_shares",
    "自營商賣出股數(自行買賣)": "dealer_self_sell_shares",
    "自營商買賣超股數(自行買賣)": "dealer_self_net_shares",
    "自營商買進股數(避險)": "dealer_hedge_buy_shares",
    "自營商賣出股數(避險)": "dealer_hedge_sell_shares",
    "自營商買賣超股數(避險)": "dealer_hedge_net_shares",
    "三大法人買賣超股數": "all_institutional_net_shares",
}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_id",
    "trade_date",
    "retrieved_at",
    "unit",
    "source",
    "integrity",
    "records",
}
_SOURCE_FIELDS = {
    "publisher",
    "endpoint",
    "response_date",
    "title",
    "hints",
    "select_type",
}
_INTEGRITY_FIELDS = {"row_count", "field_count", "canonical_sha256"}
_RECORD_FIELDS = set(FIELD_MAP.values())
_INTEGER_FIELDS = _RECORD_FIELDS - {"stock_id", "stock_name"}
_STOCK_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


class T86SnapshotContractError(ValueError):
    """T86 response 或 normalized snapshot 違反 closed contract。"""


def build_t86_snapshot(
    payload: Mapping[str, Any],
    *,
    requested_trade_date: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """把官方 response 轉成 deterministic、單位明確的 SHARE snapshot。"""

    trade_date = _validate_trade_date(requested_trade_date)
    _validate_retrieved_at(retrieved_at)
    if not isinstance(payload, Mapping):
        raise T86SnapshotContractError("payload must be an object")
    if payload.get("stat") != "OK":
        raise T86SnapshotContractError(f"T86 response stat is not OK: {payload.get('stat')}")

    response_date = payload.get("date")
    if response_date != trade_date.replace("-", ""):
        raise T86SnapshotContractError("T86 response date does not match requested date")
    hints = payload.get("hints")
    if not isinstance(hints, str) or "股" not in hints or "元" in hints:
        raise T86SnapshotContractError("T86 response unit must be shares")
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise T86SnapshotContractError("T86 response title is missing")
    if payload.get("selectType") != SELECT_TYPE:
        raise T86SnapshotContractError("T86 selectType does not match request")

    fields = payload.get("fields")
    if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
        raise T86SnapshotContractError("T86 fields must be a string list")
    if len(fields) != len(set(fields)) or set(fields) != set(FIELD_MAP):
        raise T86SnapshotContractError("T86 field set differs from v1 contract")
    field_positions = {field: position for position, field in enumerate(fields)}

    source_rows = payload.get("data")
    if not isinstance(source_rows, list) or not source_rows:
        raise T86SnapshotContractError("T86 data must be a non-empty list")
    total = payload.get("total")
    if type(total) is not int or total != len(source_rows):
        raise T86SnapshotContractError("T86 total does not equal data row count")

    records: list[dict[str, Any]] = []
    stock_ids: set[str] = set()
    for source_row in source_rows:
        if not isinstance(source_row, list) or len(source_row) != len(fields):
            raise T86SnapshotContractError("T86 row width differs from field count")
        record: dict[str, Any] = {}
        for source_field, target_field in FIELD_MAP.items():
            raw_value = source_row[field_positions[source_field]]
            if target_field == "stock_id":
                if not isinstance(raw_value, str):
                    raise T86SnapshotContractError("T86 stock_id must be a string")
                value = raw_value.strip()
                if not _STOCK_ID_PATTERN.fullmatch(value):
                    raise T86SnapshotContractError("T86 stock_id has invalid syntax")
            elif target_field == "stock_name":
                if not isinstance(raw_value, str):
                    raise T86SnapshotContractError("T86 stock_name must be a string")
                value = raw_value.strip()
                if not value:
                    raise T86SnapshotContractError("T86 stock_name is empty")
            else:
                value = _parse_integer(raw_value, target_field)
            record[target_field] = value
        if record["stock_id"] in stock_ids:
            raise T86SnapshotContractError(f"duplicate T86 stock_id: {record['stock_id']}")
        stock_ids.add(record["stock_id"])
        _validate_record_arithmetic(record)
        records.append(record)

    records.sort(key=lambda row: row["stock_id"])
    source = {
        "publisher": "Taiwan Stock Exchange",
        "endpoint": ENDPOINT,
        "response_date": response_date,
        "title": title.strip(),
        "hints": hints.strip(),
        "select_type": SELECT_TYPE,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "trade_date": trade_date,
        "unit": "SHARE",
        "source": source,
        "records": records,
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "trade_date": trade_date,
        "retrieved_at": retrieved_at,
        "unit": "SHARE",
        "source": source,
        "integrity": {
            "row_count": len(records),
            "field_count": len(fields),
            "canonical_sha256": _canonical_hash(core),
        },
        "records": records,
    }
    return _validate_snapshot(snapshot)


def fetch_t86_snapshot(
    trade_date: str,
    *,
    http_get: Callable[..., Any] = requests.get,
    retrieved_at: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """每次呼叫只送出一個 GET，不內建 retry loop。"""

    normalized_date = _validate_trade_date(trade_date)
    response = http_get(
        ENDPOINT,
        params={
            "date": normalized_date.replace("-", ""),
            "selectType": SELECT_TYPE,
            "response": "json",
        },
        headers=REQUEST_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    observed_at = retrieved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return build_t86_snapshot(
        payload,
        requested_trade_date=normalized_date,
        retrieved_at=observed_at,
    )


def write_t86_snapshot(snapshot: Mapping[str, Any], path: Path) -> Path:
    """以同目錄 temporary file + replace 原子更新 snapshot。"""

    canonical = _validate_snapshot(snapshot)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(canonical, temporary_file, ensure_ascii=False, indent=2, allow_nan=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return target


def load_t86_snapshot(path: Path) -> dict[str, Any]:
    """載入 artifact 並重新驗證 closed schema、算術與 checksum。"""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise T86SnapshotContractError("saved T86 snapshot is invalid JSON") from error
    return _validate_snapshot(payload)


def market_aggregate(snapshot: Mapping[str, Any]) -> dict[str, int]:
    """從逐證券 snapshot 產生既有 market-context 三類合計股數。"""

    canonical = _validate_snapshot(snapshot)
    return {
        "foreign_net": sum(
            row["foreign_ex_dealer_net_shares"]
            for row in canonical["records"]
        ),
        "trust_net": sum(row["investment_trust_net_shares"] for row in canonical["records"]),
        "dealer_net": sum(row["dealer_total_net_shares"] for row in canonical["records"]),
    }


def _validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _TOP_LEVEL_FIELDS:
        raise T86SnapshotContractError("snapshot top-level schema mismatch")
    value = deepcopy(dict(snapshot))
    if value["schema_version"] != SCHEMA_VERSION or value["source_id"] != SOURCE_ID:
        raise T86SnapshotContractError("snapshot version or source mismatch")
    _validate_trade_date(value["trade_date"])
    _validate_retrieved_at(value["retrieved_at"])
    if value["unit"] != "SHARE":
        raise T86SnapshotContractError("snapshot unit must equal SHARE")
    if not isinstance(value["source"], dict) or set(value["source"]) != _SOURCE_FIELDS:
        raise T86SnapshotContractError("snapshot source schema mismatch")
    source = value["source"]
    if (
        source["publisher"] != "Taiwan Stock Exchange"
        or source["endpoint"] != ENDPOINT
        or source["response_date"] != value["trade_date"].replace("-", "")
        or source["select_type"] != SELECT_TYPE
        or not isinstance(source["title"], str)
        or not source["title"].strip()
        or not isinstance(source["hints"], str)
        or "股" not in source["hints"]
    ):
        raise T86SnapshotContractError("snapshot source metadata mismatch")
    if not isinstance(value["integrity"], dict) or set(value["integrity"]) != _INTEGRITY_FIELDS:
        raise T86SnapshotContractError("snapshot integrity schema mismatch")
    records = value["records"]
    if not isinstance(records, list) or not records:
        raise T86SnapshotContractError("snapshot records must be non-empty")
    stock_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
            raise T86SnapshotContractError("snapshot record schema mismatch")
        if not isinstance(record["stock_id"], str) or not _STOCK_ID_PATTERN.fullmatch(
            record["stock_id"]
        ):
            raise T86SnapshotContractError("snapshot stock_id has invalid syntax")
        if record["stock_id"] in stock_ids:
            raise T86SnapshotContractError("snapshot contains duplicate stock_id")
        stock_ids.add(record["stock_id"])
        if not isinstance(record["stock_name"], str) or not record["stock_name"].strip():
            raise T86SnapshotContractError("snapshot stock_name is empty")
        if any(type(record[field]) is not int for field in _INTEGER_FIELDS):
            raise T86SnapshotContractError("snapshot share metrics must be integers")
        _validate_record_arithmetic(record)
    if records != sorted(records, key=lambda row: row["stock_id"]):
        raise T86SnapshotContractError("snapshot records must be sorted by stock_id")
    integrity = value["integrity"]
    if integrity["row_count"] != len(records) or integrity["field_count"] != len(FIELD_MAP):
        raise T86SnapshotContractError("snapshot integrity counts mismatch")
    core = {
        "schema_version": value["schema_version"],
        "source_id": value["source_id"],
        "trade_date": value["trade_date"],
        "unit": value["unit"],
        "source": source,
        "records": records,
    }
    if integrity["canonical_sha256"] != _canonical_hash(core):
        raise T86SnapshotContractError("snapshot checksum mismatch")
    return value


def _validate_record_arithmetic(record: Mapping[str, Any]) -> None:
    groups = (
        ("foreign_ex_dealer_buy_shares", "foreign_ex_dealer_sell_shares", "foreign_ex_dealer_net_shares"),
        ("foreign_dealer_buy_shares", "foreign_dealer_sell_shares", "foreign_dealer_net_shares"),
        ("investment_trust_buy_shares", "investment_trust_sell_shares", "investment_trust_net_shares"),
        ("dealer_self_buy_shares", "dealer_self_sell_shares", "dealer_self_net_shares"),
        ("dealer_hedge_buy_shares", "dealer_hedge_sell_shares", "dealer_hedge_net_shares"),
    )
    for buy_field, sell_field, net_field in groups:
        if record[buy_field] - record[sell_field] != record[net_field]:
            raise T86SnapshotContractError(f"T86 arithmetic mismatch: {net_field}")
    if record["dealer_self_net_shares"] + record["dealer_hedge_net_shares"] != record["dealer_total_net_shares"]:
        raise T86SnapshotContractError("T86 arithmetic mismatch: dealer_total_net_shares")
    expected_total = (
        record["foreign_ex_dealer_net_shares"]
        + record["foreign_dealer_net_shares"]
        + record["investment_trust_net_shares"]
        + record["dealer_total_net_shares"]
    )
    if expected_total != record["all_institutional_net_shares"]:
        raise T86SnapshotContractError("T86 arithmetic mismatch: all_institutional_net_shares")


def _parse_integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise T86SnapshotContractError(f"T86 {field} must be an integer")
    text = str(value).strip().replace(",", "")
    if not _INTEGER_PATTERN.fullmatch(text):
        raise T86SnapshotContractError(f"T86 {field} must be an integer")
    return int(text)


def _validate_trade_date(value: Any) -> str:
    if not isinstance(value, str):
        raise T86SnapshotContractError("trade_date must be YYYY-MM-DD")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise T86SnapshotContractError("trade_date must be a valid YYYY-MM-DD date") from error
    return parsed.strftime("%Y-%m-%d")


def _validate_retrieved_at(value: Any) -> None:
    if not isinstance(value, str):
        raise T86SnapshotContractError("retrieved_at must be RFC3339 UTC")
    try:
        parse_utc_instant(value)
    except ValueError as error:
        raise T86SnapshotContractError("retrieved_at must be RFC3339 UTC") from error


def _canonical_hash(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
