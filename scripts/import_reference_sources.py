#!/usr/bin/env python3
"""Import external concept/industry reference sources into local CSV contracts."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import csv
import json
from pathlib import Path
import sys

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.reference_sources import ConceptMembership, build_collectors
from app.reference_sources.normalization import PARENT_CONCEPTS


CONCEPT_MEMBERSHIP_FIELDS = [
    "stock_id",
    "canonical_concept_id",
    "canonical_name",
    "parent_concept_id",
    "raw_concept_name",
    "concept_type",
    "source",
    "source_url",
    "observed_at",
    "confidence",
    "match_method",
]

TAXONOMY_FIELDS = [
    "canonical_concept_id",
    "canonical_name",
    "parent_concept_id",
    "concept_type",
    "confidence",
    "status",
]

ALIAS_FIELDS = [
    "source",
    "raw_concept_name",
    "normalized_name",
    "canonical_concept_id",
    "match_method",
    "confidence",
    "reviewed",
]

AUDIT_FIELDS = [
    "source",
    "fetched_at",
    "status",
    "fetched_pages",
    "row_count",
    "error",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import concept/industry reference sources")
    parser.add_argument("--config", default="config/reference_sources.yaml")
    parser.add_argument("--sources", help="Comma-separated source names to import, e.g. yahoo,moneydj")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse, but do not update data/reference CSV")
    parser.add_argument("--allow-partial", action="store_true", help="Return 0 if at least one source succeeds")
    args = parser.parse_args()

    config = yaml.safe_load((PROJECT_ROOT / args.config).read_text(encoding="utf-8")) or {}
    selected_sources = parse_sources(args.sources)
    if selected_sources:
        config["enabled_sources"] = selected_sources
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw_dir = PROJECT_ROOT / "data" / "raw" / "reference" / today
    collectors = build_collectors(project_root=PROJECT_ROOT, config=config, raw_dir=raw_dir)

    all_memberships: list[ConceptMembership] = []
    audit_rows = []
    failed_sources = []
    blocked_sources = []
    for collector in collectors:
        result = collector.collect(probe_only=False)
        all_memberships.extend(result.memberships)
        if result.status == "FAILED":
            failed_sources.append(result.source)
        if result.metadata.get("stopped_on_blocked"):
            blocked_sources.append(result.source)
        audit_rows.append(
            {
                "source": result.source,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "status": result.status,
                "fetched_pages": result.fetched_pages,
                "row_count": result.row_count,
                "error": " | ".join(result.errors),
            }
        )
        print(
            f"{result.source}: status={result.status} pages={result.fetched_pages} "
            f"rows={result.row_count} errors={len(result.errors)}"
        )

    deduped = dedupe_memberships(all_memberships)
    reference_dir = PROJECT_ROOT / "data" / "reference"
    if selected_sources and not args.dry_run:
        preserved = load_existing_memberships(
            reference_dir / "stock_concept_membership.csv",
            excluded_sources=set(selected_sources),
        )
        deduped = dedupe_memberships([*preserved, *deduped])
        audit_rows = [
            *load_existing_audit_rows(reference_dir / "reference_source_audit.csv", excluded_sources=set(selected_sources)),
            *audit_rows,
        ]
    can_write = not args.dry_run and not blocked_sources
    if can_write:
        reference_dir.mkdir(parents=True, exist_ok=True)
        write_csv(reference_dir / "stock_concept_membership.csv", CONCEPT_MEMBERSHIP_FIELDS, [membership_row(m) for m in deduped])
        write_csv(reference_dir / "concept_taxonomy.csv", TAXONOMY_FIELDS, taxonomy_rows(deduped))
        write_csv(reference_dir / "concept_alias_map.csv", ALIAS_FIELDS, alias_rows(deduped))
        write_csv(reference_dir / "reference_source_audit.csv", AUDIT_FIELDS, audit_rows)
    elif blocked_sources:
        print(f"skipped_write_blocked_sources={','.join(blocked_sources)}")

    artifact_path = PROJECT_ROOT / "artifacts" / "reference_import_summary.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": args.dry_run,
                "sources": audit_rows,
                "raw_rows": len(all_memberships),
                "deduped_rows": len(deduped),
                "failed_sources": failed_sources,
                "blocked_sources": blocked_sources,
                "selected_sources": selected_sources,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"reference_import_summary={artifact_path}")

    if failed_sources and not args.allow_partial:
        return 1
    if blocked_sources:
        return 1
    if not deduped:
        return 1
    return 0


def parse_sources(value: str | None) -> list[str]:
    if not value:
        return []
    return [source.strip() for source in value.split(",") if source.strip()]


def load_existing_memberships(path: Path, excluded_sources: set[str]) -> list[ConceptMembership]:
    if not path.exists():
        return []
    preserved: list[ConceptMembership] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("source", "")).strip() in excluded_sources:
                continue
            preserved.append(
                ConceptMembership(
                    stock_id=str(row.get("stock_id", "")).strip(),
                    canonical_concept_id=str(row.get("canonical_concept_id", "")).strip(),
                    canonical_name=str(row.get("canonical_name", "")).strip(),
                    parent_concept_id=blank_to_none(row.get("parent_concept_id")),
                    raw_concept_name=str(row.get("raw_concept_name", "")).strip(),
                    concept_type=str(row.get("concept_type", "")).strip() or "theme",
                    source=str(row.get("source", "")).strip(),
                    source_url=str(row.get("source_url", "")).strip(),
                    observed_at=str(row.get("observed_at", "")).strip(),
                    confidence=float(row.get("confidence") or 0),
                    match_method=str(row.get("match_method", "")).strip(),
                )
            )
    return preserved


def load_existing_audit_rows(path: Path, excluded_sources: set[str]) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("source", "")).strip() not in excluded_sources:
                rows.append({field: row.get(field, "") for field in AUDIT_FIELDS})
    return rows


def blank_to_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def dedupe_memberships(memberships: list[ConceptMembership]) -> list[ConceptMembership]:
    by_key: dict[tuple[str, str, str, str], ConceptMembership] = {}
    for membership in memberships:
        key = (
            membership.stock_id,
            membership.canonical_concept_id,
            membership.source,
            membership.raw_concept_name,
        )
        existing = by_key.get(key)
        if existing is None or membership.confidence > existing.confidence:
            by_key[key] = membership
    return sorted(
        by_key.values(),
        key=lambda item: (item.canonical_concept_id, item.stock_id, item.source, item.raw_concept_name),
    )


def membership_row(membership: ConceptMembership) -> dict[str, object]:
    row = asdict(membership)
    return {field: row.get(field) for field in CONCEPT_MEMBERSHIP_FIELDS}


def taxonomy_rows(memberships: list[ConceptMembership]) -> list[dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for parent_id, (parent_name, grand_parent_id) in PARENT_CONCEPTS.items():
        rows[parent_id] = {
            "canonical_concept_id": parent_id,
            "canonical_name": parent_name,
            "parent_concept_id": grand_parent_id,
            "concept_type": "group",
            "confidence": 1.0,
            "status": "active",
        }
    for membership in memberships:
        existing = rows.get(membership.canonical_concept_id)
        confidence = round(float(membership.confidence), 4)
        if existing is None or confidence > float(existing["confidence"]):
            rows[membership.canonical_concept_id] = {
                "canonical_concept_id": membership.canonical_concept_id,
                "canonical_name": membership.canonical_name,
                "parent_concept_id": membership.parent_concept_id,
                "concept_type": membership.concept_type,
                "confidence": confidence,
                "status": "active" if confidence >= 0.9 else "thin",
            }
    return sorted(rows.values(), key=lambda row: str(row["canonical_concept_id"]))


def alias_rows(memberships: list[ConceptMembership]) -> list[dict[str, object]]:
    rows: dict[tuple[str, str, str], dict[str, object]] = {}
    for membership in memberships:
        key = (membership.source, membership.raw_concept_name, membership.canonical_concept_id)
        rows[key] = {
            "source": membership.source,
            "raw_concept_name": membership.raw_concept_name,
            "normalized_name": membership.canonical_name,
            "canonical_concept_id": membership.canonical_concept_id,
            "match_method": membership.match_method,
            "confidence": round(float(membership.confidence), 4),
            "reviewed": False,
        }
    return sorted(rows.values(), key=lambda row: (str(row["canonical_concept_id"]), str(row["source"])))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"wrote {path} rows={len(rows)}")


if __name__ == "__main__":
    raise SystemExit(main())
