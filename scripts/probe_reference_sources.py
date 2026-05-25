#!/usr/bin/env python3
"""Probe external reference sources without updating normalized data."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.reference_sources import build_collectors


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe concept/industry reference sources")
    parser.add_argument("--config", default="config/reference_sources.yaml")
    parser.add_argument("--sources", help="Comma-separated source names to probe, e.g. yahoo,moneydj")
    parser.add_argument("--output", default="artifacts/reference_source_probe.json")
    args = parser.parse_args()

    config = yaml.safe_load((PROJECT_ROOT / args.config).read_text(encoding="utf-8")) or {}
    selected_sources = parse_sources(args.sources)
    if selected_sources:
        config["enabled_sources"] = selected_sources
    collectors = build_collectors(project_root=PROJECT_ROOT, config=config, raw_dir=None)

    results = []
    failed = False
    for collector in collectors:
        result = collector.collect(probe_only=True)
        results.append(asdict(result))
        failed = failed or result.status == "FAILED"
        print(
            f"{result.source}: status={result.status} pages={result.fetched_pages} "
            f"rows={result.row_count} errors={len(result.errors)}"
        )
        for error in result.errors:
            print(f"  {error}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": not failed,
        "selected_sources": selected_sources,
        "results": results,
    }
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"probe_output={output_path}")
    return 1 if failed else 0


def parse_sources(value: str | None) -> list[str]:
    if not value:
        return []
    return [source.strip() for source in value.split(",") if source.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
