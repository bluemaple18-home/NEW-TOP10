#!/usr/bin/env python3
"""驗證 top10-agent-status-event.v1。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from top10_agent_status import DEFAULT_MANIFEST_PATH, read_manifest, validate_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify top10-agent-status-event.v1 JSON")
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    event_path = resolve(args.event)
    manifest_path = resolve(args.manifest)
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    errors = validate_event(payload, read_manifest(manifest_path))
    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "event": repo_path(event_path), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
