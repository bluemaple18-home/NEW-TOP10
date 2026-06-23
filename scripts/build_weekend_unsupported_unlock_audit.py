#!/usr/bin/env python3
"""建立 weekend unsupported unlock audit。

這份 audit 只決定 unsupported 是否值得解鎖與下一步，不執行 replay、
不修改 production ranking、不訓練模型。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, now_utc, repo_path, rollup_paths, write_json, write_text


SCHEMA_VERSION = "weekend-unsupported-unlock-audit.v1"
WEEKEND_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "weekend_training"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend unsupported unlock audit")
    parser.add_argument("--date", required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def audit_paths(date: str) -> tuple[Path, Path]:
    stem = f"weekend_unsupported_unlock_audit_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def category_plan(category: str, count: int, reason_counts: dict[str, int]) -> dict[str, Any]:
    top_reasons = [
        {"reason": reason, "count": value}
        for reason, value in reason_counts.items()
        if reason_matches_category(reason, category)
    ][:5]
    if category == "UNSUPPORTED_RANKING_DIR_MISSING":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "SMOKE_UNLOCK_CANDIDATE",
            "priority": 1,
            "can_unlock_now": False,
            "why": "這類最像 artifact 接線缺口，但不能直接假設缺的 ranking 目錄等價於現有目錄。",
            "risk": "若直接補路徑，可能把不同 ranking source 混成同一條策略。",
            "next_action": "先做 ranking dir availability smoke：選 1 個 topic、1 個 entry filter、1 個 horizon，確認 baseline/candidate 目錄來源後再展開。",
            "top_reasons": top_reasons,
        }
    if category == "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "CONTRACT_DECISION_REQUIRED",
            "priority": 2,
            "can_unlock_now": False,
            "why": "`TOPIC_DEFAULT` 不是 replay runner 支援的 entry filter，不能偷映射成 LOG_GATE 或 PERCENTILE_GATE。",
            "risk": "錯誤映射會讓同一個研究點代表不同進場邏輯，地圖會失真。",
            "next_action": "先定義 TOPIC_DEFAULT 是 topic 原生 filter、NONE filter，還是 deprecated coordinate；只允許 smoke 驗證，不直接大跑。",
            "top_reasons": top_reasons,
        }
    if category == "UNSUPPORTED_REGIME_SLICE_NO_DATA":
        return {
            "category": category,
            "count": count,
            "unlock_decision": "HOLD_UNSUPPORTED_FOR_NOW",
            "priority": 3,
            "can_unlock_now": False,
            "why": "數量最大，但牽涉 NEUTRAL / PANIC_SELLING / RISK_OFF 的樣本與合約定義；直接展開會把低樣本盤勢當有效結論。",
            "risk": "容易把防守盤、崩跌盤與牛市策略混在一起，產生看似完整但不可交易的結論。",
            "next_action": "先做 regime-slice data adequacy audit，確認各 regime 的日期數、可比較 ranking、交易結果樣本，再決定是否開子宇宙。",
            "top_reasons": top_reasons,
        }
    return {
        "category": category,
        "count": count,
        "unlock_decision": "MANUAL_REVIEW_REQUIRED",
        "priority": 99,
        "can_unlock_now": False,
        "why": "未知 unsupported category，需要先拆穩定分類。",
        "risk": "分類不清會污染 burn-down 統計。",
        "next_action": "補 category contract 後再評估。",
        "top_reasons": top_reasons,
    }


def reason_matches_category(reason: str, category: str) -> bool:
    if category == "UNSUPPORTED_RANKING_DIR_MISSING":
        return reason.startswith("MISSING_BASELINE_RANKINGS_DIR:") or reason.startswith("MISSING_CANDIDATE_RANKINGS_DIR:")
    if category == "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE":
        return reason.startswith("UNSUPPORTED_ENTRY_FILTER:")
    if category == "UNSUPPORTED_REGIME_SLICE_NO_DATA":
        return reason.startswith("UNSUPPORTED_REGIME_GATE:")
    return False


def build_payload(date: str) -> dict[str, Any]:
    rollup_path, _ = rollup_paths(date)
    rollup = read_json(rollup_path)
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    category_counts = summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {}
    reason_counts = summary.get("unsupported_reason_top_counts") if isinstance(summary.get("unsupported_reason_top_counts"), dict) else {}
    categories = [
        category_plan(str(category), int(count or 0), {str(k): int(v or 0) for k, v in reason_counts.items()})
        for category, count in sorted(category_counts.items())
    ]
    categories.sort(key=lambda item: int(item["priority"]))
    unsupported_count = int(summary.get("unsupported_count") or 0)
    category_total = sum(int(item["count"]) for item in categories)
    errors: list[str] = []
    if category_total != unsupported_count:
        errors.append("category total does not match unsupported_count")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK" if not errors else "FAILED",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"rollup": repo_path(rollup_path)},
        "summary": {
            "unsupported_count": unsupported_count,
            "category_total": category_total,
            "category_count": len(categories),
            "first_unlock_candidate": categories[0]["category"] if categories else None,
            "first_unlock_decision": categories[0]["unlock_decision"] if categories else None,
            "can_unlock_now_count": sum(1 for item in categories if item.get("can_unlock_now") is True),
        },
        "categories": categories,
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
        },
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Unsupported Unlock Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- unsupported_count: `{summary['unsupported_count']}`",
        f"- category_total: `{summary['category_total']}`",
        f"- first_unlock_candidate: `{summary['first_unlock_candidate']}`",
        f"- first_unlock_decision: `{summary['first_unlock_decision']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Categories",
        "",
    ]
    for item in payload["categories"]:
        lines.extend(
            [
                f"### {item['category']}",
                "",
                f"- count: `{item['count']}`",
                f"- unlock_decision: `{item['unlock_decision']}`",
                f"- priority: `{item['priority']}`",
                f"- can_unlock_now: `{item['can_unlock_now']}`",
                f"- why: {item['why']}",
                f"- risk: {item['risk']}",
                f"- next_action: {item['next_action']}",
                "",
            ]
        )
        if item["top_reasons"]:
            lines.append("Top reasons:")
            for reason in item["top_reasons"]:
                lines.append(f"- `{reason['reason']}`: `{reason['count']}`")
            lines.append("")
    lines.append("No production ranking, model, or Clawd changes.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date)
    json_path, md_path = audit_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(json_path),
                "first_unlock_candidate": payload["summary"]["first_unlock_candidate"],
                "unsupported_count": payload["summary"]["unsupported_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
