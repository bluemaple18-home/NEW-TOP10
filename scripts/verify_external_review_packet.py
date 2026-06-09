#!/usr/bin/env python3
"""驗證 external-review-packet.v1 是否符合外送安全邊界。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "external-review-packet.v1"
ALLOWED_ROOT_KEYS = {
    "schema_version",
    "sendable",
    "packet_date",
    "generated_at",
    "market",
    "purpose",
    "safety_boundary",
    "market_overview",
    "outcome_status",
    "recommendations",
    "reviewer_instructions",
}
FORBIDDEN_KEYS = {
    "sources",
    "source",
    "lineage",
    "manifest",
    "features_ohlc",
    "features",
    "data_dir",
    "model",
    "model_path",
    "scores",
    "model_prob",
    "final_score",
    "risk_adjusted_score",
    "rule_score",
    "prediction_score",
    "setup_score",
    "quality_score",
    "risk_penalty",
    "feature_names",
    "feature_importance",
    "shap",
    "weights",
    "promotion_ready",
    "promotion_gate",
}
FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"\bAI\s*:", re.IGNORECASE),
    re.compile(r"\bSHAP\b", re.IGNORECASE),
    re.compile(r"\bmodel_prob\b", re.IGNORECASE),
    re.compile(r"\bfinal_score\b", re.IGNORECASE),
    re.compile(r"\brisk_adjusted_score\b", re.IGNORECASE),
    re.compile(r"\bprediction_score\b", re.IGNORECASE),
    re.compile(r"\bsetup_score\b", re.IGNORECASE),
    re.compile(r"\bquality_score\b", re.IGNORECASE),
    re.compile(r"\brisk_penalty\b", re.IGNORECASE),
    re.compile(r"\bfeatures_ohlc\b", re.IGNORECASE),
    re.compile(r"\bfeatures\.parquet\b", re.IGNORECASE),
    re.compile(r"\bdata/clean\b", re.IGNORECASE),
    re.compile(r"\bmodels?/[^ \t\n\"']*", re.IGNORECASE),
    re.compile(r"\blatest_lgbm\.pkl\b", re.IGNORECASE),
    re.compile(r"\bartifacts/ranking_\d{4}-\d{2}-\d{2}\.csv\b", re.IGNORECASE),
    re.compile(r"\b[\w./-]+\.parquet\b", re.IGNORECASE),
    re.compile(r"/Users/"),
    re.compile(r"/private/"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="verify external-review-packet.v1 JSON")
    parser.add_argument("--packet", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.packet.read_text(encoding="utf-8"))
    errors = validate_packet(payload)
    if errors:
        print("EXTERNAL_REVIEW_PACKET_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EXTERNAL_REVIEW_PACKET_OK")
    return 0


def validate_packet(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["root: must be object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: must be {SCHEMA_VERSION}")
    if payload.get("sendable") is not True:
        errors.append("sendable: must be true")
    if payload.get("market") != "TW":
        errors.append("market: must be TW")
    if payload.get("purpose") != "post_daily_external_review":
        errors.append("purpose: must be post_daily_external_review")
    extra_root_keys = sorted(set(payload) - ALLOWED_ROOT_KEYS)
    if extra_root_keys:
        errors.append(f"root: unexpected sendable keys {extra_root_keys}")

    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        errors.append("recommendations: must be non-empty list")
    else:
        for index, item in enumerate(recommendations):
            validate_recommendation(item, f"recommendations[{index}]", errors)

    for path, key in walk_keys(payload):
        if key.lower() in FORBIDDEN_KEYS:
            errors.append(f"{path}: forbidden key")

    for path, text in walk_text(payload):
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path}: forbidden text pattern {pattern.pattern}")

    return errors


def validate_recommendation(item: Any, path: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path}: must be object")
        return
    required = ["rank", "stock_id", "stock_name", "reference", "trade_plan", "public_reasons"]
    for key in required:
        if key not in item:
            errors.append(f"{path}.{key}: missing")
    if not re.fullmatch(r"\d{4,6}", str(item.get("stock_id", ""))):
        errors.append(f"{path}.stock_id: invalid stock id")
    if not isinstance(item.get("public_reasons"), list):
        errors.append(f"{path}.public_reasons: must be list")
    for reason_index, reason in enumerate(item.get("public_reasons") or []):
        if not isinstance(reason, str):
            errors.append(f"{path}.public_reasons[{reason_index}]: must be string")
        elif looks_like_internal_feature(reason):
            errors.append(f"{path}.public_reasons[{reason_index}]: looks like internal feature")


def looks_like_internal_feature(text: str) -> bool:
    if "AI:" in text or "SHAP" in text.upper():
        return True
    if re.search(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", text) and not re.search(r"[\u4e00-\u9fff]", text):
        return True
    return False


def walk_keys(value: Any, path: str = "root"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key)
            yield from walk_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_keys(child, f"{path}[{index}]")


def walk_text(value: Any, path: str = "root"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_text(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_text(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


if __name__ == "__main__":
    raise SystemExit(main())
