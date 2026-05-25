#!/usr/bin/env python3
"""列印每日流程狀態摘要，供 shell wrapper 與 launchd log 使用。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="print daily automation status")
    parser.add_argument("--status", default="artifacts/automation_status.json")
    parser.add_argument("--min-started-at-epoch", type=float, default=None)
    args = parser.parse_args()

    status_path = Path(args.status)
    if not status_path.exists():
        print(f"📄 每日狀態: {status_path}")
        print("⚠️ automation_status.json 不存在")
        return 1

    payload: dict[str, Any] = json.loads(status_path.read_text(encoding="utf-8"))
    started_at = payload.get("started_at")
    if args.min_started_at_epoch is not None:
        if not started_at:
            print(f"📄 每日狀態: {status_path}")
            print("⚠️ 本次未產生有效 status：status 缺少 started_at")
            return 1
        try:
            status_epoch = datetime.fromisoformat(str(started_at)).timestamp()
        except ValueError:
            print(f"📄 每日狀態: {status_path}")
            print(f"⚠️ 本次未產生有效 status：started_at 格式錯誤 {started_at}")
            return 1
        if status_epoch < args.min_started_at_epoch:
            print(f"📄 每日狀態: {status_path}")
            print(f"⚠️ 本次未產生有效 status：status started_at={started_at} 早於 wrapper start epoch={args.min_started_at_epoch:.0f}")
            return 1

    run_date = payload.get("run_date") or "unknown"
    status = payload.get("status") or "UNKNOWN"
    skip_reason = payload.get("skip_reason")
    metadata = payload.get("metadata") or {}
    summary_path = status_path.parent / f"daily_run_summary_{run_date}.json"
    ranking_artifact = metadata.get("ranking_artifact")
    expected_ranking_artifact = metadata.get("expected_ranking_artifact")

    print(f"📌 每日狀態: {status} run_date={run_date}")
    if skip_reason:
        print(f"⏭️ Skip reason: {skip_reason}")
    print(f"📄 每日狀態檔: {status_path}")
    print(f"📄 每日摘要: {summary_path}")

    if ranking_artifact and Path(ranking_artifact).exists():
        print(f"📄 選股結果: {ranking_artifact}")
    elif expected_ranking_artifact:
        print(f"📄 預期選股結果: {expected_ranking_artifact}")
        print("⚠️ 尚未確認該 ranking artifact 存在")
    else:
        print("📄 選股結果: 無")

    if payload.get("errors"):
        print("❌ Errors:")
        for error in payload["errors"]:
            print(f"  - {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
