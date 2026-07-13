"""Clawd payload 所需 reference/config 的唯讀 loader boundary。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.publishing.clawd_payload import clean_concept_name, is_noisy_concept, number_value, unique_preserve_order


def load_payload_reference_data(project_root: Path) -> dict[str, Any]:
    """一次載入 domain transform 所需的四組外部 lookup。"""
    return {
        "industry_map": load_industry_map(project_root),
        "concept_map": load_concept_map(project_root),
        "industry_bucket_map": load_notification_industry_buckets(project_root),
        "bucket_rules": load_notification_theme_buckets(project_root),
    }


def load_industry_map(project_root: Path) -> dict[str, dict[str, str]]:
    path = project_root / "data" / "reference" / "stock_industry_map.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {
            str(row.get("stock_id", "")).zfill(4): row
            for row in csv.DictReader(file)
            if row.get("stock_id")
        }


def load_concept_map(project_root: Path) -> dict[str, list[str]]:
    path = project_root / "data" / "reference" / "stock_concept_membership.csv"
    if not path.exists():
        return {}
    concepts: dict[str, list[tuple[float, str]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("concept_type") != "theme":
                continue
            stock_id = str(row.get("stock_id", "")).zfill(4)
            concept = clean_concept_name(str(row.get("canonical_name") or row.get("raw_concept_name") or ""))
            if not stock_id or not concept or is_noisy_concept(concept):
                continue
            confidence = number_value(row.get("confidence")) or 0.0
            concepts.setdefault(stock_id, []).append((confidence, concept))
    return {
        stock_id: unique_preserve_order(
            concept for _, concept in sorted(rows, key=lambda item: (-item[0], item[1]))
        )[:6]
        for stock_id, rows in concepts.items()
    }


def load_notification_theme_buckets(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / "config" / "notification_theme_buckets.csv"
    if not path.exists():
        return []
    rules = []
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            bucket = str(row.get("bucket") or "").strip()
            if not bucket:
                continue
            rules.append(
                {
                    "priority": int(number_value(row.get("priority")) or 999),
                    "bucket": bucket,
                    "industry_keywords": split_keywords(row.get("industry_keywords")),
                    "concept_keywords": split_keywords(row.get("concept_keywords")),
                    "notes": str(row.get("notes") or "").strip(),
                }
            )
    return sorted(rules, key=lambda row: (row["priority"], row["bucket"]))


def load_notification_industry_buckets(project_root: Path) -> dict[str, str]:
    path = project_root / "config" / "notification_industry_buckets.csv"
    if not path.exists():
        return {}
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            industry = str(row.get("industry_name") or "").strip()
            bucket = str(row.get("notification_bucket") or "").strip()
            if industry and bucket:
                result[industry] = bucket
    return result


def split_keywords(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]
