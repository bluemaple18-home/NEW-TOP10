#!/usr/bin/env python3
"""檢查 NEW-TOP10 daily scheduler 是否只有 launchd owner。"""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
from pathlib import Path
from typing import Any, TypedDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAILY_LABEL = "com.new-top10.daily"
DAILY_CRON_MARKERS = ("scripts/run_daily.sh", "scripts/run_daily_publish.sh")
EXPECTED_DAILY_START_CALENDAR = tuple({"Weekday": weekday, "Hour": 17, "Minute": 30} for weekday in range(1, 6))


class OwnershipReport(TypedDict):
    status: str
    launchd_owner: bool
    cron_owner: bool
    message: str


def has_launchd_owner(launchd_text: str) -> bool:
    """判斷 injected launchd 輸出是否含正式 daily label。"""
    return DAILY_LABEL in launchd_text


def has_daily_cron(cron_text: str) -> bool:
    """判斷 injected crontab 內容是否含 TOP10 daily entry。"""
    entries = (line for line in cron_text.splitlines() if not line.lstrip().startswith("#"))
    return any(marker in entry for entry in entries for marker in DAILY_CRON_MARKERS)


def evaluate_ownership(launchd_text: str, cron_text: str) -> OwnershipReport:
    """依 launchd 與 cron 文本產生單一 owner 判定。"""
    launchd_owner = has_launchd_owner(launchd_text)
    cron_owner = has_daily_cron(cron_text)
    if launchd_owner and not cron_owner:
        return {
            "status": "GO",
            "launchd_owner": True,
            "cron_owner": False,
            "message": "launchd com.new-top10.daily 是唯一 daily owner。",
        }
    if cron_owner and not launchd_owner:
        return {
            "status": "WARNING",
            "launchd_owner": False,
            "cron_owner": True,
            "message": "僅偵測到 legacy cron；請遷移至 launchd com.new-top10.daily。",
        }
    if launchd_owner and cron_owner:
        return {
            "status": "NO-GO",
            "launchd_owner": True,
            "cron_owner": True,
            "message": "偵測到 launchd 與 legacy cron 同時擁有 daily，禁止雙重排程。",
        }
    return {
        "status": "NO-GO",
        "launchd_owner": False,
        "cron_owner": False,
        "message": "未偵測到 daily scheduler owner。",
    }


def read_command(command: list[str]) -> str:
    """以唯讀子程序讀取排程內容；查詢失敗視為無內容。"""
    try:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    except OSError:
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def verify_repo_owner() -> OwnershipReport:
    """CI 用靜態檢查：repo plist 必須指向正式 daily publish wrapper。"""
    plist = PROJECT_ROOT / "scripts" / "com.new-top10.daily.plist"
    errors: list[str] = []
    if not plist.exists():
        errors.append("repo daily plist missing")
    else:
        try:
            payload = plistlib.loads(plist.read_bytes())
        except (plistlib.InvalidFileException, OSError, ValueError) as exc:
            errors.append(f"repo daily plist invalid: {exc}")
            payload = {}
        errors.extend(validate_repo_daily_plist(payload))
    if not errors:
        return {
            "status": "GO",
            "launchd_owner": True,
            "cron_owner": False,
            "message": "repo daily plist 指向 scripts/run_daily_publish.sh，且只排週一至週五 17:30。",
        }
    return {
        "status": "NO-GO",
        "launchd_owner": False,
        "cron_owner": False,
        "message": "repo daily plist 不符合契約: " + "; ".join(errors),
    }


def validate_repo_daily_plist(payload: dict[str, Any]) -> list[str]:
    """驗證正式 daily launchd plist 的 repo 靜態契約。"""
    errors: list[str] = []
    arguments = payload.get("ProgramArguments")
    if not isinstance(arguments, list) or "scripts/run_daily_publish.sh" not in " ".join(map(str, arguments)):
        errors.append("must point to scripts/run_daily_publish.sh")

    intervals = payload.get("StartCalendarInterval")
    expected = list(EXPECTED_DAILY_START_CALENDAR)
    if not isinstance(intervals, list):
        errors.append("StartCalendarInterval must be an array for weekday-only scheduling")
        return errors
    actual = [
        {key: item.get(key) for key in ("Weekday", "Hour", "Minute")}
        for item in intervals
        if isinstance(item, dict)
    ]
    if actual != expected:
        errors.append(f"StartCalendarInterval must be Monday-Friday 17:30, got {actual}")
    if len(actual) != len(intervals):
        errors.append("StartCalendarInterval entries must all be dictionaries")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify NEW-TOP10 daily scheduler has one owner.")
    parser.add_argument("--repo-only", action="store_true", help="只檢查 repo plist，供 CI 使用")
    args = parser.parse_args()

    report = verify_repo_owner() if args.repo_only else evaluate_ownership(
        read_command(["launchctl", "print", f"gui/{os.getuid()}/{DAILY_LABEL}"]),
        read_command(["crontab", "-l"]),
    )
    print(f"SCHEDULER_OWNERSHIP_{report['status']}: {report['message']}")
    return 1 if report["status"] == "NO-GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
