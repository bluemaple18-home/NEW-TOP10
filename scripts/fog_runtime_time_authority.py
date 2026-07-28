#!/usr/bin/env python3
"""Fog runtime 的單一市場時間與 freshness authority。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path("config/fog_runtime_time_authority_v1.json")
UTC_Z_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
EXPECTED_POLICY: dict[str, Any] = {
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


class TimeAuthorityError(ValueError):
    """時間 authority fail-closed 錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _resolve_policy_path(
    policy_path: str | Path | None,
    project_root: str | Path,
) -> Path:
    root = Path(project_root).resolve()
    path = Path(policy_path) if policy_path is not None else POLICY_PATH
    if path.is_absolute():
        return path
    return root / path


def load_policy(
    policy_path: str | Path | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    path = _resolve_policy_path(policy_path, project_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TimeAuthorityError("TIME_AUTHORITY_LOAD_FAILED", str(error)) from error
    if payload != EXPECTED_POLICY:
        raise TimeAuthorityError(
            "TIME_AUTHORITY_CONTRACT_DRIFT",
            "repo policy 不等於 fog-runtime-time-authority.v1 semantic authority",
        )
    if canonical_json_hash(payload) != (
        "67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357"
    ):
        raise TimeAuthorityError("TIME_AUTHORITY_HASH_DRIFT", "canonical policy hash 錯誤")
    return payload


def parse_utc_z(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise TimeAuthorityError("NAIVE_TIMESTAMP", "datetime 必須 timezone-aware")
        return value.astimezone(UTC)
    if not isinstance(value, str) or UTC_Z_PATTERN.fullmatch(value) is None:
        raise TimeAuthorityError("NON_CANONICAL_UTC_TIMESTAMP", "必須是 RFC3339 UTC Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise TimeAuthorityError("INVALID_UTC_TIMESTAMP", value) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimeAuthorityError("NAIVE_TIMESTAMP", value)
    canonical = format_utc_z(parsed)
    if canonical != value:
        raise TimeAuthorityError("NON_CANONICAL_UTC_TIMESTAMP", value)
    return parsed.astimezone(UTC)


def format_utc_z(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TimeAuthorityError("NAIVE_TIMESTAMP", "datetime 必須 timezone-aware")
    normalized = value.astimezone(UTC)
    timespec = "microseconds" if normalized.microsecond else "seconds"
    return normalized.isoformat(timespec=timespec).replace("+00:00", "Z")


def format_market_datetime(value: str | datetime) -> str:
    instant = parse_utc_z(value)
    local = instant.astimezone(ZoneInfo("Asia/Taipei"))
    timespec = "microseconds" if local.microsecond else "seconds"
    return local.isoformat(timespec=timespec)


def derive_market_run_date(
    instant_utc: str | datetime,
    policy: dict[str, Any] | None = None,
) -> str:
    effective_policy = EXPECTED_POLICY if policy is None else policy
    if effective_policy != EXPECTED_POLICY:
        raise TimeAuthorityError("TIME_AUTHORITY_CONTRACT_DRIFT", "不接受 policy override")
    zone = ZoneInfo(effective_policy["market_timezone"])
    return parse_utc_z(instant_utc).astimezone(zone).date().isoformat()


def validate_date(value: str, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise TimeAuthorityError("INVALID_DATE", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise TimeAuthorityError("INVALID_DATE", field) from error
    if parsed.isoformat() != value:
        raise TimeAuthorityError("INVALID_DATE", field)
    return value


def build_run_context(
    instant_utc: str | datetime,
    *,
    project_root: str | Path = PROJECT_ROOT,
    policy_path: str | Path | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path, project_root=project_root)
    normalized = parse_utc_z(instant_utc)
    market_run_date = derive_market_run_date(normalized, policy)
    return {
        "schema_version": "fog-runtime-run-context.v1",
        "time_authority_schema_version": policy["schema_version"],
        "time_contract_hash": canonical_json_hash(policy),
        "market_id": policy["market_id"],
        "market_timezone": policy["market_timezone"],
        "run_context_created_at_utc": format_utc_z(normalized),
        "run_context_market_datetime": format_market_datetime(normalized),
        "market_run_date": market_run_date,
        "artifact_run_date": market_run_date,
    }


def validate_run_context(
    context: dict[str, Any],
    *,
    project_root: str | Path = PROJECT_ROOT,
    policy_path: str | Path | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path, project_root=project_root)
    expected_keys = {
        "schema_version",
        "time_authority_schema_version",
        "time_contract_hash",
        "market_id",
        "market_timezone",
        "run_context_created_at_utc",
        "run_context_market_datetime",
        "market_run_date",
        "artifact_run_date",
    }
    reason_codes: list[str] = []
    if not isinstance(context, dict) or set(context) != expected_keys:
        return {"ok": False, "reason_codes": ["RUN_CONTEXT_SCHEMA_REJECT"]}
    try:
        computed = derive_market_run_date(context["run_context_created_at_utc"], policy)
        expected_market_datetime = format_market_datetime(
            context["run_context_created_at_utc"]
        )
        validate_date(context["market_run_date"], "market_run_date")
        validate_date(context["artifact_run_date"], "artifact_run_date")
    except (TimeAuthorityError, TypeError):
        return {"ok": False, "reason_codes": ["RUN_CONTEXT_SCHEMA_REJECT"]}
    expected_values = {
        "schema_version": "fog-runtime-run-context.v1",
        "time_authority_schema_version": policy["schema_version"],
        "time_contract_hash": canonical_json_hash(policy),
        "market_id": policy["market_id"],
        "market_timezone": policy["market_timezone"],
        "run_context_market_datetime": expected_market_datetime,
        "market_run_date": computed,
        "artifact_run_date": computed,
    }
    for key, expected in expected_values.items():
        if context.get(key) != expected:
            reason_codes.append("RUN_CONTEXT_AUTHORITY_MISMATCH")
            break
    return {
        "ok": not reason_codes,
        "reason_codes": reason_codes,
        "computed_market_run_date": computed,
    }


def verify_freshness(
    generated_at_utc: str | datetime,
    verification_time_utc: str | datetime,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_policy = EXPECTED_POLICY if policy is None else policy
    if effective_policy != EXPECTED_POLICY:
        return {"ok": False, "reason_codes": ["TIME_AUTHORITY_CONTRACT_DRIFT"]}
    generated = parse_utc_z(generated_at_utc)
    verification = parse_utc_z(verification_time_utc)
    age = (verification - generated).total_seconds()
    minimum = -float(effective_policy["freshness"]["future_tolerance_seconds"])
    maximum = float(effective_policy["freshness"]["max_age_seconds"])
    reason_codes: list[str] = []
    if age < minimum:
        reason_codes.append("FUTURE_RECEIPT")
    if age > maximum:
        reason_codes.append("STALE_RECEIPT")
    return {
        "ok": not reason_codes,
        "reason_codes": reason_codes,
        "receipt_age_seconds": age,
        "generated_at_utc": format_utc_z(generated),
        "verification_time_utc": format_utc_z(verification),
        "future_tolerance_seconds": -minimum,
        "max_age_seconds": maximum,
    }


def verify_date_lineage(
    *,
    market_run_date: str,
    artifact_run_date: str,
    daily_source_date: str,
    source_trade_date: str,
    canonical_artifact_run_date: str,
    canonical_daily_source_date: str,
    canonical_source_trade_date: str,
) -> dict[str, Any]:
    values = {
        "market_run_date": market_run_date,
        "artifact_run_date": artifact_run_date,
        "daily_source_date": daily_source_date,
        "source_trade_date": source_trade_date,
        "canonical_artifact_run_date": canonical_artifact_run_date,
        "canonical_daily_source_date": canonical_daily_source_date,
        "canonical_source_trade_date": canonical_source_trade_date,
    }
    try:
        for field, value in values.items():
            validate_date(value, field)
    except TimeAuthorityError:
        return {"ok": False, "reason_codes": ["INVALID_DATE_LINEAGE"]}
    reason_codes: list[str] = []
    if (
        artifact_run_date != market_run_date
        or canonical_artifact_run_date != market_run_date
        or artifact_run_date != canonical_artifact_run_date
    ):
        reason_codes.append("ARTIFACT_IDENTITY_DRIFT")
    if daily_source_date > market_run_date:
        reason_codes.append("FUTURE_DAILY_SOURCE_DATE")
    elif daily_source_date != canonical_daily_source_date:
        reason_codes.append("DAILY_SOURCE_DATE_MISMATCH")
    if source_trade_date > market_run_date:
        reason_codes.append("FUTURE_REGIME_SOURCE_DATE")
    elif source_trade_date != canonical_source_trade_date:
        reason_codes.append("REGIME_SOURCE_DATE_MISMATCH")
    return {"ok": not reason_codes, "reason_codes": reason_codes}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 immutable Fog runtime time context")
    parser.add_argument("--instant-utc")
    parser.add_argument("--output")
    parser.add_argument("--context", help="驗證既有 context，不重新 sample clock")
    parser.add_argument(
        "--field",
        choices=[
            "run_context_created_at_utc",
            "market_run_date",
            "artifact_run_date",
        ],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.context:
        context_path = Path(args.context)
        if not context_path.is_absolute():
            context_path = PROJECT_ROOT / context_path
        context = json.loads(context_path.read_text(encoding="utf-8"))
        result = validate_run_context(context)
        if not result["ok"]:
            print(
                json.dumps(
                    {"status": "FAILED", **result},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 1
        if args.field:
            print(context[args.field])
        else:
            print(
                json.dumps(
                    {"status": "OK", **result},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        return 0
    if args.field:
        raise SystemExit("--field 必須搭配 --context")
    instant = args.instant_utc or format_utc_z(datetime.now(UTC))
    context = build_run_context(instant)
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = PROJECT_ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
