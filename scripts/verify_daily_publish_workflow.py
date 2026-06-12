#!/usr/bin/env python3
"""驗證 daily publish 工作流是否可安全送出。

這支腳本不抓資料、不送 Clawd，只檢查工作流契約：
- 排程入口指向 run_daily_publish.sh
- 本次 daily status / ranking / report / payload / message 日期一致
- 需要正式送出時，Clawd send status 必須 OK
- stale live send guard 必須存在
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - 讓錯誤訊息更明確
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify NEW-TOP10 daily publish workflow contract.")
    parser.add_argument("--date", default=None, help="要檢查的 ranking / publish 日期，預設讀 automation_status.run_date")
    parser.add_argument("--require-send", action="store_true", help="要求 clawd_send_status_YYYY-MM-DD.json 已正式送出 OK")
    parser.add_argument("--check-launchd", action="store_true", help="額外檢查本機 launchd com.new-top10.daily 是否載入")
    parser.add_argument("--output", default=None, help="輸出 JSON 檢查報告路徑")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    check_static_workflow(errors, warnings, details)
    if args.check_launchd:
        check_launchd(errors, warnings, details)

    status = read_json(ARTIFACTS_DIR / "automation_status.json", errors)
    run_date = args.date or status.get("run_date")
    if not run_date:
        errors.append("missing run_date: pass --date or provide artifacts/automation_status.json")
        run_date = datetime.now().date().isoformat()
    details["run_date"] = run_date

    check_daily_artifacts(run_date, status, errors, warnings, details)
    check_publish_artifacts(run_date, args.require_send, errors, warnings, details)

    report = {
        "schema_version": "daily-publish-workflow-verification.v1",
        "status": "OK" if not errors else "FAILED",
        "run_date": run_date,
        "require_send": args.require_send,
        "check_launchd": args.check_launchd,
        "details": details,
        "warnings": warnings,
        "errors": errors,
    }

    output = Path(args.output) if args.output else ARTIFACTS_DIR / f"daily_publish_workflow_verification_{run_date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DAILY_PUBLISH_WORKFLOW_{report['status']} output={output}")
    if warnings:
        print(f"warnings={len(warnings)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    return 0


def check_static_workflow(errors: list[str], warnings: list[str], details: dict[str, Any]) -> None:
    plist = PROJECT_ROOT / "scripts" / "com.new-top10.daily.plist"
    run_daily_publish = PROJECT_ROOT / "scripts" / "run_daily_publish.sh"
    run_daily = PROJECT_ROOT / "scripts" / "run_daily.sh"
    sender = PROJECT_ROOT / "scripts" / "send_clawd_publish_message.py"
    wrapper_guard = PROJECT_ROOT / "scripts" / "verify_daily_publish_wrapper_guards.py"

    details["static"] = {
        "repo_plist": str(plist),
        "run_daily_publish": str(run_daily_publish),
        "run_daily": str(run_daily),
        "sender": str(sender),
        "wrapper_guard": str(wrapper_guard),
    }

    if not plist.exists():
        errors.append("repo daily plist missing")
    elif "scripts/run_daily_publish.sh" not in plist.read_text(encoding="utf-8"):
        errors.append("repo daily plist must point to scripts/run_daily_publish.sh")

    if not run_daily_publish.exists():
        errors.append("scripts/run_daily_publish.sh missing")
    else:
        text = run_daily_publish.read_text(encoding="utf-8")
        if "scripts/run_daily.sh" not in text:
            errors.append("run_daily_publish.sh must call scripts/run_daily.sh")
        if "automation_status.json" not in text or "clawd_publish_message" not in text:
            errors.append("run_daily_publish.sh must gate on automation_status metadata.clawd_publish_message")
        if "allow-stale-send" not in text:
            errors.append("run_daily_publish.sh must only allow stale send through explicit catch-up flag")
        if "clawd_publish_message_*.md" in text or "latest" in text.lower():
            errors.append("run_daily_publish.sh must not use latest-message fallback")
        if "export TOP10_RUN_DATE" not in text:
            errors.append("run_daily_publish.sh must export TOP10_RUN_DATE before invoking daily")
        if 'exit "$SEND_EXIT_CODE"' not in text:
            errors.append("run_daily_publish.sh must fail non-zero when Clawd live send fails")

    if not run_daily.exists():
        errors.append("scripts/run_daily.sh missing")
    else:
        text = run_daily.read_text(encoding="utf-8")
        if ".venv/bin/python" not in text:
            errors.append("run_daily.sh must prefer repo .venv python for launchd stability")
        if "UV_BIN" not in text or "run --with-requirements requirements.txt python" not in text:
            warnings.append("run_daily.sh has no uv fallback; this may be intentional but should be explicit")
        if "--run-date" not in text:
            errors.append("run_daily.sh must pass TOP10_RUN_DATE as explicit --run-date to run_automation")

    if not sender.exists():
        errors.append("scripts/send_clawd_publish_message.py missing")
    else:
        text = sender.read_text(encoding="utf-8")
        if "--allow-stale-send" not in text or "stale Clawd message blocked" not in text:
            errors.append("send_clawd_publish_message.py must block stale live send by default")

    runner = PROJECT_ROOT / "scripts" / "run_automation.py"
    if not runner.exists():
        errors.append("scripts/run_automation.py missing")
    else:
        text = runner.read_text(encoding="utf-8")
        if "--run-date" not in text or "run_date_source" not in text:
            errors.append("run_automation.py must support explicit --run-date catch-up contract")

    if not wrapper_guard.exists():
        errors.append("scripts/verify_daily_publish_wrapper_guards.py missing")


def check_launchd(errors: list[str], warnings: list[str], details: dict[str, Any]) -> None:
    command = ["launchctl", "list", "com.new-top10.daily"]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    details["launchd"] = {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        errors.append("launchd job com.new-top10.daily is not loaded or cannot be inspected")
        return
    expected_script = str(PROJECT_ROOT / "scripts" / "run_daily_publish.sh")
    if expected_script not in completed.stdout and "scripts/run_daily_publish.sh" not in completed.stdout:
        errors.append("launchd com.new-top10.daily must point to scripts/run_daily_publish.sh")
    if '"LastExitStatus" = 0' not in completed.stdout and '"LastExitStatus" = 512' in completed.stdout:
        warnings.append("launchd LastExitStatus still reflects the previous failed scheduled run; rerun after next schedule to confirm reset")


def check_daily_artifacts(
    run_date: str,
    status: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    details["automation_status"] = {
        "path": str(ARTIFACTS_DIR / "automation_status.json"),
        "status": status.get("status"),
        "run_date": status.get("run_date"),
    }
    if status.get("status") != "OK":
        errors.append(f"automation_status.status must be OK, got {status.get('status')}")
    if status.get("run_date") != run_date:
        errors.append(f"automation_status.run_date mismatch: {status.get('run_date')} != {run_date}")

    metadata = status.get("metadata") if isinstance(status.get("metadata"), dict) else {}
    required_metadata = {
        "ranking_artifact": ARTIFACTS_DIR / f"ranking_{run_date}.csv",
        "daily_report_artifact": ARTIFACTS_DIR / f"daily_report_{run_date}.json",
        "clawd_publish_payload": ARTIFACTS_DIR / f"clawd_publish_payload_{run_date}.json",
        "clawd_publish_message": ARTIFACTS_DIR / f"clawd_publish_message_{run_date}.md",
    }
    details["metadata"] = {}
    for key, expected_path in required_metadata.items():
        actual = metadata.get(key)
        details["metadata"][key] = actual
        if not actual:
            errors.append(f"automation_status.metadata.{key} missing")
            continue
        actual_path = Path(actual)
        if actual_path.name != expected_path.name:
            errors.append(f"automation_status.metadata.{key} must point to {expected_path.name}, got {actual_path.name}")
        if not actual_path.exists():
            errors.append(f"artifact missing on disk: {actual_path}")

    for path in required_metadata.values():
        if not path.exists():
            errors.append(f"expected artifact missing: {path}")


def check_publish_artifacts(
    run_date: str,
    require_send: bool,
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    payload_path = ARTIFACTS_DIR / f"clawd_publish_payload_{run_date}.json"
    message_path = ARTIFACTS_DIR / f"clawd_publish_message_{run_date}.md"
    send_path = ARTIFACTS_DIR / f"clawd_send_status_{run_date}.json"

    payload = read_json(payload_path, errors) if payload_path.exists() else {}
    delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    details["payload"] = {
        "path": str(payload_path),
        "ranking_date": payload.get("ranking_date"),
        "delivery_status": delivery.get("status"),
        "channel": delivery.get("channel"),
        "to": delivery.get("to"),
    }
    if payload and payload.get("ranking_date") != run_date:
        errors.append(f"payload ranking_date mismatch: {payload.get('ranking_date')} != {run_date}")
    if payload and delivery.get("status") != "READY_FOR_CLAWD":
        errors.append(f"payload delivery.status must be READY_FOR_CLAWD, got {delivery.get('status')}")

    if message_path.exists():
        first_line = message_path.read_text(encoding="utf-8").splitlines()[0]
        details["message"] = {"path": str(message_path), "first_line": first_line}
        if run_date not in first_line:
            errors.append(f"message first line must include run_date {run_date}, got {first_line}")
    else:
        errors.append(f"message artifact missing: {message_path}")

    if send_path.exists():
        send_status = read_json(send_path, errors)
        details["send_status"] = {
            "path": str(send_path),
            "status": send_status.get("status"),
            "message_date": send_status.get("message_date"),
            "dry_run": send_status.get("dry_run"),
            "send_attempted": send_status.get("send_attempted"),
            "target": send_status.get("target"),
        }
        if send_status.get("message_date") != run_date:
            errors.append(f"send_status.message_date mismatch: {send_status.get('message_date')} != {run_date}")
        if require_send:
            if send_status.get("status") != "OK":
                errors.append(f"send_status.status must be OK, got {send_status.get('status')}")
            if send_status.get("dry_run") is not False:
                errors.append("send_status.dry_run must be false for live publish verification")
            if send_status.get("send_attempted") is not True:
                errors.append("send_status.send_attempted must be true")
    elif require_send:
        errors.append(f"send status missing: {send_path}")
    else:
        warnings.append(f"send status not checked because --require-send is false: {send_path}")


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"JSON missing: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
