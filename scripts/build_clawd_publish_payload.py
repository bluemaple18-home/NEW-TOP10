#!/usr/bin/env python3
"""從每日決策日報產出 Clawd 頻道發送 payload。

此腳本只做 artifact 轉換，不呼叫 Clawd、不發送訊息、不讀取 token。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.publishing.clawd_payload import (  # noqa: E402
    PAYLOAD_SCHEMA_VERSION,
    ai_feature_names,
    build_payload as build_domain_payload,
    classified_publish_sections,
    notification_summary,
    raw_signal_texts,
)
from app.publishing.clawd_payload_io import load_payload_reference_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="產生 Clawd-ready Top10 推播 payload")
    parser.add_argument("--date", default=None, help="日報日期，格式 YYYY-MM-DD；未指定時使用最新 daily_report")
    parser.add_argument("--report", default=None, help="指定 daily_report JSON 路徑")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--channel", default=None, help="Clawd channel，例如 discord / line / slack")
    parser.add_argument("--to", default=None, help="Clawd target，例如 channel:123")
    parser.add_argument("--max-items", type=int, default=10, help="訊息內最多列出幾檔")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / args.artifacts_dir
    report_path = resolve_report_path(artifacts_dir=artifacts_dir, date=args.date, report=args.report)
    report = load_json(report_path)
    payload = build_payload(
        report=report,
        report_path=report_path,
        channel=args.channel,
        to=args.to,
        max_items=args.max_items,
    )

    ranking_date = payload["ranking_date"]
    payload_path = artifacts_dir / f"clawd_publish_payload_{ranking_date}.json"
    message_path = artifacts_dir / f"clawd_publish_message_{ranking_date}.md"
    payload["artifacts"]["payload"] = str(payload_path)
    payload["artifacts"]["message"] = str(message_path)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    message_path.write_text(payload["message_markdown"], encoding="utf-8")
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CLAWD_PUBLISH_PAYLOAD_OK json={payload_path} md={message_path} status={payload['delivery']['status']}")
    return 0


def resolve_report_path(artifacts_dir: Path, date: str | None, report: str | None) -> Path:
    if report:
        path = Path(report)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 daily report 不存在：{path}")

    if date:
        path = artifacts_dir / f"daily_report_{date}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 daily report 不存在：{path}")

    files = sorted(artifacts_dir.glob("daily_report_*.json"))
    if not files:
        raise FileNotFoundError("找不到 daily_report_*.json")
    return files[-1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(
    report: dict[str, Any],
    report_path: Path,
    channel: str | None,
    to: str | None,
    max_items: int,
) -> dict[str, Any]:
    """保留既有 script import 介面，並在 I/O boundary 載入外部 lookup。"""
    return build_domain_payload(
        report=report,
        report_path=report_path,
        channel=channel,
        to=to,
        max_items=max_items,
        project_root=PROJECT_ROOT,
        **load_payload_reference_data(PROJECT_ROOT),
    )


if __name__ == "__main__":
    raise SystemExit(main())
