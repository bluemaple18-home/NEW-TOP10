"""Provider-neutral finalized Daily Close immutable snapshot 契約。"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from app.research.contracts import CANONICALIZATION_VERSION, content_hash
from app.research.receipt_store import ImmutableCollisionError, write_immutable_json


SCHEMA_VERSION = "daily-close-snapshot.v1"
RECORDS_SCHEMA_VERSION = "daily-close-records.v1"
IDENTITY_KIND = "DAILY_CLOSE_SNAPSHOT_V1"
FINALIZATION_STATUS = "FINALIZED_EOD"
PRICE_BASIS = "UNADJUSTED"
ALLOWED_MARKETS = frozenset({"TWSE", "TPEX"})
REQUIRED_COLUMNS = (
    "date",
    "stock_id",
    "stock_name",
    "market",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
)
NULLABLE_COLUMNS = ("transactions",)
RECORD_COLUMNS = REQUIRED_COLUMNS + NULLABLE_COLUMNS
NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "value")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
FINALIZATION_AUTHORITY = "OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1"
OBSERVATION_TIMEZONE = "Asia/Taipei"
DAILY_CLOSE_CUTOFF = time(15, 30)


class DailyCloseSnapshotError(ValueError):
    """Daily Close input 或 immutable snapshot 不符合契約。"""


@dataclass(frozen=True)
class DailyCloseValidationResult:
    status: str
    snapshot_id: str
    errors: list[str]


@dataclass(frozen=True)
class DailyCloseSnapshot:
    frame: pd.DataFrame
    manifest: dict[str, Any]
    records_path: Path
    manifest_path: Path
    write_status: str = "LOADED"


def _canonical_number(value: object) -> str:
    normalized = format(Decimal(str(value)).normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _utc_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DailyCloseSnapshotError("fetched_at must be an RFC3339 UTC timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise DailyCloseSnapshotError("fetched_at must be UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def _calendar_date(value: str, field: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise DailyCloseSnapshotError(f"{field} must be a calendar date") from exc
    if parsed.tzinfo is not None or parsed != parsed.normalize():
        raise DailyCloseSnapshotError(f"{field} must be a calendar date")
    return parsed


def _finalization_contract(
    frame: pd.DataFrame,
    *,
    source: Mapping[str, Any],
    fetched_at: str,
) -> dict[str, Any]:
    endpoint = source.get("endpoint_contract")
    authority = endpoint.get("finalization_authority") if isinstance(endpoint, Mapping) else None
    if authority != FINALIZATION_AUTHORITY:
        raise DailyCloseSnapshotError("official finalized-daily endpoint authority is required")
    fetched = datetime.fromisoformat(_utc_timestamp(fetched_at).replace("Z", "+00:00"))
    local_fetched = fetched.astimezone(ZoneInfo(OBSERVATION_TIMEZONE))
    observed_through = None if frame.empty else frame["date"].max().date()
    if observed_through is not None:
        if local_fetched.date() < observed_through:
            raise DailyCloseSnapshotError("fetched_at is earlier than observed trading date")
        if local_fetched.date() == observed_through and local_fetched.time() < DAILY_CLOSE_CUTOFF:
            raise DailyCloseSnapshotError("same-day observation is before official Daily Close cutoff")
    return {
        "contract_version": "daily-close-finalization.v2",
        "status": FINALIZATION_STATUS if observed_through is not None else "UNRESOLVED_NO_OBSERVATION",
        "authority": authority,
        "observation_policy_version": "daily-close-observation.v1",
        "observed_at_policy": "TRADING_DATE_DAY_PRECISION",
        "timezone": OBSERVATION_TIMEZONE,
        "official_daily_close_cutoff": DAILY_CLOSE_CUTOFF.isoformat(),
        "cutoff_policy_version": "twse-tpex-daily-close-cutoff.v1",
        "observed_through_date": observed_through.isoformat() if observed_through else None,
    }


def _canonicalize_frame(
    frame: pd.DataFrame,
    *,
    requested_start: str,
    requested_end: str,
    price_basis: str,
    finalization_status: str,
) -> pd.DataFrame:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise DailyCloseSnapshotError(f"required columns missing: {missing_columns}")
    if price_basis != PRICE_BASIS:
        raise DailyCloseSnapshotError("price basis drift: this contract requires UNADJUSTED")
    if finalization_status != FINALIZATION_STATUS:
        raise DailyCloseSnapshotError("finalization drift: this contract requires FINALIZED_EOD")

    normalized = frame.loc[:, REQUIRED_COLUMNS].copy()
    if normalized.isna().any().any():
        raise DailyCloseSnapshotError("required value must not be null")
    normalized["transactions"] = frame["transactions"] if "transactions" in frame.columns else pd.NA
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.normalize()
    if normalized["date"].isna().any():
        raise DailyCloseSnapshotError("required value date is invalid")
    normalized["stock_id"] = normalized["stock_id"].astype(str).str.strip()
    normalized["stock_name"] = normalized["stock_name"].astype(str).str.strip()
    if (normalized["stock_id"] == "").any() or (normalized["stock_name"] == "").any():
        raise DailyCloseSnapshotError("required value stock identity must not be blank")
    normalized["market"] = normalized["market"].astype(str).str.strip().str.upper()
    invalid_markets = sorted(set(normalized["market"]) - ALLOWED_MARKETS)
    if invalid_markets:
        raise DailyCloseSnapshotError(f"market is invalid: {invalid_markets}")

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any() or not normalized[column].map(math.isfinite).all():
            raise DailyCloseSnapshotError(f"required value {column} must be finite")
    if (normalized[["open", "high", "low", "close"]] <= 0).any().any():
        raise DailyCloseSnapshotError("OHLC values must be positive")
    if (
        (normalized["low"] > normalized["high"])
        | (normalized["open"] < normalized["low"])
        | (normalized["open"] > normalized["high"])
        | (normalized["close"] < normalized["low"])
        | (normalized["close"] > normalized["high"])
    ).any():
        raise DailyCloseSnapshotError("OHLC invariant is invalid")
    for column in ("volume", "value"):
        if (normalized[column] < 0).any():
            raise DailyCloseSnapshotError(f"{column} must not be negative")
    transactions = pd.to_numeric(normalized["transactions"], errors="coerce")
    invalid_transactions = normalized["transactions"].notna() & (
        transactions.isna() | ~transactions.fillna(0).map(math.isfinite) | (transactions < 0)
    )
    if invalid_transactions.any():
        raise DailyCloseSnapshotError("transactions must be null or finite and non-negative")
    normalized["transactions"] = transactions

    if "price_basis" in frame.columns:
        observed = set(frame["price_basis"].dropna().astype(str).str.strip().str.upper())
        if observed != {price_basis} or frame["price_basis"].isna().any():
            raise DailyCloseSnapshotError("price basis drift in Daily Close records")
    if "finalization_status" in frame.columns:
        observed = set(frame["finalization_status"].dropna().astype(str).str.strip().str.upper())
        if observed != {finalization_status} or frame["finalization_status"].isna().any():
            raise DailyCloseSnapshotError("finalization drift in Daily Close records")

    duplicate = normalized.duplicated(["date", "stock_id"], keep=False)
    if duplicate.any():
        raise DailyCloseSnapshotError("duplicate (date, stock_id) Daily Close record")
    start = _calendar_date(requested_start, "requested_start")
    end = _calendar_date(requested_end, "requested_end")
    if start > end:
        raise DailyCloseSnapshotError("requested_start must be <= requested_end")
    business_dates = set(pd.bdate_range(start, end))
    if not normalized.empty and not set(normalized["date"]).issubset(business_dates):
        raise DailyCloseSnapshotError("trading date is outside requested business-day candidates")
    return normalized.sort_values(["date", "stock_id"], kind="mergesort").reset_index(drop=True)


def _iter_records(frame: pd.DataFrame):
    for row in frame.itertuples(index=False):
        yield {
            "date": row.date.date().isoformat(),
            "stock_id": row.stock_id,
            "stock_name": row.stock_name,
            "market": row.market,
            "open": _canonical_number(row.open),
            "high": _canonical_number(row.high),
            "low": _canonical_number(row.low),
            "close": _canonical_number(row.close),
            "volume": _canonical_number(row.volume),
            "value": _canonical_number(row.value),
            "transactions": None if pd.isna(row.transactions) else _canonical_number(row.transactions),
        }


def _json_line(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _write_records_stream(root: Path, frame: pd.DataFrame) -> tuple[str, Path, str]:
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    temp = data_dir / f".daily-close.{secrets.token_hex(8)}.tmp"
    metadata = {
        "schema_version": RECORDS_SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "columns": list(RECORD_COLUMNS),
        "record_count": len(frame),
    }
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
                compressed.write(_json_line(metadata))
                for record in _iter_records(frame):
                    compressed.write(_json_line(record))
            raw.flush()
            os.fsync(raw.fileno())
        content_id = _sha256_file(temp)
        target = data_dir / f"{content_id[7:]}.jsonl.gz"
        try:
            os.link(temp, target)
            status = "CREATED"
        except FileExistsError:
            if _sha256_file(target) != content_id:
                raise ImmutableCollisionError(f"immutable target collision: {target}")
            status = "EXISTS_IDENTICAL"
        directory = os.open(data_dir, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return content_id, target, status
    finally:
        temp.unlink(missing_ok=True)


def _coverage_and_evidence(
    frame: pd.DataFrame,
    *,
    requested_start: str,
    requested_end: str,
    expected_markets: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    markets = sorted({str(market).strip().upper() for market in expected_markets})
    if not markets or set(markets) - ALLOWED_MARKETS:
        raise DailyCloseSnapshotError("expected markets are invalid")
    dates = [item.date().isoformat() for item in pd.bdate_range(requested_start, requested_end)]
    if not dates:
        raise DailyCloseSnapshotError("requested range must include a business-day candidate")
    if set(frame["market"]) - set(markets):
        raise DailyCloseSnapshotError("observed market is outside expected markets")
    observations = {
        (row.date.date().isoformat(), row.market)
        for row in frame[["date", "market"]].drop_duplicates().itertuples(index=False)
    }
    no_observation = [
        {"date": day, "status": "UNRESOLVED_NO_OBSERVATION"}
        for day in dates
        if not any((day, market) in observations for market in markets)
    ]
    partial_market: list[dict[str, Any]] = []
    for day in dates:
        observed = sorted(market for market in markets if (day, market) in observations)
        missing = sorted(set(markets) - set(observed))
        if observed and missing:
            partial_market.append(
                {
                    "date": day,
                    "observed_markets": observed,
                    "missing_markets": missing,
                    "status": "PARTIAL_MARKET_OBSERVATION",
                }
            )
    expected_count = len(dates) * len(markets)
    observed_count = len(observations)
    status = "EMPTY" if observed_count == 0 else "COMPLETE" if observed_count == expected_count else "PARTIAL"
    actual_dates = frame["date"] if not frame.empty else None
    coverage = {
        "schema_version": "dataset-component-coverage.v1",
        "status": status,
        "expected_member_count": expected_count,
        "observed_member_count": observed_count,
        "date_start": actual_dates.min().date().isoformat() if actual_dates is not None else None,
        "date_end": actual_dates.max().date().isoformat() if actual_dates is not None else None,
    }
    evidence = {
        "business_date_contract": "WEEKDAY_CANDIDATES_V1",
        "business_date_candidates": dates,
        "expected_markets": markets,
        "no_observation_dates": no_observation,
        "partial_market_dates": partial_market,
    }
    resolution = (
        "UNRESOLVED_NO_OBSERVATION"
        if observed_count == 0
        else "RESOLVED_WITH_GAPS"
        if no_observation or partial_market
        else "RESOLVED"
    )
    return coverage, evidence, resolution


def validate_daily_close_manifest(payload: Mapping[str, Any]) -> DailyCloseValidationResult:
    errors: list[str] = []
    if set(payload) != {"snapshot_id", "identity_payload"}:
        errors.append("manifest fields are invalid")
    identity = payload.get("identity_payload")
    if not isinstance(identity, Mapping):
        return DailyCloseValidationResult("INVALID", "", errors + ["identity_payload is required"])
    expected = {
        "schema_version",
        "canonicalization_version",
        "identity_kind",
        "resolution_status",
        "records_content_id",
        "source",
        "fetched_at",
        "finalization",
        "price_basis",
        "coverage",
        "observation_evidence",
    }
    if set(identity) != expected:
        errors.append("identity_payload fields are invalid")
    if identity.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version is invalid")
    if identity.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    if identity.get("identity_kind") != IDENTITY_KIND:
        errors.append("identity_kind is invalid")
    if identity.get("resolution_status") not in {"RESOLVED", "RESOLVED_WITH_GAPS", "UNRESOLVED_NO_OBSERVATION"}:
        errors.append("resolution_status is invalid")
    if not isinstance(identity.get("records_content_id"), str) or not _HASH_RE.match(str(identity.get("records_content_id"))):
        errors.append("records_content_id is invalid")
    source = identity.get("source")
    if not isinstance(source, Mapping) or set(source) != {"provider_identity", "adapter_contract", "endpoint_contract"}:
        errors.append("source contract is invalid")
    elif (
        not isinstance(source.get("provider_identity"), str)
        or not source["provider_identity"].strip()
        or not isinstance(source.get("adapter_contract"), str)
        or not source["adapter_contract"].strip()
        or not isinstance(source.get("endpoint_contract"), Mapping)
        or not source["endpoint_contract"]
    ):
        errors.append("source identity must be exact and non-empty")
    elif source["endpoint_contract"].get("finalization_authority") != FINALIZATION_AUTHORITY:
        errors.append("source finalization authority is invalid")
    try:
        _utc_timestamp(str(identity.get("fetched_at")))
    except DailyCloseSnapshotError as exc:
        errors.append(str(exc))
    finalization = identity.get("finalization")
    expected_finalization_fields = {
        "contract_version", "status", "authority", "observation_policy_version",
        "observed_at_policy", "timezone", "official_daily_close_cutoff",
        "cutoff_policy_version", "observed_through_date",
    }
    if not isinstance(finalization, Mapping) or set(finalization) != expected_finalization_fields:
        errors.append("finalization contract drift")
    else:
        expected_status = "UNRESOLVED_NO_OBSERVATION" if identity.get("resolution_status") == "UNRESOLVED_NO_OBSERVATION" else FINALIZATION_STATUS
        if finalization != {
            "contract_version": "daily-close-finalization.v2",
            "status": expected_status,
            "authority": FINALIZATION_AUTHORITY,
            "observation_policy_version": "daily-close-observation.v1",
            "observed_at_policy": "TRADING_DATE_DAY_PRECISION",
            "timezone": OBSERVATION_TIMEZONE,
            "official_daily_close_cutoff": DAILY_CLOSE_CUTOFF.isoformat(),
            "cutoff_policy_version": "twse-tpex-daily-close-cutoff.v1",
            "observed_through_date": coverage.get("date_end") if isinstance(coverage := identity.get("coverage"), Mapping) else None,
        }:
            errors.append("finalization contract drift")
        observed_through = finalization.get("observed_through_date")
        if observed_through is not None:
            try:
                observed_date = _calendar_date(str(observed_through), "finalization.observed_through_date").date()
                fetched = datetime.fromisoformat(_utc_timestamp(str(identity.get("fetched_at"))).replace("Z", "+00:00"))
                local_fetched = fetched.astimezone(ZoneInfo(OBSERVATION_TIMEZONE))
                if local_fetched.date() < observed_date:
                    errors.append("fetched_at is earlier than observed trading date")
                elif local_fetched.date() == observed_date and local_fetched.time() < DAILY_CLOSE_CUTOFF:
                    errors.append("same-day observation is before official Daily Close cutoff")
            except DailyCloseSnapshotError as exc:
                errors.append(str(exc))
    if identity.get("price_basis") != {
        "adjustment_policy": "NONE",
        "basis": PRICE_BASIS,
        "contract_version": "daily-close-price-basis.v1",
    }:
        errors.append("price basis contract drift")
    coverage = identity.get("coverage")
    if not isinstance(coverage, Mapping) or set(coverage) != {
        "schema_version", "status", "expected_member_count", "observed_member_count", "date_start", "date_end"
    }:
        errors.append("coverage contract is invalid")
    else:
        expected_count = coverage.get("expected_member_count")
        observed_count = coverage.get("observed_member_count")
        status = coverage.get("status")
        if coverage.get("schema_version") != "dataset-component-coverage.v1":
            errors.append("coverage schema_version is invalid")
        if status not in {"COMPLETE", "PARTIAL", "EMPTY"}:
            errors.append("coverage status is invalid")
        if (
            not isinstance(expected_count, int)
            or isinstance(expected_count, bool)
            or expected_count <= 0
            or not isinstance(observed_count, int)
            or isinstance(observed_count, bool)
            or observed_count < 0
            or observed_count > expected_count
        ):
            errors.append("coverage counts are invalid")
        if status == "COMPLETE" and expected_count != observed_count:
            errors.append("COMPLETE coverage counts drift")
        if status == "PARTIAL" and not (
            isinstance(observed_count, int) and isinstance(expected_count, int) and 0 < observed_count < expected_count
        ):
            errors.append("PARTIAL coverage counts drift")
        if status == "EMPTY" and observed_count != 0:
            errors.append("EMPTY coverage counts drift")
        if status == "EMPTY":
            if coverage.get("date_start") is not None or coverage.get("date_end") is not None:
                errors.append("EMPTY coverage dates must be null")
        else:
            try:
                start = _calendar_date(str(coverage.get("date_start")), "coverage.date_start")
                end = _calendar_date(str(coverage.get("date_end")), "coverage.date_end")
                if start > end:
                    errors.append("coverage date range is invalid")
            except DailyCloseSnapshotError as exc:
                errors.append(str(exc))
    evidence = identity.get("observation_evidence")
    if not isinstance(evidence, Mapping) or set(evidence) != {
        "business_date_contract", "business_date_candidates", "expected_markets", "no_observation_dates", "partial_market_dates"
    }:
        errors.append("observation evidence contract is invalid")
    else:
        candidates = evidence.get("business_date_candidates")
        expected_markets = evidence.get("expected_markets")
        no_observation = evidence.get("no_observation_dates")
        partial_market = evidence.get("partial_market_dates")
        if evidence.get("business_date_contract") != "WEEKDAY_CANDIDATES_V1":
            errors.append("business date contract is invalid")
        if (
            not isinstance(candidates, list)
            or not candidates
            or not all(isinstance(item, str) for item in candidates)
            or candidates != sorted(candidates)
            or len(candidates) != len(set(candidates))
        ):
            errors.append("business date candidates must be sorted and unique")
        if (
            not isinstance(expected_markets, list)
            or not expected_markets
            or not all(isinstance(item, str) for item in expected_markets)
            or expected_markets != sorted(expected_markets)
            or len(expected_markets) != len(set(expected_markets))
            or set(expected_markets) - ALLOWED_MARKETS
        ):
            errors.append("expected markets are invalid")
        if not isinstance(no_observation, list) or any(
            not isinstance(item, Mapping)
            or set(item) != {"date", "status"}
            or item.get("status") != "UNRESOLVED_NO_OBSERVATION"
            for item in (no_observation if isinstance(no_observation, list) else [])
        ):
            errors.append("no-observation evidence is invalid")
        if not isinstance(partial_market, list) or any(
            not isinstance(item, Mapping)
            or set(item) != {"date", "observed_markets", "missing_markets", "status"}
            or item.get("status") != "PARTIAL_MARKET_OBSERVATION"
            for item in (partial_market if isinstance(partial_market, list) else [])
        ):
            errors.append("partial-market evidence is invalid")
        resolution = identity.get("resolution_status")
        coverage_status = coverage.get("status") if isinstance(coverage, Mapping) else None
        if coverage_status == "EMPTY" and resolution != "UNRESOLVED_NO_OBSERVATION":
            errors.append("empty coverage must remain unresolved")
        if coverage_status == "COMPLETE" and resolution != "RESOLVED":
            errors.append("complete coverage resolution drift")
        if coverage_status == "PARTIAL" and resolution != "RESOLVED_WITH_GAPS":
            errors.append("partial coverage resolution drift")
    computed = content_hash(identity)
    if payload.get("snapshot_id") != computed:
        errors.append("snapshot_id must equal canonical identity payload hash")
    return DailyCloseValidationResult("VALID" if not errors else "INVALID", computed, errors)


def materialize_daily_close_snapshot(
    frame: pd.DataFrame,
    *,
    root: Path,
    source: Mapping[str, Any],
    fetched_at: str,
    requested_start: str,
    requested_end: str,
    expected_markets: Sequence[str] = ("TPEX", "TWSE"),
    price_basis: str = PRICE_BASIS,
    finalization_status: str = FINALIZATION_STATUS,
) -> DailyCloseSnapshot:
    """驗證、正規化並原子寫入 content-addressed records 與 manifest。"""

    if set(source) != {"provider_identity", "adapter_contract", "endpoint_contract"}:
        raise DailyCloseSnapshotError("source contract must contain exact provider, adapter, and endpoint identity")
    if (
        not isinstance(source.get("provider_identity"), str)
        or not str(source["provider_identity"]).strip()
        or not isinstance(source.get("adapter_contract"), str)
        or not str(source["adapter_contract"]).strip()
        or not isinstance(source.get("endpoint_contract"), Mapping)
        or not source["endpoint_contract"]
    ):
        raise DailyCloseSnapshotError("source identity must be exact and non-empty")
    normalized = _canonicalize_frame(
        frame,
        requested_start=requested_start,
        requested_end=requested_end,
        price_basis=price_basis,
        finalization_status=finalization_status,
    )
    coverage, evidence, resolution = _coverage_and_evidence(
        normalized,
        requested_start=requested_start,
        requested_end=requested_end,
        expected_markets=expected_markets,
    )
    finalization = _finalization_contract(normalized, source=source, fetched_at=fetched_at)
    records_content_id, records_path, records_write_status = _write_records_stream(root, normalized)
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "identity_kind": IDENTITY_KIND,
        "resolution_status": resolution,
        "records_content_id": records_content_id,
        "source": dict(source),
        "fetched_at": _utc_timestamp(fetched_at),
        "finalization": finalization,
        "price_basis": {
            "adjustment_policy": "NONE",
            "basis": price_basis,
            "contract_version": "daily-close-price-basis.v1",
        },
        "coverage": coverage,
        "observation_evidence": evidence,
    }
    manifest = {"snapshot_id": content_hash(identity_payload), "identity_payload": identity_payload}
    manifest_path = root / "manifests" / f"{manifest['snapshot_id'][7:]}.json"
    manifest_write = write_immutable_json(
        manifest_path,
        manifest,
        validator=lambda item: validate_daily_close_manifest(item).errors,
        identity_field="snapshot_id",
    )
    loaded = load_daily_close_snapshot(manifest_path)
    status = "EXISTS_IDENTICAL" if records_write_status == manifest_write.status == "EXISTS_IDENTICAL" else "CREATED"
    return replace(loaded, write_status=status)


def load_daily_close_snapshot(
    manifest_path: Path | str,
    *,
    records_path: Path | str | None = None,
) -> DailyCloseSnapshot:
    """從 immutable manifest 重新驗證並載入 canonical records。"""

    path = Path(manifest_path)
    external_records_path = Path(records_path) if records_path is not None else None
    if not path.is_file() or path.is_symlink() or (external_records_path is None and path.parent.name != "manifests"):
        raise DailyCloseSnapshotError("Daily Close manifest must be a regular content-addressed manifest file")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DailyCloseSnapshotError("Daily Close manifest is not valid JSON") from exc
    result = validate_daily_close_manifest(manifest)
    if result.errors:
        raise DailyCloseSnapshotError("; ".join(result.errors))
    if external_records_path is None and path.stem != result.snapshot_id[7:]:
        raise DailyCloseSnapshotError("Daily Close manifest path does not match snapshot identity")
    records_id = manifest["identity_payload"]["records_content_id"]
    resolved_records_path = external_records_path or path.parent.parent / "data" / f"{records_id[7:]}.jsonl.gz"
    if not resolved_records_path.is_file() or resolved_records_path.is_symlink():
        raise DailyCloseSnapshotError("Daily Close records artifact is missing")
    if _sha256_file(resolved_records_path) != records_id:
        raise DailyCloseSnapshotError("Daily Close records artifact identity is invalid")
    if external_records_path is None and resolved_records_path.name != f"{records_id[7:]}.jsonl.gz":
        raise DailyCloseSnapshotError("Daily Close records path does not match content identity")
    try:
        with gzip.open(resolved_records_path, "rb") as handle:
            metadata_line = handle.readline()
            metadata = json.loads(metadata_line)
            expected_metadata = {
                "schema_version": RECORDS_SCHEMA_VERSION,
                "canonicalization_version": CANONICALIZATION_VERSION,
                "columns": list(RECORD_COLUMNS),
                "record_count": metadata.get("record_count"),
            }
            if (
                metadata != expected_metadata
                or not isinstance(metadata.get("record_count"), int)
                or metadata["record_count"] < 0
                or metadata_line != _json_line(metadata)
            ):
                raise DailyCloseSnapshotError("Daily Close records metadata is invalid")
            previous_key: tuple[str, str] | None = None

            def rows():
                nonlocal previous_key
                count = 0
                for line in handle:
                    record = json.loads(line)
                    if not isinstance(record, Mapping) or set(record) != set(RECORD_COLUMNS) or line != _json_line(record):
                        raise DailyCloseSnapshotError("Daily Close record is not canonical")
                    key = (str(record["date"]), str(record["stock_id"]))
                    if previous_key is not None and key <= previous_key:
                        raise DailyCloseSnapshotError("Daily Close records are not sorted and unique")
                    previous_key = key
                    count += 1
                    yield record
                if count != metadata["record_count"]:
                    raise DailyCloseSnapshotError("Daily Close record count drift")

            raw = pd.DataFrame.from_records(rows(), columns=RECORD_COLUMNS)
    except (OSError, EOFError, json.JSONDecodeError) as exc:
        raise DailyCloseSnapshotError("Daily Close records artifact is not valid JSONL gzip") from exc
    evidence = manifest["identity_payload"]["observation_evidence"]
    business_dates = evidence["business_date_candidates"]
    if not business_dates:
        raise DailyCloseSnapshotError("Daily Close business date evidence must not be empty")
    normalized = _canonicalize_frame(
        raw,
        requested_start=business_dates[0],
        requested_end=business_dates[-1],
        price_basis=manifest["identity_payload"]["price_basis"]["basis"],
        finalization_status=FINALIZATION_STATUS,
    )
    observed_rows = (dict(zip(RECORD_COLUMNS, row, strict=True)) for row in raw.itertuples(index=False, name=None))
    for canonical, observed in zip(_iter_records(normalized), observed_rows, strict=True):
        if canonical != observed:
            raise DailyCloseSnapshotError("Daily Close records are not canonical and deterministic")
    recomputed_coverage, recomputed_evidence, recomputed_resolution = _coverage_and_evidence(
        normalized,
        requested_start=business_dates[0],
        requested_end=business_dates[-1],
        expected_markets=evidence["expected_markets"],
    )
    identity = manifest["identity_payload"]
    if (
        identity["coverage"] != recomputed_coverage
        or identity["observation_evidence"] != recomputed_evidence
        or identity["resolution_status"] != recomputed_resolution
        or identity["finalization"] != _finalization_contract(
            normalized,
            source=identity["source"],
            fetched_at=identity["fetched_at"],
        )
    ):
        raise DailyCloseSnapshotError("Daily Close coverage or observation evidence drift")
    return DailyCloseSnapshot(normalized, dict(manifest), resolved_records_path, path)


def load_daily_close_snapshot_from_component(
    corpus_root: Path | str,
    component: Mapping[str, Any],
) -> DailyCloseSnapshot:
    """由 DatasetBundle 的 corpus-relative refs 重建 exact Daily Close snapshot。"""

    root = Path(corpus_root)
    ref_pattern = re.compile(r"^source_corpus/sha256/[0-9a-f]{64}$")
    manifest_ref = component.get("manifest_ref")
    records_ref = component.get("records_ref")
    if (
        component.get("role") != "DAILY_CLOSE_SNAPSHOT"
        or not isinstance(manifest_ref, str)
        or not isinstance(records_ref, str)
        or not ref_pattern.fullmatch(manifest_ref)
        or not ref_pattern.fullmatch(records_ref)
    ):
        raise DailyCloseSnapshotError("Daily Close component refs are invalid")
    manifest_path = root / manifest_ref
    records_path = root / records_ref
    if _sha256_file(manifest_path) != f"sha256:{Path(manifest_ref).name}":
        raise DailyCloseSnapshotError("Daily Close corpus manifest ref identity is invalid")
    if _sha256_file(records_path) != f"sha256:{Path(records_ref).name}":
        raise DailyCloseSnapshotError("Daily Close corpus records ref identity is invalid")
    snapshot = load_daily_close_snapshot(manifest_path, records_path=records_path)
    if snapshot.manifest["snapshot_id"] != component.get("content_id"):
        raise DailyCloseSnapshotError("Daily Close component content_id drift")
    return snapshot
