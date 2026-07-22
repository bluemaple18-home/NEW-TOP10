"""TPEx 官方 OpenAPI 單日上櫃三大法人逐證券 snapshot。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from app.tskg.identity import parse_utc_instant
from app.tskg.source_policy import SourcePolicyRegistry, preflight_source


SCHEMA_VERSION = "tskg-tpex-institutional-snapshot-v1"
SOURCE_ID = "tpex-openapi-3insti-daily"
ENDPOINT = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"
ENDPOINT_PATH = "/openapi/v1/tpex_3insti_daily_trading"
REQUEST_HEADERS = {"User-Agent": "TOP10new-TSKG/1.0 (scheduled-local-research)"}
DEFAULT_GOVERNED_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "tskg_source_policy_governed_v1.json"
)

FIELD_MAP = {
    "SecuritiesCompanyCode": "stock_id",
    "CompanyName": "stock_name",
    "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy": "foreign_ex_dealer_buy_shares",
    " Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell": "foreign_ex_dealer_sell_shares",
    "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference": "foreign_ex_dealer_net_shares",
    "Foreign Dealers-Total Buy": "foreign_dealer_buy_shares",
    "Foreign Dealers-TotalSell": "foreign_dealer_sell_shares",
    "ForeignDealers-Difference": "foreign_dealer_net_shares",
    "ForeignInvestorsIncludeMainlandAreaInvestors-TotalBuy": "foreign_total_buy_shares",
    "ForeignInvestorsIncludeMainlandAreaInvestors-TotalSell": "foreign_total_sell_shares",
    "ForeignInvestorsInclude MainlandAreaInvestors-Difference": "foreign_total_net_shares",
    "SecuritiesInvestmentTrustCompanies-TotalBuy": "investment_trust_buy_shares",
    "SecuritiesInvestmentTrustCompanies-TotalSell": "investment_trust_sell_shares",
    "SecuritiesInvestmentTrustCompanies-Difference": "investment_trust_net_shares",
    "Dealers-TotalBuy": "dealer_total_buy_shares",
    "Dealers-TotalSell": "dealer_total_sell_shares",
    "Dealers-Difference": "dealer_total_net_shares",
    "Dealers -TotalSell": "dealer_hedge_sell_shares",
    "TotalDifference": "all_institutional_net_shares",
}
EXPECTED_SOURCE_FIELDS = {"Date", *FIELD_MAP}
RECORD_FIELDS = set(FIELD_MAP.values())
INTEGER_FIELDS = RECORD_FIELDS - {"stock_id", "stock_name"}
TOP_LEVEL_FIELDS = {
    "schema_version", "source_id", "trade_date", "retrieved_at", "unit",
    "source", "integrity", "records",
}
SOURCE_FIELDS = {
    "publisher", "data_providing_organization", "endpoint", "dataset_id",
    "license", "response_date",
}
INTEGRITY_FIELDS = {"row_count", "field_count", "canonical_sha256"}
STOCK_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")
INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
ROC_DATE_PATTERN = re.compile(r"^(\d{3})(\d{2})(\d{2})$")


class TPExInstitutionalContractError(ValueError):
    """TPEx response 或 normalized snapshot 違反 closed contract。"""


def build_tpex_institutional_snapshot(
    payload: Any,
    *,
    retrieved_at: str,
    expected_trade_date: str | None = None,
) -> dict[str, Any]:
    """把官方 OpenAPI response 轉成 deterministic SHARE snapshot。"""

    _validate_retrieved_at(retrieved_at)
    if not isinstance(payload, list) or not payload:
        raise TPExInstitutionalContractError("payload must be a non-empty list")
    if any(not isinstance(row, Mapping) or set(row) != EXPECTED_SOURCE_FIELDS for row in payload):
        raise TPExInstitutionalContractError("TPEx source field set differs from v1 contract")

    response_dates = {row["Date"] for row in payload}
    if len(response_dates) != 1:
        raise TPExInstitutionalContractError("TPEx response must contain exactly one trade date")
    response_date = next(iter(response_dates))
    trade_date = _roc_date(response_date)
    if expected_trade_date is not None and trade_date != _iso_date(expected_trade_date):
        raise TPExInstitutionalContractError("TPEx response date does not match expected date")

    records: list[dict[str, Any]] = []
    stock_ids: set[str] = set()
    for source_row in payload:
        record: dict[str, Any] = {}
        for source_field, target_field in FIELD_MAP.items():
            raw_value = source_row[source_field]
            if target_field == "stock_id":
                if not isinstance(raw_value, str) or not STOCK_ID_PATTERN.fullmatch(raw_value.strip()):
                    raise TPExInstitutionalContractError("invalid TPEx stock_id")
                value: str | int = raw_value.strip()
            elif target_field == "stock_name":
                if not isinstance(raw_value, str) or not raw_value.strip():
                    raise TPExInstitutionalContractError("invalid TPEx stock_name")
                value = raw_value.strip()
            else:
                value = _integer(raw_value, target_field)
            record[target_field] = value
        if record["stock_id"] in stock_ids:
            raise TPExInstitutionalContractError(f"duplicate TPEx stock_id: {record['stock_id']}")
        stock_ids.add(str(record["stock_id"]))
        _validate_arithmetic(record)
        records.append(record)
    records.sort(key=lambda row: str(row["stock_id"]))

    source = {
        "publisher": "Taipei Exchange",
        "data_providing_organization": "金融監督管理委員會證券期貨局",
        "endpoint": ENDPOINT,
        "dataset_id": "data.gov.tw-dataset-11856",
        "license": "Open Government Data License 1.0",
        "response_date": response_date,
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
        **core,
        "retrieved_at": retrieved_at,
        "integrity": {
            "row_count": len(records),
            "field_count": len(EXPECTED_SOURCE_FIELDS),
            "canonical_sha256": _canonical_hash(core),
        },
    }
    return _validate_snapshot(snapshot)


def fetch_tpex_institutional_snapshot(
    *,
    expected_trade_date: str,
    http_get: Callable[..., Any] = requests.get,
    retrieved_at: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """只呼叫官方 OGL OpenAPI 一次；不使用受網站條款限制的歷史頁爬取。"""

    observed_at = retrieved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    registry = SourcePolicyRegistry.from_governed_file(DEFAULT_GOVERNED_POLICY_PATH)

    def reader(_: str) -> Any:
        response = http_get(ENDPOINT, headers=REQUEST_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()

    authorized = preflight_source(
        registry,
        source_id=SOURCE_ID,
        method="GET",
        path=ENDPOINT_PATH,
        media_type="application/json",
        as_of=observed_at,
        reader=reader,
        requested_rate=1,
        requested_concurrency=1,
    )
    if not authorized["ok"]:
        code = authorized["error"]["code"]
        raise TPExInstitutionalContractError(f"TPEx source preflight failed: {code}")
    return build_tpex_institutional_snapshot(
        authorized["reader_result"],
        retrieved_at=observed_at,
        expected_trade_date=expected_trade_date,
    )


def write_tpex_institutional_snapshot(snapshot: Mapping[str, Any], path: Path) -> Path:
    canonical = _validate_snapshot(snapshot)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
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


def load_tpex_institutional_snapshot(path: Path) -> dict[str, Any]:
    return _validate_snapshot(json.loads(Path(path).read_text(encoding="utf-8")))


def market_aggregate(snapshot: Mapping[str, Any]) -> dict[str, int]:
    canonical = _validate_snapshot(snapshot)
    fields = (
        "foreign_ex_dealer_net_shares", "investment_trust_net_shares",
        "dealer_total_net_shares", "all_institutional_net_shares",
    )
    return {field: sum(int(row[field]) for row in canonical["records"]) for field in fields}


def _validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != TOP_LEVEL_FIELDS:
        raise TPExInstitutionalContractError("snapshot top-level shape mismatch")
    data = deepcopy(dict(snapshot))
    if data["schema_version"] != SCHEMA_VERSION or data["source_id"] != SOURCE_ID or data["unit"] != "SHARE":
        raise TPExInstitutionalContractError("snapshot identity mismatch")
    _iso_date(data["trade_date"])
    _validate_retrieved_at(data["retrieved_at"])
    if not isinstance(data["source"], Mapping) or set(data["source"]) != SOURCE_FIELDS:
        raise TPExInstitutionalContractError("snapshot source shape mismatch")
    expected_source = {
        "publisher": "Taipei Exchange",
        "data_providing_organization": "金融監督管理委員會證券期貨局",
        "endpoint": ENDPOINT,
        "dataset_id": "data.gov.tw-dataset-11856",
        "license": "Open Government Data License 1.0",
        "response_date": _to_roc_date(data["trade_date"]),
    }
    if dict(data["source"]) != expected_source:
        raise TPExInstitutionalContractError("snapshot source identity mismatch")
    records = data["records"]
    if not isinstance(records, list) or not records:
        raise TPExInstitutionalContractError("snapshot records must be non-empty")
    if records != sorted(records, key=lambda row: str(row["stock_id"])):
        raise TPExInstitutionalContractError("snapshot records are not canonical")
    if len({row["stock_id"] for row in records}) != len(records):
        raise TPExInstitutionalContractError("snapshot contains duplicate stock_id")
    for record in records:
        if not isinstance(record, Mapping) or set(record) != RECORD_FIELDS:
            raise TPExInstitutionalContractError("snapshot record shape mismatch")
        if not isinstance(record["stock_id"], str) or not STOCK_ID_PATTERN.fullmatch(record["stock_id"]):
            raise TPExInstitutionalContractError("snapshot stock_id mismatch")
        if not isinstance(record["stock_name"], str) or not record["stock_name"]:
            raise TPExInstitutionalContractError("snapshot stock_name mismatch")
        if any(type(record[field]) is not int for field in INTEGER_FIELDS):
            raise TPExInstitutionalContractError("snapshot numeric field mismatch")
        _validate_arithmetic(record)
    integrity = data["integrity"]
    if not isinstance(integrity, Mapping) or set(integrity) != INTEGRITY_FIELDS:
        raise TPExInstitutionalContractError("snapshot integrity shape mismatch")
    if integrity["row_count"] != len(records) or integrity["field_count"] != len(EXPECTED_SOURCE_FIELDS):
        raise TPExInstitutionalContractError("snapshot integrity count mismatch")
    core = {key: data[key] for key in ("schema_version", "source_id", "trade_date", "unit", "source", "records")}
    if integrity["canonical_sha256"] != _canonical_hash(core):
        raise TPExInstitutionalContractError("snapshot checksum mismatch")
    return data


def _validate_arithmetic(record: Mapping[str, Any]) -> None:
    triplets = (
        ("foreign_ex_dealer_buy_shares", "foreign_ex_dealer_sell_shares", "foreign_ex_dealer_net_shares"),
        ("foreign_dealer_buy_shares", "foreign_dealer_sell_shares", "foreign_dealer_net_shares"),
        ("foreign_total_buy_shares", "foreign_total_sell_shares", "foreign_total_net_shares"),
        ("investment_trust_buy_shares", "investment_trust_sell_shares", "investment_trust_net_shares"),
        ("dealer_total_buy_shares", "dealer_total_sell_shares", "dealer_total_net_shares"),
    )
    for buy, sell, net in triplets:
        if record[buy] - record[sell] != record[net]:
            raise TPExInstitutionalContractError(f"TPEx arithmetic mismatch: {net}")
    if record["foreign_ex_dealer_net_shares"] + record["foreign_dealer_net_shares"] != record["foreign_total_net_shares"]:
        raise TPExInstitutionalContractError("TPEx foreign total arithmetic mismatch")
    expected_total = (
        record["foreign_ex_dealer_net_shares"]
        + record["investment_trust_net_shares"]
        + record["dealer_total_net_shares"]
    )
    if expected_total != record["all_institutional_net_shares"]:
        raise TPExInstitutionalContractError("TPEx institutional total arithmetic mismatch")


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, str):
        raise TPExInstitutionalContractError(f"{field} must be a string integer")
    compact = value.replace(",", "").strip()
    if not INTEGER_PATTERN.fullmatch(compact):
        raise TPExInstitutionalContractError(f"{field} has invalid integer syntax")
    return int(compact)


def _roc_date(value: Any) -> str:
    if not isinstance(value, str) or not (match := ROC_DATE_PATTERN.fullmatch(value)):
        raise TPExInstitutionalContractError("TPEx Date must use YYYMMDD ROC format")
    year, month, day = int(match.group(1)) + 1911, int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError as error:
        raise TPExInstitutionalContractError("TPEx Date is invalid") from error


def _to_roc_date(value: str) -> str:
    parsed = date.fromisoformat(_iso_date(value))
    return f"{parsed.year - 1911:03d}{parsed.month:02d}{parsed.day:02d}"


def _iso_date(value: Any) -> str:
    if not isinstance(value, str):
        raise TPExInstitutionalContractError("trade_date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise TPExInstitutionalContractError("trade_date must be YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise TPExInstitutionalContractError("trade_date must be canonical YYYY-MM-DD")
    return value


def _validate_retrieved_at(value: Any) -> None:
    try:
        parse_utc_instant(value)
    except (TypeError, ValueError) as error:
        raise TPExInstitutionalContractError("retrieved_at must be RFC3339 UTC") from error


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()
