#!/usr/bin/env python3
"""建立 artifact inventory 與 retention dry-run 摘要。

此 CLI 永遠只做 read-only 分類；本卡不提供刪除、搬移或壓縮選項。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.artifact_management import build_inventory, load_policy, render_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立只讀 artifact retention inventory。")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT / "artifacts")
    parser.add_argument("--policy", type=Path, default=None, help="JSON policy 路徑")
    parser.add_argument("--as-of", default=None, help="分類基準日，格式 YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=None, help="寫出 structured inventory JSON")
    parser.add_argument("--json", action="store_true", help="輸出 JSON，不輸出摘要")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="明確標示 read-only 模式；未提供此旗標時仍然是 dry-run",
    )
    return parser.parse_args(argv)


def resolve_path(path: Path | None) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.as_of is not None:
        date.fromisoformat(args.as_of)
    root = resolve_path(args.root)
    policy = load_policy(resolve_path(args.policy))
    inventory = build_inventory(root, policy=policy, as_of=args.as_of)

    if args.output is not None:
        output = resolve_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        print(render_summary(inventory))
        if args.output is not None:
            print(f"inventory JSON 路徑：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
