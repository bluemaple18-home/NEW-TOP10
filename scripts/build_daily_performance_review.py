#!/usr/bin/env python3
"""產生每日報牌績效復盤評論與研究派工候選。

本腳本只讀 daily_recommendation_performance / decision_quality artifacts，
把數字轉成需要回報的操盤訊號與研究卡候選；不改 ranking、model 或推播。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "daily-performance-review.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily performance review")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--performance", default=None)
    parser.add_argument("--decision-quality", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def metric(payload: dict[str, Any], horizon: str, key: str) -> float | None:
    value = ((payload.get("summary") or {}).get("by_horizon") or {}).get(horizon, {}).get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def portfolio_metric(payload: dict[str, Any], horizon: str, key: str) -> float | None:
    value = ((payload.get("summary") or {}).get("portfolio_by_horizon") or {}).get(horizon, {}).get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def build_findings(performance: dict[str, Any], decision_quality: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for horizon in ["1", "3", "5", "10"]:
        avg_return = metric(performance, horizon, "avg_net_return")
        hit_rate = metric(performance, horizon, "hit_rate")
        max_drawdown = portfolio_metric(performance, horizon, "max_drawdown")
        if avg_return is not None and avg_return < 0:
            findings.append(
                {
                    "id": f"h{horizon}-negative-average-return",
                    "severity": "high" if horizon in {"1", "3"} else "medium",
                    "title": f"D+{horizon} 平均報酬為負",
                    "detail": f"D+{horizon} avg_return={pct(avg_return)}，hit_rate={pct(hit_rate)}。",
                    "suggested_action": "拆 rank bucket / market regime / entry quality，確認是入場時機還是選股名單問題。",
                }
            )
        if hit_rate is not None and hit_rate < 0.45:
            findings.append(
                {
                    "id": f"h{horizon}-low-hit-rate",
                    "severity": "medium",
                    "title": f"D+{horizon} 命中率偏低",
                    "detail": f"D+{horizon} hit_rate={pct(hit_rate)}。",
                    "suggested_action": "優先檢查 Top1-3 與 Top8-10 是否拖累，避免平均值掩蓋 ranking 層級差異。",
                }
            )
        if max_drawdown is not None and max_drawdown <= -0.15:
            findings.append(
                {
                    "id": f"h{horizon}-portfolio-drawdown",
                    "severity": "high",
                    "title": f"D+{horizon} bucket 回撤偏大",
                    "detail": f"D+{horizon} portfolio max_drawdown={pct(max_drawdown)}。",
                    "suggested_action": "交叉檢查 gross55 / capital_entry_quality 是否能降低回撤。",
                }
            )

    summary = performance.get("summary") or {}
    trade_count = int(summary.get("trade_count") or 0)
    pending_count = int(summary.get("pending_count") or 0)
    if trade_count > 0 and pending_count / trade_count > 0.25:
        findings.append(
            {
                "id": "pending-sample-high",
                "severity": "low",
                "title": "未成熟樣本比例偏高",
                "detail": f"trade_count={trade_count}, pending_count={pending_count}。",
                "suggested_action": "報告需標示近期 horizon 尚未成熟，避免把短期 pending 當成缺資料。",
            }
        )

    dq_summary = decision_quality.get("summary") or {}
    available_count = int(dq_summary.get("daily_performance_available_count") or 0)
    top_count = int(dq_summary.get("top_count") or 0)
    if top_count and available_count < top_count:
        findings.append(
            {
                "id": "top10-performance-coverage-gap",
                "severity": "low",
                "title": "今日 Top10 部分標的缺成熟後驗",
                "detail": f"Top10 中 {available_count}/{top_count} 檔已有過去成熟績效。",
                "suggested_action": "新進榜標的只做觀察，不用單日缺後驗否定名單。",
            }
        )
    return findings


def research_cards(findings: list[dict[str, Any]], date_text: str, output_path: Path) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    ids = {item["id"] for item in findings}
    if {"h1-negative-average-return", "h3-negative-average-return"} & ids:
        cards.append(
            {
                "task_id": f"PERF-REVIEW-{date_text}-ENTRY-TIMING",
                "card_type_owner": "Performance Diagnostics｜Research Worker",
                "read": "artifacts/daily_recommendation_performance_YYYY-MM-DD.json, artifacts/decision_quality_YYYY-MM-DD.json",
                "purpose": "拆 D+1/D+3 偏弱來源：rank bucket、entry quality、market regime、入榜天數。",
                "evidence_path": repo_path(output_path) or "",
            }
        )
    if any(item["id"].endswith("portfolio-drawdown") for item in findings):
        cards.append(
            {
                "task_id": f"PERF-REVIEW-{date_text}-DRAWDOWN",
                "card_type_owner": "Risk Overlay｜Research Worker",
                "read": "artifacts/daily_recommendation_performance_YYYY-MM-DD.json, artifacts/model_experiments/daily_shadow_status_YYYY-MM-DD.json",
                "purpose": "驗證 gross55 / capital_entry_quality 是否能降低後驗 bucket 回撤。",
                "evidence_path": repo_path(output_path) or "",
            }
        )
    return cards


def operator_summary(findings: list[dict[str, Any]]) -> str:
    high = [item for item in findings if item.get("severity") == "high"]
    if high:
        return "今日復盤有高優先訊號，需要回報並轉診斷；先不要改模型或報牌規則。"
    if findings:
        return "今日復盤有觀察訊號，建議累積樣本並排入低成本診斷。"
    return "今日復盤沒有觸發明顯異常；維持監控。"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    performance_path = resolve_path(args.performance) or ARTIFACTS_DIR / f"daily_recommendation_performance_{args.date}.json"
    decision_path = resolve_path(args.decision_quality) or ARTIFACTS_DIR / f"decision_quality_{args.date}.json"
    output_path = resolve_path(args.output) or ARTIFACTS_DIR / f"daily_performance_review_{args.date}.json"
    performance = read_json(performance_path)
    decision_quality = read_json(decision_path)
    findings = build_findings(performance, decision_quality)
    cards = research_cards(findings, args.date, output_path)
    status = "NEEDS_REVIEW" if any(item.get("severity") == "high" for item in findings) else "WATCH" if findings else "OK"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "review_commentary_only": True,
            "reads_daily_performance": True,
            "reads_decision_quality": True,
            "changes_production_ranking": False,
            "changes_model": False,
            "changes_clawd_message": False,
            "creates_research_candidates_only": True,
            "live_send": False,
        },
        "inputs": {
            "performance": repo_path(performance_path) if performance_path.exists() else None,
            "decision_quality": repo_path(decision_path) if decision_path.exists() else None,
        },
        "summary": {
            "finding_count": len(findings),
            "high_count": sum(1 for item in findings if item.get("severity") == "high"),
            "research_card_count": len(cards),
            "operator_summary": operator_summary(findings),
        },
        "findings": findings,
        "research_cards": cards,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Daily Performance Review - {payload['date']}",
        "",
        f"- status: `{payload['status']}`",
        f"- summary: {payload['summary']['operator_summary']}",
        f"- findings: `{payload['summary']['finding_count']}`",
        f"- research_cards: `{payload['summary']['research_card_count']}`",
        "",
        "## Findings",
        "",
    ]
    for item in payload["findings"]:
        lines.append(f"- [{item['severity']}] {item['title']}：{item['detail']} 建議：{item['suggested_action']}")
    if payload["research_cards"]:
        lines.extend(["", "## Research Cards", ""])
        for card in payload["research_cards"]:
            lines.extend(
                [
                    f"任務ID：{card['task_id']}",
                    f"卡片類型｜派工對象：{card['card_type_owner']}",
                    f"請讀：{card['read']}",
                    f"任務目的：{card['purpose']}",
                    f"證據路徑：{card['evidence_path']}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or ARTIFACTS_DIR / f"daily_performance_review_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "finding_count": payload["summary"]["finding_count"],
                "research_card_count": payload["summary"]["research_card_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
