#!/usr/bin/env python3
"""串流追溯 weekend training full artifact 明細。

主線 artifacts 預設只保留 summary-only；這支工具只在人工排查歷史日期時，
從封存的 `.json.gz` / `.json.zst` / `.json` records 裡找指定 combo/topic。
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
FAMILIES = {
    "inventory": "weekend_universe_inventory",
    "queue": "weekend_frontier_queue",
}
ARRAY_KEYS = {
    "inventory": "records",
    "queue": "items",
}


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="trace archived weekend training artifact records")
    parser.add_argument("--date", required=True)
    parser.add_argument("--family", choices=["inventory", "queue", "all"], default="all")
    parser.add_argument("--combo-id", default=None)
    parser.add_argument("--topic-id", default=None)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def candidate_paths(date: str, family: str) -> list[Path]:
    stem = FAMILIES[family]
    return [
        WEEKEND_DIR / f"{stem}_{date}.json",
        WEEKEND_DIR / f"{stem}_{date}.json.gz",
        WEEKEND_DIR / f"{stem}_{date}.json.zst",
    ]


def resolve_artifact(date: str, family: str) -> Path | None:
    for path in candidate_paths(date, family):
        if path.exists():
            return path
    return None


@contextmanager
def open_text(path: Path) -> Iterator[TextIO]:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            yield handle
        return
    if path.name.endswith(".zst"):
        proc = subprocess.Popen(
            ["zstd", "-dc", str(path)],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.stdout is None:
            raise RuntimeError("zstd stdout unavailable")
        try:
            yield proc.stdout
        finally:
            _, stderr = proc.communicate()
            if proc.returncode not in {0, None}:
                raise RuntimeError(f"zstd failed: {stderr.strip()}")
        return
    with path.open("rt", encoding="utf-8") as handle:
        yield handle


def iter_array_objects(path: Path, array_key: str) -> Iterator[dict[str, Any]]:
    """從大型 JSON payload 的指定 array 串流取出單筆 object。"""

    marker = f'"{array_key}":['
    search_buffer = ""
    in_records = False
    in_object = False
    in_string = False
    escaped = False
    depth = 0
    record_chars: list[str] = []
    with open_text(path) as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            if not in_records:
                search_buffer += chunk
                found = search_buffer.find(marker)
                if found < 0:
                    search_buffer = search_buffer[-len(marker) :]
                    continue
                chunk = search_buffer[found + len(marker) :]
                search_buffer = ""
                in_records = True
            index = 0
            while index < len(chunk):
                char = chunk[index]
                index += 1
                if not in_object:
                    if char == "{":
                        in_object = True
                        in_string = False
                        escaped = False
                        depth = 1
                        record_chars = [char]
                    elif char == "]":
                        return
                    continue
                record_chars.append(char)
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        in_object = False
                        yield json.loads("".join(record_chars))


def record_matches(record: dict[str, Any], combo_id: str | None, topic_id: str | None) -> bool:
    if not combo_id and not topic_id:
        return True
    if combo_id and str(record.get("combo_id") or "") != combo_id:
        return False
    if topic_id and str(record.get("topic_id") or "") != topic_id:
        return False
    return True


def trace_family(date: str, family: str, combo_id: str | None, topic_id: str | None, limit: int) -> dict[str, Any]:
    artifact = resolve_artifact(date, family)
    if artifact is None:
        return {
            "family": family,
            "status": "MISSING_ARTIFACT",
            "artifact": None,
            "matches": [],
            "scanned_records": 0,
        }
    matches: list[dict[str, Any]] = []
    scanned = 0
    array_key = ARRAY_KEYS[family]
    for record in iter_array_objects(artifact, array_key):
        scanned += 1
        if record_matches(record, combo_id, topic_id):
            matches.append(record)
            if len(matches) >= limit:
                break
    return {
        "family": family,
        "status": "OK",
        "artifact": repo_path(artifact),
        "array_key": array_key,
        "matches": matches,
        "match_count": len(matches),
        "scanned_records": scanned,
        "truncated": len(matches) >= limit,
    }


def main() -> int:
    args = parse_args()
    families = ["inventory", "queue"] if args.family == "all" else [args.family]
    results = [trace_family(args.date, family, args.combo_id, args.topic_id, max(1, args.limit)) for family in families]
    payload = {
        "status": "OK" if all(row["status"] == "OK" for row in results) else "PARTIAL",
        "date": args.date,
        "filters": {"combo_id": args.combo_id, "topic_id": args.topic_id},
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
