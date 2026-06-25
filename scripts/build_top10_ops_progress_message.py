#!/usr/bin/env python3
"""產生 TOP10 工作進度頻道訊息。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "top10-ops-progress-message.v1"
STATUS_LABELS = {
    "ok": "正常",
    "pass": "通過",
    "warning": "警告",
    "degraded": "降級",
    "failed": "失敗",
    "blocked": "阻塞",
    "skipped": "略過",
    "pending": "等待中",
    "unknown": "未知",
}
AGENT_LABELS = {
    "harness_runner": "主控排程",
    "preflight": "事前檢查",
    "data_etl": "資料擷取與整理",
    "data_quality_gate": "資料品質閘門",
    "ranking": "每日排名",
    "anomaly_circuit_breaker": "異常與熔斷檢查",
    "daily_push": "報牌推播",
    "outcome_tracker": "市場後驗追蹤",
    "external_review_harness": "外部檢核主控",
    "ai_review_adapter": "雙 AI 檢核接頭",
    "disagreement_next_actions": "分歧與後續處置",
    "fog_map": "迷霧地圖",
    "research_worker": "自主研究 worker",
    "ops_reporter": "工作進度回報",
}
ACTION_LABELS = {
    "continue to daily publish gate and external review branch": "可以交給報牌閘門與外部檢核支線。",
    "daily pick message sent to report channel": "今日報牌訊息已送到報牌頻道。",
    "review decision_quality/postcheck warning before relying on publish or external review": "先檢查決策品質或收盤後檢查警告，再依賴報牌或外部檢核。",
    "review missing provider before trusting disagreement summary": "先確認缺少的外部 AI 回覆，再採信分歧摘要。",
    "manual review required before using external review": "使用外部檢核前需要人工複核。",
    "wait for daily OK before external review": "等待每日流程正常後，再啟動外部檢核。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build TOP10 ops progress message")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--output", default=None, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    rollup_path = resolve_rollup_path(artifacts_dir, args.run_date, args.run_id)
    if rollup_path is None:
        raise SystemExit("missing TOP10 harness rollup; run daily status recorder first")
    rollup = read_json(rollup_path)
    run_date = str(rollup.get("run_date") or args.run_date or datetime.now().date().isoformat())
    external_summary = load_external_summary(artifacts_dir, run_date)
    message = render_ops_message(rollup, external_summary, rollup_path=rollup_path, artifacts_dir=artifacts_dir)
    output = resolve_path(args.output) if args.output else artifacts_dir / f"ops_progress_message_{run_date}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(message, encoding="utf-8")
    status_path = artifacts_dir / f"ops_progress_message_status_{run_date}.json"
    status_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "run_date": run_date,
                "run_id": rollup.get("run_id"),
                "message_path": safe_ref(output, artifacts_dir),
                "rollup_path": safe_ref(rollup_path, artifacts_dir),
                "external_review_summary_path": safe_ref(external_summary["_path"], artifacts_dir)
                if external_summary and external_summary.get("_path")
                else None,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "message": safe_ref(output, artifacts_dir)}, ensure_ascii=False))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_rollup_path(artifacts_dir: Path, run_date: str | None, run_id: str | None) -> Path | None:
    root = artifacts_dir / "harness_status"
    if run_date and run_id:
        return root / run_date / run_id / "rollup.json"
    if run_date:
        return root / run_date / "latest_rollup.json"
    candidates = sorted(root.glob("*/latest_rollup.json"), reverse=True)
    return candidates[0] if candidates else None


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def load_external_summary(artifacts_dir: Path, run_date: str) -> dict[str, Any] | None:
    path = artifacts_dir / "external_review" / run_date / f"external_review_summary_{run_date}.json"
    if not path.exists():
        return None
    payload = read_json(path)
    payload["_path"] = path
    return payload


def render_ops_message(rollup: dict[str, Any], external_summary: dict[str, Any] | None, *, rollup_path: Path, artifacts_dir: Path) -> str:
    run_date = str(rollup.get("run_date") or "unknown")
    run_id = str(rollup.get("run_id") or "unknown")
    status = str(rollup.get("status") or "unknown")
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    agents = rollup.get("agents") if isinstance(rollup.get("agents"), list) else []
    problem_agents = [
        agent
        for agent in agents
        if isinstance(agent, dict) and str(agent.get("status")) in {"failed", "blocked", "warning", "degraded", "skipped", "pending"}
    ]
    failed_agents = [agent for agent in problem_agents if str(agent.get("status")) in {"failed", "blocked"}]
    warning_agents = [agent for agent in problem_agents if str(agent.get("status")) not in {"failed", "blocked"}]

    lines = [
        f"TOP10 工作進度｜{run_date}",
        "",
        f"- 執行代號：`{run_id}`",
        f"- 總狀態：{status_label(status)}",
        f"- 已回報節點：`{summary.get('event_count', 0)}/{summary.get('agent_count', 0)}`",
        f"- 失敗：`{summary.get('failed_count', 0)}`；警告：`{summary.get('warning_count', 0)}`；缺漏：`{summary.get('missing_count', 0)}`",
        f"- 證據檔：`{safe_ref(rollup_path, artifacts_dir)}`",
        "",
    ]

    if failed_agents:
        lines.append("阻塞項目")
        lines.extend(render_agent_rows(failed_agents[:6]))
        lines.append("")
    elif warning_agents:
        lines.append("需要注意")
        lines.extend(render_agent_rows(warning_agents[:6]))
        lines.append("")
    else:
        lines.extend(["狀態", "- daily harness 目前沒有 blocker。", ""])

    lines.extend(render_external_review_section(external_summary))
    lines.extend(render_next_actions(problem_agents, external_summary))
    return "\n".join(lines).rstrip() + "\n"


def render_agent_rows(agents: list[dict[str, Any]]) -> list[str]:
    rows = []
    for agent in agents:
        agent_id = str(agent.get("agent_id") or "")
        label = agent_label(agent)
        status = status_label(agent.get("status"))
        reason = translate_text(agent.get("failure_reason") or agent.get("next_action") or "沒有細節")
        if agent_id == "ai_review_adapter" and str(agent.get("failure_reason") or "").strip().lower() in {"chatgpt", "gemini"}:
            reason = f"{provider_label(agent.get('failure_reason'))} 尚未完成或需要複核。"
        rows.append(f"- {status}｜{label}：{reason}")
    return rows


def render_external_review_section(external_summary: dict[str, Any] | None) -> list[str]:
    if not external_summary:
        return ["外部 AI 檢核", "- 尚未有 ChatGPT / Gemini 的檢核摘要。", ""]
    valid_count = external_summary.get("valid_provider_count", 0)
    disagreements = list_value(external_summary.get("disagreements"))
    today_misses = list_value(external_summary.get("today_misses"))
    safety = external_summary.get("safety") if isinstance(external_summary.get("safety"), dict) else {}
    rows = [
        "外部 AI 檢核",
        f"- 有效回覆：`{valid_count}`；需要人工複核：{yes_no(bool(safety.get('needs_human_review')))}",
    ]
    if disagreements:
        rows.append("- 跟我們結果明顯不一致：")
        for item in disagreements[:5]:
            if isinstance(item, dict):
                rows.append(f"  - {translate_text(item.get('title') or item.get('type'))}：{translate_text(item.get('detail') or item.get('providers'))}")
    if today_misses:
        rows.append("- AI 認為今天可能漏看的點：")
        for item in today_misses[:5]:
            if isinstance(item, dict):
                symbol = item.get("stock_id") or item.get("symbol") or item.get("name") or "未知標的"
                reason = item.get("reason") or item.get("detail") or item.get("note") or item.get("provider")
                rows.append(f"  - {symbol}：{translate_text(reason)}")
    if not disagreements and not today_misses:
        rows.append("- 目前沒有明確反對點或今日漏看清單。")
    rows.append("")
    return rows


def render_next_actions(problem_agents: list[dict[str, Any]], external_summary: dict[str, Any] | None) -> list[str]:
    actions = []
    for agent in problem_agents:
        if isinstance(agent, dict) and agent.get("next_action"):
            actions.append(str(agent["next_action"]))
    if external_summary:
        disagreements = list_value(external_summary.get("disagreements"))
        today_misses = list_value(external_summary.get("today_misses"))
        if disagreements or today_misses:
            actions.append("把外部 AI 反對點轉成 research card；不能直接改 ranking。")
    if not actions:
        actions.append("等待下一輪 daily 或 external review。")
    rows = ["下一步"]
    rows.extend(f"- {translate_text(action)}" for action in unique(actions)[:6])
    return rows


def agent_label(agent: dict[str, Any]) -> str:
    agent_id = str(agent.get("agent_id") or "")
    if agent_id in AGENT_LABELS:
        return AGENT_LABELS[agent_id]
    return translate_text(agent.get("label") or agent_id or "未知節點")


def status_label(value: Any) -> str:
    text = str(value or "unknown")
    return STATUS_LABELS.get(text, text)


def provider_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == "chatgpt":
        return "ChatGPT"
    if text == "gemini":
        return "Gemini"
    return str(value or "外部 AI")


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def translate_text(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(translate_text(item) for item in value)
    text = str(value or "").strip()
    if not text:
        return "沒有細節"
    if text in ACTION_LABELS:
        return ACTION_LABELS[text]
    replacements = {
        "review decision_quality/postcheck warning before relying on publish or external review": "先檢查決策品質或收盤後檢查警告，再依賴報牌或外部檢核",
        "review missing provider before trusting disagreement summary": "先確認缺少的外部 AI 回覆，再採信分歧摘要",
        "manual review required before using external review": "使用外部檢核前需要人工複核",
        "do not publish ranking until data is repaired": "資料修好前不要報牌。",
        "coverage below threshold": "資料覆蓋率低於門檻",
        "risk view opposite": "風險判讀相反",
        "AI thinks setup is stronger than our list": "外部 AI 認為這個型態比我們名單更強",
        "missing provider": "外部 AI 回覆缺漏",
        "provider": "外部 AI",
        "reviewer": "外部檢核",
        "review": "檢核",
        "summary": "摘要",
        "manual": "人工",
        "required": "需要",
        "before": "先",
        "trusting": "採信",
        "decision_quality": "決策品質",
        "postcheck": "收盤後檢查",
        "publish": "報牌",
        "external": "外部",
        "chatgpt": "ChatGPT",
        "gemini": "Gemini",
        "only flagged by": "只有這個外部 AI 標記",
        "research card": "研究卡",
        "ranking": "排名",
        "keep single reviewer flag instead of averaging it away": "保留單一外部檢核標記，不在摘要中平均掉",
        "保留單一 reviewer 標記，不在 summary 中平均掉": "保留單一外部檢核標記，不在摘要中平均掉",
        "單一 外部檢核": "單一外部檢核",
        "外部檢核 標記": "外部檢核標記",
        "不在 摘要": "不在摘要",
        "不在摘要 中": "不在摘要中",
        "轉成 研究卡": "轉成研究卡",
        "改 排名": "改排名",
        "unknown": "未知",
        "no detail": "沒有細節",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def safe_ref(path: str | Path, artifacts_dir: Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        return str(value)
    try:
        return str(value.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        pass
    try:
        return str(value.resolve().relative_to(artifacts_dir.resolve()))
    except ValueError:
        return f"local_artifact/{value.name}"


if __name__ == "__main__":
    raise SystemExit(main())
