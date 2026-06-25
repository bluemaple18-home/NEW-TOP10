#!/usr/bin/env python3
"""每日外部 review host runner。

Top10 repo 擁有流程狀態、packet 安全驗證、normalization、summary 與證據落點；
provider adapter 只負責把 verified packet 送到外部 LLM/browser session 並留下 raw text。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from top10_agent_status import build_event, write_agent_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCHEMA_VERSION = "external-review-host-runner-status.v1"
SUMMARY_SCHEMA_VERSION = "external-review-host-runner-summary.v1"
PROVIDERS = ("chatgpt", "gemini")
ALLOWED_STATUS = {"OK", "PARTIAL", "FAILED", "SKIPPED", "RUNNING"}


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run post-daily external review host harness.")
    parser.add_argument("--date", default=None, help="執行日期 YYYY-MM-DD；預設讀 automation_status.run_date")
    parser.add_argument("--run-id", default=None, help="harness status run_id；預設 daily-YYYY-MM-DD")
    parser.add_argument("--artifacts-dir", default="artifacts", type=Path)
    parser.add_argument("--wait-daily-ok-seconds", default=0, type=int, help="等待同日 daily OK 的秒數")
    parser.add_argument("--poll-seconds", default=30, type=int, help="等待 daily OK 時的輪詢間隔秒數")
    parser.add_argument(
        "--allow-existing-daily-artifacts",
        action="store_true",
        help="補跑歷史日期時，若同日 ranking/daily_report/market_context 已存在，允許不依賴目前 automation_status.json",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=PROVIDERS,
        help="只跑指定 provider；可重複指定。預設跑 chatgpt + gemini",
    )
    parser.add_argument(
        "--skip-provider-submit",
        action="store_true",
        help="不呼叫 provider adapter，只使用已存在 raw 檔做 normalize/verify",
    )
    parser.add_argument(
        "--provider-mode",
        choices=["api", "browser"],
        default=os.environ.get("TOP10_EXTERNAL_REVIEW_PROVIDER_MODE", "browser"),
        help="provider 主幹模式；正式預設 browser，api 僅作明確切換的備援",
    )
    parser.add_argument(
        "--dry-run-provider-api",
        action="store_true",
        help="provider-mode=api 時不外送，產生合法 fixture raw 以驗證整段 harness",
    )
    parser.add_argument("--skip-fog-map-handoff", action="store_true", help="不執行 harness 迷霧地圖交接節點")
    parser.add_argument("--skip-research-quota", action="store_true", help="Fog Map handoff 只刷新地圖，不跑研究 quota")
    parser.add_argument(
        "--chatgpt-command",
        default="bash scripts/review_chatgpt_chrome.sh --date {date} --packet {packet}",
        help="ChatGPT adapter command template，可用 {date} / {packet}",
    )
    parser.add_argument(
        "--gemini-command",
        default="bash scripts/review_gemini_chrome.sh --date {date} --packet {packet}",
        help="Gemini adapter command template，可用 {date} / {packet}",
    )
    parser.add_argument("--skip-ops-report", action="store_true", help="不送工作進度頻道回報")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_project_path(args.artifacts_dir)
    automation_status = read_json_if_exists(artifacts_dir / "automation_status.json")
    run_date = args.date or str(automation_status.get("run_date") or datetime.now().date().isoformat())
    providers = tuple(args.provider or PROVIDERS)

    host_dir = artifacts_dir / "host_runner" / run_date
    host_dir.mkdir(parents=True, exist_ok=True)
    status_path = host_dir / f"host_runner_status_{run_date}.json"
    host_summary_path = host_dir / f"host_runner_summary_{run_date}.json"
    run_id = args.run_id or f"daily-{run_date}"
    started_at = datetime.now(timezone.utc).isoformat()

    status = initial_status(run_date, artifacts_dir, status_path, host_summary_path, providers)
    write_json(status_path, status)
    write_status_event(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        run_date=run_date,
        agent_id="external_review_harness",
        status="running",
        started_at=started_at,
        artifact_paths=[status_path, host_summary_path],
        metrics={"providers": list(providers)},
    )

    try:
        daily_ok = wait_for_daily_ok(
            artifacts_dir,
            run_date,
            args.wait_daily_ok_seconds,
            args.poll_seconds,
            status_path,
            status,
            allow_existing_daily_artifacts=args.allow_existing_daily_artifacts,
        )
        status["daily_status_ok"] = daily_ok
        if not daily_ok:
            status["status"] = "SKIPPED"
            status["notes"].append("same-date automation_status.json is not OK; external review skipped")
            write_json(status_path, status)
            write_host_summary(host_summary_path, status, None)
            write_status_event(
                artifacts_dir=artifacts_dir,
                run_id=run_id,
                run_date=run_date,
                agent_id="external_review_harness",
                status="skipped",
                decision="stop",
                started_at=started_at,
                input_refs=[artifacts_dir / "automation_status.json"],
                artifact_paths=[status_path, host_summary_path],
                failure_reason="same-date automation_status.json is not OK",
                next_action="wait for daily OK before external review",
                metrics={"daily_status_snapshot": status.get("daily_status_snapshot")},
            )
            if not args.skip_fog_map_handoff:
                run_fog_map_handoff(
                    run_date=run_date,
                    run_id=run_id,
                    artifacts_dir=artifacts_dir,
                    skip_refresh=True,
                    skip_reason="same-date automation_status.json is not OK",
                    skip_research_quota=args.skip_research_quota,
                )
            return 0

        packet_path = artifacts_dir / "external_review" / run_date / f"review_packet_{run_date}.json"
        manifest_path = artifacts_dir / "external_review" / run_date / f"review_packet_manifest_{run_date}.json"
        run_checked(
            [
                python_bin(),
                "scripts/build_external_review_packet.py",
                "--date",
                run_date,
                "--artifacts-dir",
                str(artifacts_dir),
            ]
        )
        run_checked([python_bin(), "scripts/verify_external_review_packet.py", "--packet", str(packet_path)])
        if "manifest" in packet_path.name:
            raise RuntimeError(f"refuse to send manifest-like packet path: {packet_path}")
        status["packet_path"] = repo_relative(packet_path)
        status["packet_verified"] = True
        status["manifest_path"] = repo_relative(manifest_path) if manifest_path.exists() else None
        status["manifest_refused"] = True
        write_json(status_path, status)
        write_status_event(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            agent_id="external_review_harness",
            status="ok",
            decision="pass",
            started_at=started_at,
            input_refs=[artifacts_dir / "automation_status.json"],
            artifact_paths=[status_path, host_summary_path, packet_path, manifest_path],
            metrics={"packet_verified": True, "manifest_refused": True, "daily_status_source": status.get("daily_status_source")},
        )

        for provider in providers:
            provider_status = run_provider(
                provider=provider,
                run_date=run_date,
                packet_path=packet_path,
                artifacts_dir=artifacts_dir,
                skip_submit=args.skip_provider_submit,
                provider_mode=args.provider_mode,
                dry_run_provider_api=args.dry_run_provider_api,
                command_template=args.chatgpt_command if provider == "chatgpt" else args.gemini_command,
            )
            status[provider] = provider_status
            write_json(status_path, status)

        external_summary_path = artifacts_dir / "external_review" / run_date / f"external_review_summary_{run_date}.json"
        run_checked(
            [
                python_bin(),
                "scripts/build_external_review_summary.py",
                "--date",
                run_date,
                "--artifacts-dir",
                str(artifacts_dir / "external_review"),
            ]
        )
        run_checked([python_bin(), "scripts/verify_external_review_summary.py", "--summary", str(external_summary_path)])
        status["summary_path"] = repo_relative(external_summary_path)
        status["summary_verified"] = True

        provider_values = [status[name]["status"] for name in providers]
        if provider_values and all(value == "OK" for value in provider_values):
            status["status"] = "OK"
        elif any(value == "OK" for value in provider_values):
            status["status"] = "PARTIAL"
        else:
            status["status"] = "FAILED"
            status["notes"].append("external summary built, but no provider response verified OK")

        external_summary = read_json_if_exists(external_summary_path)
        write_host_summary(host_summary_path, status, external_summary)
        write_json(status_path, status)
        write_provider_events(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            status=status,
            providers=providers,
            started_at=started_at,
        )
        write_disagreement_event(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            external_summary_path=external_summary_path,
            external_summary=external_summary,
            started_at=started_at,
        )
        exit_code = 0 if status["status"] in {"OK", "PARTIAL"} else 1
        if not args.skip_fog_map_handoff:
            fog_exit_code = run_fog_map_handoff(
                run_date=run_date,
                run_id=run_id,
                artifacts_dir=artifacts_dir,
                skip_research_quota=args.skip_research_quota,
            )
            if fog_exit_code != 0:
                status["notes"].append("fog map handoff failed")
                write_json(status_path, status)
                exit_code = 1
        return exit_code
    except Exception as exc:
        status["status"] = "FAILED"
        status["notes"].append(str(exc))
        write_json(status_path, status)
        write_host_summary(host_summary_path, status, None)
        write_status_event(
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            run_date=run_date,
            agent_id="external_review_harness",
            status="failed",
            decision="stop",
            started_at=started_at,
            input_refs=[artifacts_dir / "automation_status.json"],
            artifact_paths=[status_path, host_summary_path],
            failure_reason=str(exc),
            next_action="inspect host runner status and retry after blocker is resolved",
        )
        if not args.skip_fog_map_handoff:
            run_fog_map_handoff(
                run_date=run_date,
                run_id=run_id,
                artifacts_dir=artifacts_dir,
                skip_refresh=True,
                skip_reason=f"external review host runner failed before fog handoff: {exc}",
                skip_research_quota=args.skip_research_quota,
            )
        print(f"EXTERNAL_REVIEW_HOST_RUNNER_FAILED output={status_path}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.skip_ops_report:
            run_ops_report(run_date=run_date, run_id=run_id, artifacts_dir=artifacts_dir)
        print(f"EXTERNAL_REVIEW_HOST_RUNNER_{status['status']} output={status_path} summary={host_summary_path}")


def initial_status(
    run_date: str,
    artifacts_dir: Path,
    status_path: Path,
    host_summary_path: Path,
    providers: tuple[str, ...],
) -> dict[str, Any]:
    review_dir = artifacts_dir / "external_review" / run_date
    status: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "RUNNING",
        "daily_status_ok": False,
        "packet_verified": False,
        "packet_path": None,
        "manifest_path": None,
        "manifest_refused": False,
        "summary_path": repo_relative(review_dir / f"external_review_summary_{run_date}.json"),
        "summary_verified": False,
        "host_runner_status_path": repo_relative(status_path),
        "host_runner_summary_path": repo_relative(host_summary_path),
        "notes": [],
    }
    for provider in PROVIDERS:
        status[provider] = provider_defaults(provider, run_date, artifacts_dir, enabled=provider in providers)
    return status


def provider_defaults(provider: str, run_date: str, artifacts_dir: Path, *, enabled: bool) -> dict[str, Any]:
    review_dir = artifacts_dir / "external_review" / run_date
    return {
        "status": "PENDING" if enabled else "SKIPPED",
        "target": provider_target(provider),
        "raw_path": repo_relative(review_dir / f"{provider}_raw_{run_date}.txt"),
        "response_path": repo_relative(review_dir / f"{provider}_response_{run_date}.json"),
        "collect_status_path": repo_relative(review_dir / f"{provider}_collect_status_{run_date}.json"),
        "provider_mode": None,
        "command": None,
        "exit_code": None,
        "notes": [] if enabled else ["provider not selected"],
    }


def provider_target(provider: str) -> str:
    if provider == "chatgpt":
        return "TOP10_CHATGPT_URL_PART browser provider or OpenAI API fallback"
    if provider == "gemini":
        return "TOP10_GEMINI_URL_PART browser provider or Gemini API fallback"
    return provider


def wait_for_daily_ok(
    artifacts_dir: Path,
    run_date: str,
    wait_seconds: int,
    poll_seconds: int,
    status_path: Path,
    status: dict[str, Any],
    *,
    allow_existing_daily_artifacts: bool,
) -> bool:
    deadline = time.monotonic() + max(wait_seconds, 0)
    while True:
        automation_status = read_json_if_exists(artifacts_dir / "automation_status.json")
        ok = (
            automation_status.get("status") == "OK"
            and automation_status.get("run_date") == run_date
            and automation_status.get("mode") == "daily"
        )
        status["daily_status_path"] = repo_relative(artifacts_dir / "automation_status.json")
        status["daily_status_snapshot"] = {
            "status": automation_status.get("status"),
            "run_date": automation_status.get("run_date"),
            "mode": automation_status.get("mode"),
        }
        if ok:
            validate_daily_artifacts(artifacts_dir, run_date)
            status["daily_status_source"] = "automation_status"
            return True
        if allow_existing_daily_artifacts:
            try:
                validate_daily_artifacts(artifacts_dir, run_date)
            except RuntimeError as exc:
                status["daily_artifact_gate"] = {"status": "FAILED", "message": str(exc)}
            else:
                status["daily_artifact_gate"] = {"status": "OK", "message": "same-date daily artifacts exist"}
                status["daily_status_source"] = "existing_daily_artifacts"
                status["notes"].append("catch-up mode used existing same-date daily artifacts")
                return True
        if time.monotonic() >= deadline:
            return False
        write_json(status_path, status)
        time.sleep(max(poll_seconds, 1))


def validate_daily_artifacts(artifacts_dir: Path, run_date: str) -> None:
    required = [
        artifacts_dir / f"ranking_{run_date}.csv",
        artifacts_dir / f"daily_report_{run_date}.json",
        artifacts_dir / f"market_context_{run_date}.json",
    ]
    missing = [repo_relative(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("same-date daily artifacts missing: " + ", ".join(missing))


def run_provider(
    provider: str,
    run_date: str,
    packet_path: Path,
    artifacts_dir: Path,
    skip_submit: bool,
    provider_mode: str,
    dry_run_provider_api: bool,
    command_template: str,
) -> dict[str, Any]:
    state = provider_defaults(provider, run_date, artifacts_dir, enabled=True)
    review_dir = artifacts_dir / "external_review" / run_date
    raw_path = review_dir / f"{provider}_raw_{run_date}.txt"
    response_path = review_dir / f"{provider}_response_{run_date}.json"
    state["provider_mode"] = provider_mode

    try:
        if not skip_submit:
            if provider_mode == "api":
                command = [
                    python_bin(),
                    "scripts/external_review_api_provider.py",
                    "--provider",
                    provider,
                    "--date",
                    run_date,
                    "--packet",
                    str(packet_path),
                    "--artifacts-dir",
                    str(artifacts_dir / "external_review"),
                ]
                if dry_run_provider_api:
                    command.append("--dry-run")
                state["preflight"] = {
                    "status": "OK",
                    "reason": None,
                    "mode": "api",
                    "dry_run": dry_run_provider_api,
                }
            else:
                preflight = run_provider_preflight(provider=provider, command_template=command_template)
                state["preflight"] = preflight
                if preflight.get("status") != "OK":
                    state["status"] = "FAILED"
                    state["notes"].append(f"provider_preflight_failed: {preflight.get('reason')}")
                    return state
                command = render_command(command_template, run_date, packet_path)
            if any("manifest" in part for part in command):
                raise RuntimeError(f"{provider}: refuse to run adapter command containing manifest")
            state["command"] = mask_command(command)
            result = run_command(command)
            state["exit_code"] = result.exit_code
            if result.exit_code != 0:
                state["notes"].append(f"adapter_failed exit_code={result.exit_code}")
                state["adapter_stdout"] = result.stdout[-2000:]
                state["adapter_stderr"] = result.stderr[-2000:]

        if not raw_path.exists():
            state["status"] = "SKIPPED" if skip_submit else "FAILED"
            state["notes"].append(f"raw response missing: {repo_relative(raw_path)}")
            return state

        normalize = [
            python_bin(),
            "scripts/normalize_external_review_response.py",
            "--provider",
            provider,
            "--date",
            run_date,
            "--raw",
            str(raw_path),
            "--packet",
            str(packet_path),
            "--out",
            str(response_path),
        ]
        run_checked(normalize)
        run_checked([python_bin(), "scripts/verify_external_review_contract.py", str(response_path)])
        state["status"] = "OK"
        state["notes"].append("normalized_contract_ok")
        return state
    except Exception as exc:
        state["status"] = "FAILED"
        state["notes"].append(str(exc))
        return state


def run_provider_preflight(*, provider: str, command_template: str) -> dict[str, Any]:
    probe_command = provider_probe_command(command_template)
    result = run_command(probe_command)
    payload = parse_probe_payload(result.stdout)
    reason = provider_preflight_reason(provider=provider, result=result, payload=payload)
    return {
        "status": "OK" if reason is None else "FAILED",
        "reason": reason,
        "command": mask_command(probe_command),
        "exit_code": result.exit_code,
        "url": payload.get("url"),
        "title": payload.get("title"),
        "has_composer": payload.get("hasComposer"),
        "has_send_button": payload.get("hasSendButton"),
        "body_sample": str(payload.get("bodySample") or "")[-500:],
        "stderr_tail": result.stderr[-1000:],
    }


def provider_probe_command(command_template: str) -> list[str]:
    command = render_command(command_template, "__probe__", Path("__probe_packet__.json"))
    filtered: list[str] = []
    skip_next = False
    for part in command:
        if skip_next:
            skip_next = False
            continue
        if part in {"--date", "--packet"}:
            skip_next = True
            continue
        filtered.append(part)
    filtered.append("probe")
    return filtered


def parse_probe_payload(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def provider_preflight_reason(*, provider: str, result: CommandResult, payload: dict[str, Any]) -> str | None:
    if result.exit_code != 0:
        return "probe_command_failed"
    if not payload:
        return "probe_payload_missing"
    body_sample = str(payload.get("bodySample") or "")
    lower_body = body_sample.lower()
    if "工作階段已過期" in body_sample or "請重新登入" in body_sample or "session has expired" in lower_body:
        return "session_expired"
    if payload.get("ok") is not True:
        return str(payload.get("reason") or "probe_not_ok")
    if payload.get("hasComposer") is not True:
        return "composer_missing"
    if provider == "gemini":
        url = str(payload.get("url") or "")
        if not re.search(r"gemini\.google\.com/app/[^/?#]+", url):
            return "gemini_conversation_id_missing"
    return None


def render_command(template: str, run_date: str, packet_path: Path) -> list[str]:
    rendered = template.format(date=run_date, packet=str(packet_path))
    return shlex.split(rendered)


def run_checked(command: list[str]) -> CommandResult:
    result = run_command(command)
    if result.exit_code != 0:
        raise RuntimeError(
            f"command failed exit_code={result.exit_code} command={mask_command(command)} "
            f"stdout={result.stdout[-1000:]} stderr={result.stderr[-1000:]}"
        )
    return result


def run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def write_host_summary(path: Path, status: dict[str, Any], external_summary: dict[str, Any] | None) -> None:
    provider_rows = []
    for provider in PROVIDERS:
        provider_state = status.get(provider) if isinstance(status.get(provider), dict) else {}
        provider_rows.append(
            {
                "provider": provider,
                "status": provider_state.get("status"),
                "raw_path": provider_state.get("raw_path"),
                "response_path": provider_state.get("response_path"),
                "notes": provider_state.get("notes", []),
            }
        )
    payload = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": status.get("run_date"),
        "status": status.get("status"),
        "host_runner_status_path": status.get("host_runner_status_path"),
        "external_review_summary_path": status.get("summary_path"),
        "providers": provider_rows,
        "valid_provider_count": (external_summary or {}).get("valid_provider_count"),
        "safety": (external_summary or {}).get("safety"),
        "promotion_boundary": (external_summary or {}).get("promotion_boundary"),
        "notes": status.get("notes", []),
    }
    write_json(path, payload)


def write_provider_events(
    *,
    artifacts_dir: Path,
    run_id: str,
    run_date: str,
    status: dict[str, Any],
    providers: tuple[str, ...],
    started_at: str,
) -> None:
    provider_states = {provider: status.get(provider, {}) for provider in providers}
    provider_statuses = {provider: state.get("status") for provider, state in provider_states.items() if isinstance(state, dict)}
    failed = [provider for provider, value in provider_statuses.items() if value == "FAILED"]
    ok = [provider for provider, value in provider_statuses.items() if value == "OK"]
    skipped = [provider for provider, value in provider_statuses.items() if value == "SKIPPED"]
    if failed and not ok:
        event_status = "failed"
        decision = "stop"
        next_action = "retry provider collection or inspect provider raw response"
    elif failed or skipped:
        event_status = "degraded"
        decision = "partial"
        next_action = "review missing provider before trusting disagreement summary"
    else:
        event_status = "ok"
        decision = "pass"
        next_action = None
    artifact_paths = []
    for state in provider_states.values():
        if isinstance(state, dict):
            artifact_paths.extend([state.get("raw_path"), state.get("response_path"), state.get("collect_status_path")])
    write_status_event(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        run_date=run_date,
        agent_id="ai_review_adapter",
        status=event_status,
        decision=decision,
        started_at=started_at,
        artifact_paths=[item for item in artifact_paths if item],
        failure_reason=", ".join(failed) if failed else None,
        next_action=next_action,
        metrics={
            "provider_statuses": provider_statuses,
            "valid_provider_count": len(ok),
            "invalid_providers": failed,
            "skipped_providers": skipped,
        },
    )


def write_disagreement_event(
    *,
    artifacts_dir: Path,
    run_id: str,
    run_date: str,
    external_summary_path: Path,
    external_summary: dict[str, Any],
    started_at: str,
) -> None:
    disagreements = external_summary.get("disagreements") if isinstance(external_summary.get("disagreements"), list) else []
    today_misses = external_summary.get("today_misses") if isinstance(external_summary.get("today_misses"), list) else []
    hypotheses = external_summary.get("research_hypotheses") if isinstance(external_summary.get("research_hypotheses"), list) else []
    safety = external_summary.get("safety") if isinstance(external_summary.get("safety"), dict) else {}
    needs_human_review = safety.get("needs_human_review") is True
    write_status_event(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        run_date=run_date,
        agent_id="disagreement_next_actions",
        status="warning" if needs_human_review else "ok",
        decision="needs_more_data" if needs_human_review else "pass",
        started_at=started_at,
        input_refs=[external_summary_path],
        artifact_paths=[external_summary_path],
        next_action="manual review required before using external review" if needs_human_review else None,
        metrics={
            "disagreement_count": len(disagreements),
            "today_miss_count": len(today_misses),
            "research_hypothesis_count": len(hypotheses),
            "needs_human_review": needs_human_review,
            "invalid_providers": safety.get("invalid_providers") or [],
        },
    )


def write_status_event(
    *,
    artifacts_dir: Path,
    run_id: str,
    run_date: str,
    agent_id: str,
    status: str,
    started_at: str,
    decision: str = "not_applicable",
    input_refs: list[str | Path] | None = None,
    artifact_paths: list[str | Path] | None = None,
    failure_reason: str | None = None,
    next_action: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    event = build_event(
        run_id=run_id,
        run_date=run_date,
        agent_id=agent_id,
        status=status,
        decision=decision,
        started_at=started_at,
        input_refs=[event_path_ref(item, artifacts_dir) for item in input_refs or []],
        artifact_paths=[event_path_ref(item, artifacts_dir) for item in artifact_paths or []],
        failure_reason=failure_reason,
        next_action=next_action,
        metrics=metrics,
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=PROJECT_ROOT / "docs" / "architecture" / "top10_harness_team.dashboard.json")


def event_path_ref(path: str | Path, artifacts_dir: Path) -> str:
    value = Path(path)
    try:
        return str(value.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        pass
    try:
        return str(value.resolve().relative_to(artifacts_dir.resolve()))
    except ValueError:
        return str(value)


def python_bin() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def run_ops_report(*, run_date: str, run_id: str, artifacts_dir: Path) -> None:
    command = [
        python_bin(),
        "scripts/send_top10_ops_report.py",
        "--run-date",
        run_date,
        "--run-id",
        run_id,
        "--artifacts-dir",
        str(artifacts_dir),
        "--send",
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"WARNING: ops report failed exit_code={completed.returncode}", file=sys.stderr)
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)


def run_fog_map_handoff(
    *,
    run_date: str,
    run_id: str,
    artifacts_dir: Path,
    skip_refresh: bool = False,
    skip_reason: str | None = None,
    skip_research_quota: bool = False,
) -> int:
    command = [
        python_bin(),
        "scripts/run_top10_fog_map_handoff.py",
        "--run-date",
        run_date,
        "--run-id",
        run_id,
        "--artifacts-dir",
        str(artifacts_dir),
    ]
    if skip_refresh:
        command.append("--skip-refresh")
    if skip_research_quota:
        command.append("--skip-research-quota")
    if skip_reason:
        command.extend(["--skip-reason", skip_reason])
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0:
        print(f"WARNING: fog map handoff failed exit_code={completed.returncode}", file=sys.stderr)
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)
    return completed.returncode


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mask_command(command: list[str]) -> list[str]:
    masked = list(command)
    for key in ("--message", "--delivery", "--presentation"):
        if key in masked:
            index = masked.index(key)
            if index + 1 < len(masked):
                masked[index + 1] = f"<{key[2:]} chars={len(masked[index + 1])}>"
    return masked


if __name__ == "__main__":
    raise SystemExit(main())
