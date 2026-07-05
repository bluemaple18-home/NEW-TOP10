#!/usr/bin/env python3
"""外部 reviewer provider artifact 的最小驗證規則。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MIN_RAW_CHARS = 500
SMOKE_MARKERS = (
    "top10-browser",
    "top10-chatgpt-script-click",
    "top10-browser-smoke",
    '"marker"',
)


def has_smoke_marker(text: str) -> bool:
    return any(marker in text for marker in SMOKE_MARKERS)


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def provider_artifact_errors(
    *,
    provider: str,
    review_date: str,
    raw_path: Path,
    collect_status_path: Path,
    response_payload: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    raw_text = ""
    if not raw_path.exists():
        errors.append("raw_missing")
    else:
        raw_text = raw_path.read_text(encoding="utf-8").strip()
        if len(raw_text) < MIN_RAW_CHARS:
            errors.append(f"raw_too_short:{len(raw_text)}<{MIN_RAW_CHARS}")
        if has_smoke_marker(raw_text):
            errors.append("raw_smoke_marker_detected")
        expected_raw_name = f"{provider}_raw_{review_date}.txt"
        if raw_path.name != expected_raw_name:
            errors.append(f"raw_path_mismatch:{raw_path.name}!={expected_raw_name}")

    status = read_json_if_exists(collect_status_path)
    if not status:
        errors.append("collect_status_missing_or_invalid")
    else:
        if status.get("provider") not in {None, provider}:
            errors.append(f"collect_status_provider_mismatch:{status.get('provider')}!={provider}")
        if status.get("review_date") not in {None, review_date}:
            errors.append(f"collect_status_review_date_mismatch:{status.get('review_date')}!={review_date}")
        if status.get("ok") is not True:
            errors.append(f"collect_status_not_ok:{status.get('reason') or status.get('status')}")
        if isinstance(status.get("raw_chars"), int) and status["raw_chars"] < MIN_RAW_CHARS:
            errors.append(f"collect_status_raw_too_short:{status['raw_chars']}<{MIN_RAW_CHARS}")
        if status.get("smoke_marker_detected") is True:
            errors.append("collect_status_smoke_marker_detected")
        expected_status_name = f"{provider}_collect_status_{review_date}.json"
        if collect_status_path.name != expected_status_name:
            errors.append(f"collect_status_path_mismatch:{collect_status_path.name}!={expected_status_name}")

    if response_payload is not None:
        if response_payload.get("provider") != provider:
            errors.append(f"response_provider_mismatch:{response_payload.get('provider')}!={provider}")
        if response_payload.get("review_date") != review_date:
            errors.append(f"response_review_date_mismatch:{response_payload.get('review_date')}!={review_date}")

    return errors
