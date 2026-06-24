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
        f"TOP10 工作進度 {run_date}",
        "",
        f"- run_id: `{run_id}`",
        f"- harness_status: `{status}`",
        f"- events: `{summary.get('event_count', 0)}/{summary.get('agent_count', 0)}`",
        f"- failed: `{summary.get('failed_count', 0)}` warning: `{summary.get('warning_count', 0)}` missing: `{summary.get('missing_count', 0)}`",
        f"- rollup: `{safe_ref(rollup_path, artifacts_dir)}`",
        "",
    ]

    if failed_agents:
        lines.append("Blocker")
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
        label = agent.get("label") or agent.get("agent_id")
        status = agent.get("status")
        reason = agent.get("failure_reason") or agent.get("next_action") or "no detail"
        rows.append(f"- `{status}` {label}: {reason}")
    return rows


def render_external_review_section(external_summary: dict[str, Any] | None) -> list[str]:
    if not external_summary:
        return ["外部 AI review", "- 尚未有 ChatGPT/Gemini review summary。", ""]
    valid_count = external_summary.get("valid_provider_count", 0)
    disagreements = list_value(external_summary.get("disagreements"))
    today_misses = list_value(external_summary.get("today_misses"))
    safety = external_summary.get("safety") if isinstance(external_summary.get("safety"), dict) else {}
    rows = [
        "外部 AI review",
        f"- valid_providers: `{valid_count}` needs_human_review: `{bool(safety.get('needs_human_review'))}`",
    ]
    if disagreements:
        rows.append("- 跟我們結果明顯不一致：")
        for item in disagreements[:5]:
            if isinstance(item, dict):
                rows.append(f"  - {item.get('title') or item.get('type')}: {item.get('detail') or item.get('providers')}")
    if today_misses:
        rows.append("- AI 認為今天可能漏看的點：")
        for item in today_misses[:5]:
            if isinstance(item, dict):
                symbol = item.get("stock_id") or item.get("symbol") or item.get("name") or "unknown"
                reason = item.get("reason") or item.get("detail") or item.get("note") or item.get("provider")
                rows.append(f"  - {symbol}: {reason}")
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
    rows.extend(f"- {action}" for action in unique(actions)[:6])
    return rows


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
