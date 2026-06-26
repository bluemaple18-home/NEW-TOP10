#!/usr/bin/env python3
"""彙整 TOP10 研究線中需要 PM 決策的事項。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "top10-research-decision-brief.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build TOP10 research decision brief")
    parser.add_argument("--run-date", default=datetime.now().date().isoformat())
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--output-json", default=None, type=Path)
    parser.add_argument("--output-md", default=None, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    brief = build_brief(args.run_date, artifacts_dir)
    output_json = resolve_path(args.output_json) if args.output_json else default_json_path(artifacts_dir, args.run_date)
    output_md = resolve_path(args.output_md) if args.output_md else default_markdown_path(artifacts_dir, args.run_date)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(brief), encoding="utf-8")
    print(json.dumps({"status": brief["status"], "output": repo_ref(output_json), "decision_count": brief["summary"]["decision_count"]}, ensure_ascii=False))
    return 0


def build_brief(run_date: str, artifacts_dir: Path) -> dict[str, Any]:
    external_summary, external_path = load_external_summary(artifacts_dir, run_date)
    next_queue, next_queue_path = load_json_with_path(artifacts_dir / "autonomous_research" / "next_action_queue.json")
    manager_summary, manager_path = load_json_with_path(artifacts_dir / "autonomous_research" / "manager_summary.json")
    campaign_progress, campaign_path = load_json_with_path(
        artifacts_dir / "autonomous_research" / f"research_campaign_progress_{run_date}.json"
    )
    fog_verification, fog_verification_path = load_json_with_path(artifacts_dir / "research_map" / "research_fog_map_verification_latest.json")

    decisions: list[dict[str, Any]] = []
    if external_summary:
        decisions.extend(external_review_decisions(external_summary, external_path))
    if next_queue:
        decisions.extend(next_action_queue_decisions(next_queue, next_queue_path))
    decisions.extend(model_candidate_decisions(artifacts_dir))

    decisions = unique_decisions(decisions)
    decisions.sort(key=decision_sort_key)
    open_decisions = [item for item in decisions if item.get("status") == "open"]

    research_status = build_research_status(
        run_date=run_date,
        manager_summary=manager_summary,
        manager_path=manager_path,
        campaign_progress=campaign_progress,
        campaign_path=campaign_path,
        fog_verification=fog_verification,
        fog_verification_path=fog_verification_path,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "NEEDS_DECISION" if open_decisions else "NO_DECISION",
        "summary": {
            "decision_count": len(open_decisions),
            "source_count": len([item for item in [external_path, next_queue_path, manager_path, campaign_path, fog_verification_path] if item]),
            "send_to_ops_channel": bool(open_decisions),
            "language": "zh-TW",
        },
        "decision_requests": open_decisions,
        "research_status": research_status,
        "boundaries": {
            "research_only": True,
            "does_not_change_ranking": True,
            "does_not_train_model": True,
            "does_not_promote_model": True,
            "ops_report_language": "繁體中文",
        },
    }


def external_review_decisions(summary: dict[str, Any], path: Path | None) -> list[dict[str, Any]]:
    safety = summary.get("safety") if isinstance(summary.get("safety"), dict) else {}
    disagreements = list_value(summary.get("disagreements"))
    misses = list_value(summary.get("today_misses"))
    hypotheses = list_value(summary.get("research_hypotheses"))
    if not safety.get("needs_human_review") and not disagreements and not misses:
        return []
    details = []
    for item in disagreements[:3]:
        if isinstance(item, dict):
            details.append(f"{item.get('title') or item.get('type')}: {item.get('detail') or item.get('providers')}")
    for item in misses[:3]:
        if isinstance(item, dict):
            symbol = item.get("symbol") or item.get("stock_id") or item.get("name") or "未知標的"
            detail = item.get("issue") or item.get("reason") or item.get("evidence") or "外部 AI 認為需要複核"
            details.append(f"{symbol}: {detail}")
    return [
        {
            "id": f"external-review-{summary.get('review_date') or 'latest'}",
            "status": "open",
            "priority": "high" if safety.get("needs_human_review") else "medium",
            "owner_bot": "External Review Bot",
            "formal_agent": "disagreement_next_actions",
            "title": "外部 AI 檢核有分歧，需要決定後續處置",
            "why_decision_needed": "ChatGPT / Gemini 的反對點不能直接改排名，必須由你決定要轉研究卡、先人工複核，或暫時擱置。",
            "recommended_option": "同意轉成研究卡，交給迷霧與研究 worker 排隊驗證。",
            "options": [
                "同意轉成研究卡",
                "先人工複核",
                "暫時擱置，不進研究 queue",
            ],
            "details": details[:6],
            "metrics": {
                "valid_provider_count": summary.get("valid_provider_count"),
                "disagreement_count": len(disagreements),
                "today_miss_count": len(misses),
                "research_hypothesis_count": len(hypotheses),
                "needs_human_review": bool(safety.get("needs_human_review")),
            },
            "artifact_paths": [repo_ref(path)] if path else [],
        }
    ]


def next_action_queue_decisions(queue: dict[str, Any], path: Path | None) -> list[dict[str, Any]]:
    actions = [item for item in list_value(queue.get("actions")) if isinstance(item, dict)]
    decisions = []
    for item in actions[:8]:
        action = str(item.get("next_action") or "")
        manager_status = str(item.get("manager_status") or "")
        if action == "promote_to_longer_replay_candidate" or manager_status == "confirmed_for_next_replay":
            title = "候選策略已確認可進下一階段 replay"
            recommended = "同意升級長窗 replay，但仍不允許直接改 ranking 或模型。"
            options = ["同意升級長窗 replay", "先留在觀察", "拒絕此候選"]
            priority = "high"
        elif action == "rerun_with_larger_window_or_add_risk_check" or manager_status == "partial_needs_followup":
            title = "候選策略需要追加樣本或風控檢查"
            recommended = "同意用較長窗口或額外風控檢查重跑一次。"
            options = ["同意追加驗證", "先降低優先序", "暫停此候選"]
            priority = "medium"
        else:
            continue
        decisions.append(
            {
                "id": "research-queue-" + stable_slug(str(item.get("topic_id") or item.get("candidate_dir") or action)),
                "status": "open",
                "priority": priority,
                "owner_bot": "Research Worker Bot",
                "formal_agent": "research_worker",
                "title": title,
                "why_decision_needed": "這會消耗下一輪研究資源；通過後也只會產生證據，不會直接升正式排名。",
                "recommended_option": recommended,
                "options": options,
                "details": [
                    f"候選：{item.get('candidate_dir') or item.get('topic_id') or '未知'}",
                    f"分數：{item.get('score', '未知')}",
                    f"最近判定：{item.get('last_decision') or manager_status or '未知'}",
                ],
                "metrics": {
                    "score": item.get("score"),
                    "manager_status": manager_status,
                    "next_action": action,
                },
                "artifact_paths": [repo_ref(path)] if path else [],
            }
        )
    return decisions


def model_candidate_decisions(artifacts_dir: Path) -> list[dict[str, Any]]:
    candidates = [
        artifacts_dir / "model_experiments" / "odd_lot_candidate_decision_report_verification_latest.json",
        artifacts_dir / "model_experiments" / "portfolio_overlay_promotion_review_verification_latest.json",
    ]
    decisions = []
    for path in candidates:
        payload, payload_path = load_json_with_path(path)
        if not payload or payload.get("status") != "OK":
            continue
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        decision = str(summary.get("decision") or check_value(payload, "status_known") or "")
        selected = summary.get("selected_candidate") or check_value(payload, "selected_candidate") or "未指定候選"
        next_stage = summary.get("next_stage") or "human_review"
        if decision not in {"READY_FOR_SHADOW_MONITOR", "READY_FOR_HUMAN_REVIEW"}:
            continue
        decisions.append(
            {
                "id": "model-candidate-" + stable_slug(path.stem.replace("_verification_latest", "")),
                "status": "open",
                "priority": "medium",
                "owner_bot": "Research Worker Bot",
                "formal_agent": "research_worker",
                "title": "模型候選研究已到人工決策點",
                "why_decision_needed": "驗證器已通過，但 production promotion 仍被禁止；需要你決定是否進 shadow monitor / 下一階段驗證。",
                "recommended_option": "同意進 shadow monitor 或下一階段驗證，不直接升正式模型。",
                "options": ["同意進下一階段驗證", "先補資料再說", "拒絕此候選"],
                "details": [
                    f"候選：{selected}",
                    f"目前判定：{decision}",
                    f"下一階段：{next_stage}",
                ],
                "metrics": {
                    "decision": decision,
                    "selected_candidate": selected,
                    "next_stage": next_stage,
                },
                "artifact_paths": [repo_ref(payload_path)] if payload_path else [],
            }
        )
    return decisions


def build_research_status(
    *,
    run_date: str,
    manager_summary: dict[str, Any] | None,
    manager_path: Path | None,
    campaign_progress: dict[str, Any] | None,
    campaign_path: Path | None,
    fog_verification: dict[str, Any] | None,
    fog_verification_path: Path | None,
) -> dict[str, Any]:
    campaign_summary = campaign_progress.get("summary") if isinstance(campaign_progress, dict) and isinstance(campaign_progress.get("summary"), dict) else {}
    return {
        "run_date": run_date,
        "fog_map_status": fog_verification.get("status") if isinstance(fog_verification, dict) else None,
        "manager_status": manager_summary.get("status") if isinstance(manager_summary, dict) else None,
        "next_action_count": manager_summary.get("next_action_count") if isinstance(manager_summary, dict) else None,
        "expanded_processed": campaign_summary.get("expanded_processed"),
        "expanded_universe_total": campaign_summary.get("expanded_universe_total"),
        "expanded_progress_pct": campaign_summary.get("expanded_progress_pct"),
        "next_action": campaign_summary.get("next_action"),
        "artifact_paths": [repo_ref(item) for item in [manager_path, campaign_path, fog_verification_path] if item],
    }


def render_markdown(brief: dict[str, Any]) -> str:
    lines = [
        f"TOP10 研究決策 brief｜{brief['run_date']}",
        "",
        f"- 狀態：{status_label(brief['status'])}",
        f"- 需要你決策：`{brief['summary']['decision_count']}` 件",
        "- 邊界：只做研究與驗證，不直接改排名、不訓練模型、不升正式模型。",
        "",
    ]
    decisions = list_value(brief.get("decision_requests"))
    if decisions:
        lines.append("需要你決策")
        for index, item in enumerate(decisions[:8], start=1):
            lines.extend(
                [
                    f"{index}. {priority_label(item.get('priority'))}｜{item.get('title')}",
                    f"   - 建議：{item.get('recommended_option')}",
                    f"   - 原因：{item.get('why_decision_needed')}",
                    f"   - 選項：{' / '.join(str(option) for option in list_value(item.get('options')))}",
                ]
            )
            artifacts = list_value(item.get("artifact_paths"))
            if artifacts:
                lines.append(f"   - 證據：{', '.join(f'`{artifact}`' for artifact in artifacts[:3])}")
        lines.append("")
    else:
        lines.extend(["需要你決策", "- 目前沒有新的人工決策事項。", ""])

    status = brief.get("research_status") if isinstance(brief.get("research_status"), dict) else {}
    lines.extend(
        [
            "常態研究狀態",
            f"- 迷霧地圖：{status.get('fog_map_status') or '未知'}",
            f"- 研究 manager：{status.get('manager_status') or '未知'}；待處理：`{status.get('next_action_count', '未知')}`",
            f"- expanded progress：`{status.get('expanded_processed', '未知')}/{status.get('expanded_universe_total', '未知')}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def load_external_summary(artifacts_dir: Path, run_date: str) -> tuple[dict[str, Any] | None, Path | None]:
    dated = artifacts_dir / "external_review" / run_date / f"external_review_summary_{run_date}.json"
    if dated.exists():
        return load_json_with_path(dated)
    candidates = sorted((artifacts_dir / "external_review").glob("*/external_review_summary_*.json"), reverse=True)
    if not candidates:
        return None, None
    return load_json_with_path(candidates[0])


def load_json_with_path(path: Path) -> tuple[dict[str, Any] | None, Path | None]:
    if not path.exists():
        return None, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None, path
    return payload, path


def check_value(payload: dict[str, Any], name: str) -> Any:
    for check in list_value(payload.get("checks")):
        if isinstance(check, dict) and check.get("name") == name:
            return check.get("value")
    return None


def unique_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in decisions:
        decision_id = str(item.get("id") or "")
        if not decision_id or decision_id in seen:
            continue
        seen.add(decision_id)
        result.append(item)
    return result


def decision_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    priority = {"high": 0, "medium": 1, "low": 2}.get(str(item.get("priority")), 3)
    return priority, str(item.get("id") or "")


def status_label(status: Any) -> str:
    return {"NEEDS_DECISION": "需要決策", "NO_DECISION": "沒有新決策"}.get(str(status), str(status))


def priority_label(priority: Any) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(str(priority), "未分級")


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_slug(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {":", "/", "_", "-", "."}:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:96] or "unknown"


def default_json_path(artifacts_dir: Path, run_date: str) -> Path:
    return artifacts_dir / "research_decisions" / f"research_decision_brief_{run_date}.json"


def default_markdown_path(artifacts_dir: Path, run_date: str) -> Path:
    return artifacts_dir / "research_decisions" / f"research_decision_brief_{run_date}.md"


def resolve_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("path is required")
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_ref(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return f"local_artifact/{path.name}"


if __name__ == "__main__":
    raise SystemExit(main())
