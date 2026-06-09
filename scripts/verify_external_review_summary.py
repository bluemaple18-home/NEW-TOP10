#!/usr/bin/env python3
"""驗證 external-review-summary.v1。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "external-review-summary.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify external-review-summary.v1 JSON")
    parser.add_argument("--summary", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        print("EXTERNAL_REVIEW_SUMMARY_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EXTERNAL_REVIEW_SUMMARY_OK")
    return 0


def validate(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["root: must be object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: must be {SCHEMA_VERSION}")
    check_string(payload.get("review_date"), "review_date", errors)
    providers = check_list(payload.get("providers"), "providers", errors)
    valid_count = payload.get("valid_provider_count")
    if not isinstance(valid_count, int) or valid_count < 0:
        errors.append("valid_provider_count: must be non-negative integer")
    elif providers and valid_count != sum(1 for provider in providers if isinstance(provider, dict) and provider.get("valid") is True):
        errors.append("valid_provider_count: mismatch with providers[].valid")
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            errors.append(f"providers[{index}]: must be object")
            continue
        check_string(provider.get("provider"), f"providers[{index}].provider", errors)
        check_bool(provider.get("valid"), f"providers[{index}].valid", errors)
        check_string(provider.get("reason"), f"providers[{index}].reason", errors, allow_empty=True)

    for key in ["consensus", "disagreements", "today_misses", "research_hypotheses"]:
        check_list(payload.get(key), key, errors)
    tomorrow = check_object(payload.get("tomorrow_watch"), "tomorrow_watch", errors)
    for key in ["continue", "avoid_chasing", "watch_for_reversal", "theme_candidates"]:
        check_string_list(tomorrow.get(key), f"tomorrow_watch.{key}", errors)

    safety = check_object(payload.get("safety"), "safety", errors)
    check_bool(safety.get("needs_human_review"), "safety.needs_human_review", errors)
    check_bool(safety.get("algorithm_requested"), "safety.algorithm_requested", errors)
    check_bool(safety.get("contains_algorithm_claim"), "safety.contains_algorithm_claim", errors)
    check_list(safety.get("invalid_providers"), "safety.invalid_providers", errors)
    if safety.get("algorithm_requested") is True or safety.get("contains_algorithm_claim") is True:
        errors.append("safety: algorithm boundary violation requires manual remediation")

    boundary = check_object(payload.get("promotion_boundary"), "promotion_boundary", errors)
    if boundary.get("promotion_ready") is not False:
        errors.append("promotion_boundary.promotion_ready: must be false")
    if boundary.get("may_change_ranking_or_model") is not False:
        errors.append("promotion_boundary.may_change_ranking_or_model: must be false")
    if boundary.get("external_review_is_research_only") is not True:
        errors.append("promotion_boundary.external_review_is_research_only: must be true")
    return errors


def check_object(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be object")
        return {}
    return value


def check_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path}: must be list")
        return []
    return value


def check_string_list(value: Any, path: str, errors: list[str]) -> None:
    items = check_list(value, path, errors)
    for index, item in enumerate(items):
        check_string(item, f"{path}[{index}]", errors)


def check_string(value: Any, path: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: must be string")
    elif not allow_empty and not value.strip():
        errors.append(f"{path}: must not be empty")


def check_bool(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: must be boolean")


if __name__ == "__main__":
    raise SystemExit(main())
