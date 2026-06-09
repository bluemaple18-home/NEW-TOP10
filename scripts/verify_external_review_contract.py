#!/usr/bin/env python3
"""驗證外部 reviewer 回覆是否符合 external-review.v1 contract。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "external-review.v1"

ALLOWED_PROVIDERS = {"chatgpt", "gemini"}
ALLOWED_VERDICTS = {"excellent", "good", "mixed", "poor"}
ALLOWED_OBSERVATION_TYPES = {"strength", "weakness", "risk", "missed_opportunity"}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
ALLOWED_CAUSES = {
    "market_drag",
    "theme_rotation",
    "overextended",
    "liquidity_weakness",
    "news_risk",
    "unknown",
}
ALLOWED_SIGNAL_FAMILIES = {
    "theme_momentum",
    "relative_strength",
    "risk_control",
    "liquidity",
    "timing",
    "other",
}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify external-review.v1 JSON")
    parser.add_argument("path", type=Path)
    return parser.parse_args()


def add_error(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def require_object(payload: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        add_error(errors, key, "must be object")
        return {}
    return value


def require_list(payload: dict[str, Any], key: str, errors: list[str]) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        add_error(errors, key, "must be list")
        return []
    return value


def check_string(value: Any, path: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        add_error(errors, path, "must be string")
    elif not allow_empty and not value.strip():
        add_error(errors, path, "must not be empty")


def check_bool(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        add_error(errors, path, "must be boolean")


def check_int_range(value: Any, path: str, errors: list[str], minimum: int, maximum: int) -> None:
    if not isinstance(value, int):
        add_error(errors, path, "must be integer")
    elif value < minimum or value > maximum:
        add_error(errors, path, f"must be between {minimum} and {maximum}")


def check_number_range(value: Any, path: str, errors: list[str], minimum: float, maximum: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        add_error(errors, path, "must be number")
    elif value < minimum or value > maximum:
        add_error(errors, path, f"must be between {minimum} and {maximum}")


def check_string_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        add_error(errors, path, "must be list")
        return
    for index, item in enumerate(value):
        check_string(item, f"{path}[{index}]", errors)


def check_choice(value: Any, path: str, errors: list[str], allowed: set[str]) -> None:
    if value not in allowed:
        add_error(errors, path, f"must be one of {sorted(allowed)}")


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        add_error(errors, "schema_version", f"must be {SCHEMA_VERSION}")
    check_choice(payload.get("provider"), "provider", errors, ALLOWED_PROVIDERS)
    check_string(payload.get("review_date"), "review_date", errors)
    if payload.get("market") != "TW":
        add_error(errors, "market", "must be TW")

    overall = require_object(payload, "overall", errors)
    check_int_range(overall.get("score"), "overall.score", errors, 0, 100)
    check_choice(overall.get("verdict"), "overall.verdict", errors, ALLOWED_VERDICTS)
    check_number_range(overall.get("confidence"), "overall.confidence", errors, 0, 1)
    check_string(overall.get("summary"), "overall.summary", errors)

    quality = require_object(payload, "quality", errors)
    for key in ["mainstream_alignment", "relative_strength", "risk_control", "timing_quality", "theme_fit"]:
        check_int_range(quality.get(key), f"quality.{key}", errors, 0, 5)

    for index, item in enumerate(require_list(payload, "observations", errors)):
        if not isinstance(item, dict):
            add_error(errors, f"observations[{index}]", "must be object")
            continue
        check_choice(item.get("type"), f"observations[{index}].type", errors, ALLOWED_OBSERVATION_TYPES)
        check_string(item.get("title"), f"observations[{index}].title", errors)
        check_string(item.get("evidence"), f"observations[{index}].evidence", errors)
        check_string_list(item.get("affected_symbols"), f"observations[{index}].affected_symbols", errors)
        check_choice(item.get("severity"), f"observations[{index}].severity", errors, ALLOWED_SEVERITIES)

    for index, item in enumerate(require_list(payload, "misses", errors)):
        if not isinstance(item, dict):
            add_error(errors, f"misses[{index}]", "must be object")
            continue
        check_string(item.get("symbol"), f"misses[{index}].symbol", errors, allow_empty=True)
        check_string(item.get("name"), f"misses[{index}].name", errors, allow_empty=True)
        check_string(item.get("issue"), f"misses[{index}].issue", errors)
        check_choice(item.get("likely_cause"), f"misses[{index}].likely_cause", errors, ALLOWED_CAUSES)
        check_string(item.get("evidence"), f"misses[{index}].evidence", errors)

    themes = require_object(payload, "themes", errors)
    for key in ["strong", "weak", "watch"]:
        check_string_list(themes.get(key), f"themes.{key}", errors)

    tomorrow = require_object(payload, "tomorrow_watch", errors)
    for key in ["continue", "avoid_chasing", "watch_for_reversal", "theme_candidates"]:
        check_string_list(tomorrow.get(key), f"tomorrow_watch.{key}", errors)

    for index, item in enumerate(require_list(payload, "research_hypotheses", errors)):
        if not isinstance(item, dict):
            add_error(errors, f"research_hypotheses[{index}]", "must be object")
            continue
        check_string(item.get("hypothesis"), f"research_hypotheses[{index}].hypothesis", errors)
        check_string(item.get("why_it_matters"), f"research_hypotheses[{index}].why_it_matters", errors)
        check_choice(
            item.get("candidate_signal_family"),
            f"research_hypotheses[{index}].candidate_signal_family",
            errors,
            ALLOWED_SIGNAL_FAMILIES,
        )
        check_string(item.get("validation_hint"), f"research_hypotheses[{index}].validation_hint", errors)
        check_choice(item.get("priority"), f"research_hypotheses[{index}].priority", errors, ALLOWED_PRIORITIES)

    safety = require_object(payload, "safety", errors)
    for key in ["algorithm_requested", "contains_algorithm_claim", "needs_human_review"]:
        check_bool(safety.get(key), f"safety.{key}", errors)

    if safety.get("algorithm_requested") is True or safety.get("contains_algorithm_claim") is True:
        add_error(errors, "safety", "algorithm boundary violation")

    return errors


def main() -> int:
    args = parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("root: must be object")
        return 1
    errors = validate(payload)
    if errors:
        print("EXTERNAL_REVIEW_CONTRACT_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EXTERNAL_REVIEW_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
