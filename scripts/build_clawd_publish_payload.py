#!/usr/bin/env python3
"""從每日決策日報產出 Clawd 頻道發送 payload。

此腳本只做 artifact 轉換，不呼叫 Clawd、不發送訊息、不讀取 token。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_SCHEMA_VERSION = "clawd-publish-payload.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="build Clawd-ready Top10 publish payload")
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
    ranking_date = str(report.get("ranking_date") or date_from_report_path(report_path))
    top_items = list(report.get("top10", []))[: max(1, max_items)]
    delivery_status = "READY_FOR_CLAWD" if channel and to else "PENDING_TARGET"
    missing = []
    if not channel:
        missing.append("channel")
    if not to:
        missing.append("to")

    message = render_message(report=report, ranking_date=ranking_date, top_items=top_items)
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": ranking_date,
        "source": {
            "daily_report": str(report_path),
            "ranking_artifact": report.get("ranking_artifact"),
            "automation_status": report.get("automation_status", {}),
        },
        "delivery": {
            "status": delivery_status,
            "mode": "artifact_only",
            "channel": channel,
            "to": to,
            "missing": missing,
            "send_attempted": False,
            "note": "payload 已可交給 Clawd；本腳本不負責實際發送。",
        },
        "summary": report.get("summary", {}),
        "risk": report.get("risk", {}),
        "top10": top_items,
        "message_markdown": message,
        "message_stats": {
            "characters": len(message),
            "listed_items": len(top_items),
        },
        "artifacts": {
            "payload": None,
            "message": None,
        },
    }


def date_from_report_path(path: Path) -> str:
    match = re.search(r"daily_report_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    if not match:
        raise ValueError(f"daily report 檔名無法解析日期：{path}")
    return match.group(1)


def render_message(report: dict[str, Any], ranking_date: str, top_items: list[dict[str, Any]]) -> str:
    summary = report.get("summary", {})
    automation = report.get("automation_status", {})
    risk = report.get("risk", {})
    lines = [
        f"# Top10 每日選股｜{ranking_date}",
        "",
        f"狀態：{automation.get('status') or 'UNKNOWN'}｜市場：{summary.get('market_regime') or 'UNKNOWN'}｜目標曝險：{pct(summary.get('gross_exposure'))}｜現金：{pct(summary.get('cash_weight'))}",
        "",
        "## 本日 Top10",
    ]

    for item in top_items:
        scores = item.get("scores", {})
        position = item.get("position", {})
        trade = item.get("trade_plan", {})
        lines.extend(
            [
                "",
                f"{item.get('rank')}. {item.get('stock_id')} {item.get('stock_name')}｜勝率 {pct(scores.get('model_prob'))}｜風調 {num(scores.get('risk_adjusted_score'))}｜權重 {pct(position.get('suggested_weight'))}",
                f"   進場 {num(trade.get('entry'))}｜停損 {num(trade.get('stop_loss'))}｜目標 {num(trade.get('target_price'))}｜R/R {num(trade.get('risk_reward'))}",
            ]
        )
        reason = primary_reason(item.get("reasons", []))
        if reason:
            lines.append(f"   理由：{reason}")

    notes = list(risk.get("notes", []))
    lines.extend(["", "## 風險提醒"])
    if notes:
        lines.extend(f"- {note}" for note in notes[:3])
    else:
        lines.append("- 未提供額外風險摘要；請依交易計畫控管部位。")

    freshness = risk.get("data_freshness", {}).get("datasets", {})
    if freshness:
        compact = []
        for name, info in freshness.items():
            compact.append(f"{name} latest={info.get('latest_date')} lag={info.get('lag_days')}")
        lines.extend(["", "## 資料狀態", "- " + "；".join(compact)])

    lines.append("")
    return "\n".join(lines)


def primary_reason(reasons: list[Any]) -> str:
    for reason in reasons:
        text = str(reason).strip()
        if not text:
            continue
        if text.startswith(("進場", "止損", "停損", "目標")):
            continue
        return text
    return ""


def number_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def num(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed:.2f}"


def pct(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())

