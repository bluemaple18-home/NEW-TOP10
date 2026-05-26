#!/usr/bin/env python3
"""列印自動化流程狀態摘要，供 shell wrapper 與 launchd log 使用。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="print automation status")
    parser.add_argument("--status", default="artifacts/automation_status.json")
    parser.add_argument("--min-started-at-epoch", type=float, default=None)
    parser.add_argument("--label", default="每日")
    parser.add_argument("--summary-prefix", default="daily_run_summary")
    args = parser.parse_args()

    status_path = Path(args.status)
    if not status_path.exists():
        print(f"📄 {args.label}狀態: {status_path}")
        print("⚠️ automation_status.json 不存在")
        return 1

    payload: dict[str, Any] = json.loads(status_path.read_text(encoding="utf-8"))
    started_at = payload.get("started_at")
    if args.min_started_at_epoch is not None:
        if not started_at:
            print(f"📄 {args.label}狀態: {status_path}")
            print("⚠️ 本次未產生有效 status：status 缺少 started_at")
            return 1
        try:
            status_epoch = datetime.fromisoformat(str(started_at)).timestamp()
        except ValueError:
            print(f"📄 {args.label}狀態: {status_path}")
            print(f"⚠️ 本次未產生有效 status：started_at 格式錯誤 {started_at}")
            return 1
        if status_epoch < args.min_started_at_epoch:
            print(f"📄 {args.label}狀態: {status_path}")
            print(f"⚠️ 本次未產生有效 status：status started_at={started_at} 早於 wrapper start epoch={args.min_started_at_epoch:.0f}")
            return 1

    run_date = payload.get("run_date") or "unknown"
    mode = payload.get("mode") or "unknown"
    status = payload.get("status") or "UNKNOWN"
    skip_reason = payload.get("skip_reason")
    metadata = payload.get("metadata") or {}
    summary_path = status_path.parent / f"{args.summary_prefix}_{run_date}.json" if args.summary_prefix else None
    ranking_artifact = metadata.get("ranking_artifact")
    expected_ranking_artifact = metadata.get("expected_ranking_artifact")

    print(f"📌 {args.label}狀態: {status} mode={mode} run_date={run_date}")
    if skip_reason:
        print(f"⏭️ Skip reason: {skip_reason}")
    print(f"📄 {args.label}狀態檔: {status_path}")
    if summary_path:
        print(f"📄 {args.label}摘要: {summary_path}")

    if mode == "daily":
        if ranking_artifact and Path(ranking_artifact).exists():
            print(f"📄 選股結果: {ranking_artifact}")
        elif expected_ranking_artifact:
            print(f"📄 預期選股結果: {expected_ranking_artifact}")
            print("⚠️ 尚未確認該 ranking artifact 存在")
        else:
            print("📄 選股結果: 無")
    elif mode == "retrain":
        retrain = metadata.get("retrain") or {}
        backup = (retrain.get("backup_model") or {}).get("path") or retrain.get("expected_backup_model")
        new_model = (retrain.get("new_model") or {}).get("path")
        sealed = retrain.get("sealed_oos_report") or {}
        rollback = retrain.get("rollback") or {}
        if backup:
            print(f"📄 模型備份: {backup}")
        if new_model:
            print(f"📄 新模型: {new_model}")
        if sealed:
            print(f"🔒 Sealed OOS: {sealed.get('status')} {sealed.get('path')}")
        if rollback:
            print(f"↩️ 已回滾模型: {rollback.get('restored_from')}")

    if payload.get("errors"):
        print("❌ Errors:")
        for error in payload["errors"]:
            print(f"  - {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
