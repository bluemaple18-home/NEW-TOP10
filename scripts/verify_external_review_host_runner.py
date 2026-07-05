#!/usr/bin/env python3
"""驗證 external review host runner 證據。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from external_review_provider_contract import provider_artifact_errors


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCHEMA_VERSION = "external-review-host-runner-status.v1"
SUMMARY_SCHEMA_VERSION = "external-review-host-runner-summary.v1"
STATUS_VALUES = {"OK", "PARTIAL", "FAILED", "SKIPPED", "RUNNING"}
PROVIDER_VALUES = {"OK", "FAILED", "SKIPPED", "PENDING"}
PROVIDERS = ("chatgpt", "gemini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify external review host runner artifacts")
    parser.add_argument("--status", required=True, type=Path, help="host_runner_status_YYYY-MM-DD.json")
    parser.add_argument("--summary", default=None, type=Path, help="host_runner_summary_YYYY-MM-DD.json")
    parser.add_argument("--require-success", action="store_true", help="要求 status 為 OK 或 PARTIAL")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status_path = resolve_path(args.status)
    payload = read_json(status_path)
    errors = validate_status(payload, status_path, require_success=args.require_success)

    summary_path = resolve_path(args.summary) if args.summary else resolve_optional_path(payload.get("host_runner_summary_path"))
    if summary_path:
        if not summary_path.exists():
            errors.append(f"host runner summary missing: {repo_relative(summary_path)}")
        else:
            errors.extend(validate_summary(read_json(summary_path), payload))

    if errors:
        print("EXTERNAL_REVIEW_HOST_RUNNER_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EXTERNAL_REVIEW_HOST_RUNNER_OK")
    return 0


def validate_status(payload: Any, status_path: Path, *, require_success: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["root: must be object"]
    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append(f"schema_version: must be {STATUS_SCHEMA_VERSION}")
    check_string(payload.get("run_date"), "run_date", errors)
    check_enum(payload.get("status"), "status", STATUS_VALUES, errors)
    if require_success and payload.get("status") not in {"OK", "PARTIAL"}:
        errors.append(f"status: must be OK or PARTIAL when --require-success is used, got {payload.get('status')}")
    check_bool(payload.get("daily_status_ok"), "daily_status_ok", errors)
    check_bool(payload.get("packet_verified"), "packet_verified", errors)
    check_bool(payload.get("manifest_refused"), "manifest_refused", errors)
    check_bool(payload.get("summary_verified"), "summary_verified", errors)
    check_list(payload.get("notes"), "notes", errors)

    expected_status = repo_relative(status_path)
    if payload.get("host_runner_status_path") != expected_status:
        errors.append(f"host_runner_status_path: expected {expected_status}, got {payload.get('host_runner_status_path')}")

    if payload.get("status") in {"OK", "PARTIAL"}:
        if payload.get("daily_status_ok") is not True:
            errors.append("daily_status_ok: must be true for OK/PARTIAL")
        if payload.get("packet_verified") is not True:
            errors.append("packet_verified: must be true for OK/PARTIAL")
        if payload.get("manifest_refused") is not True:
            errors.append("manifest_refused: must be true for OK/PARTIAL")
        if payload.get("summary_verified") is not True:
            errors.append("summary_verified: must be true for OK/PARTIAL")
        check_existing_path(payload.get("summary_path"), "summary_path", errors)

    manifest_path = str(payload.get("manifest_path") or "")
    packet_path = str(payload.get("packet_path") or "")
    if packet_path and "manifest" in Path(packet_path).name:
        errors.append("packet_path: must not point to manifest")
    if manifest_path and payload.get("manifest_refused") is not True:
        errors.append("manifest_path exists but manifest_refused is not true")

    for provider in PROVIDERS:
        provider_payload = payload.get(provider)
        if not isinstance(provider_payload, dict):
            errors.append(f"{provider}: must be object")
            continue
        validate_provider(provider, provider_payload, errors)
    return errors


def validate_provider(provider: str, payload: dict[str, Any], errors: list[str]) -> None:
    check_enum(payload.get("status"), f"{provider}.status", PROVIDER_VALUES, errors)
    check_string(payload.get("target"), f"{provider}.target", errors)
    check_string(payload.get("raw_path"), f"{provider}.raw_path", errors)
    check_string(payload.get("response_path"), f"{provider}.response_path", errors)
    check_list(payload.get("notes"), f"{provider}.notes", errors)
    if payload.get("status") == "OK":
        check_existing_path(payload.get("raw_path"), f"{provider}.raw_path", errors)
        check_existing_path(payload.get("response_path"), f"{provider}.response_path", errors)
        artifact_errors = provider_status_artifact_errors(provider, payload)
        if artifact_errors:
            errors.append(f"{provider}.status: OK but artifacts invalid: {'; '.join(artifact_errors)}")


def provider_status_artifact_errors(provider: str, payload: dict[str, Any]) -> list[str]:
    raw_path = resolve_optional_path(payload.get("raw_path"))
    status_path = resolve_optional_path(payload.get("collect_status_path"))
    response_path = resolve_optional_path(payload.get("response_path"))
    if raw_path is None or status_path is None:
        return ["raw_or_collect_status_path_missing"]
    response_payload = read_json(response_path) if response_path and response_path.exists() else None
    review_date = response_payload.get("review_date") if isinstance(response_payload, dict) else None
    if not isinstance(review_date, str) or not review_date:
        review_date = infer_review_date(raw_path)
    if not review_date:
        return ["review_date_missing"]
    return provider_artifact_errors(
        provider=provider,
        review_date=review_date,
        raw_path=raw_path,
        collect_status_path=status_path,
        response_payload=response_payload,
    )


def infer_review_date(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.count("-") == 2 else ""


def validate_summary(payload: Any, status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["summary root: must be object"]
    if payload.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append(f"summary.schema_version: must be {SUMMARY_SCHEMA_VERSION}")
    if payload.get("run_date") != status.get("run_date"):
        errors.append(f"summary.run_date: mismatch {payload.get('run_date')} != {status.get('run_date')}")
    if payload.get("status") != status.get("status"):
        errors.append(f"summary.status: mismatch {payload.get('status')} != {status.get('status')}")
    check_list(payload.get("providers"), "summary.providers", errors)
    check_list(payload.get("notes"), "summary.notes", errors)
    validate_external_summary_alignment(payload, errors)
    return errors


def validate_external_summary_alignment(payload: dict[str, Any], errors: list[str]) -> None:
    external_path = resolve_optional_path(payload.get("external_review_summary_path"))
    if not external_path:
        return
    if not external_path.exists():
        errors.append(f"summary.external_review_summary_path: missing on disk: {payload.get('external_review_summary_path')}")
        return
    external = read_json(external_path)
    if payload.get("valid_provider_count") != external.get("valid_provider_count"):
        errors.append(
            "summary.valid_provider_count: mismatch with external review summary "
            f"{payload.get('valid_provider_count')} != {external.get('valid_provider_count')}"
        )

    summary_safety = object_value(payload.get("safety"))
    external_safety = object_value(external.get("safety"))
    if summary_safety.get("invalid_providers") != external_safety.get("invalid_providers"):
        errors.append(
            "summary.safety.invalid_providers: mismatch with external review summary "
            f"{summary_safety.get('invalid_providers')} != {external_safety.get('invalid_providers')}"
        )
    if payload.get("promotion_boundary") != external.get("promotion_boundary"):
        errors.append("summary.promotion_boundary: mismatch with external review summary")

    summary_validity = provider_validity(payload.get("providers"))
    external_validity = provider_validity(external.get("providers"))
    for provider, valid in external_validity.items():
        if summary_validity.get(provider) != valid:
            errors.append(
                f"summary.providers[{provider}].valid: mismatch with external review summary "
                f"{summary_validity.get(provider)} != {valid}"
            )


def provider_validity(value: Any) -> dict[str, bool]:
    if not isinstance(value, list):
        return {}
    result: dict[str, bool] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        if isinstance(provider, str) and provider:
            result[provider] = item.get("valid") is True
    return result


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def check_string(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: must be non-empty string")


def check_bool(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: must be boolean")


def check_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: must be list")


def check_enum(value: Any, path: str, allowed: set[str], errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{path}: must be one of {sorted(allowed)}, got {value}")


def check_existing_path(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: must be non-empty path")
        return
    target = resolve_path(Path(value))
    if not target.exists():
        errors.append(f"{path}: missing on disk: {value}")


def resolve_optional_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return resolve_path(Path(value))


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
