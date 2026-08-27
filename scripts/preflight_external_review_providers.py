#!/usr/bin/env python3
"""送件前檢查外部 review provider 瀏覽器狀態。

只跑 provider probe，不送 review packet。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_external_review_host_runner import run_provider_preflight  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("chatgpt", "gemini")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight external review browser providers without sending packet.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--provider", action="append", choices=PROVIDERS)
    parser.add_argument("--output", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    providers = tuple(args.provider or PROVIDERS)
    checks = []
    for provider in providers:
        template = (
            "bash scripts/review_chatgpt_chrome.sh --date {date} --packet {packet}"
            if provider == "chatgpt"
            else "bash scripts/review_gemini_chrome.sh --date {date} --packet {packet}"
        )
        result = run_provider_preflight(provider=provider, command_template=template)
        checks.append(normalize_provider_check(provider, result))

    blocked = [row for row in checks if row.get("status") != "PASS"]
    payload: dict[str, Any] = {
        "schema_version": "external-review-provider-preflight.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "mode": "probe_only",
        "review_packet_sent": False,
        "status": "PASS" if not blocked else "BLOCKED",
        "checks": checks,
        "summary": {
            "provider_count": len(checks),
            "pass_count": len(checks) - len(blocked),
            "blocked_count": len(blocked),
            "blocked_providers": [row["provider"] for row in blocked],
        },
    }
    output = resolve_output(args.output, args.date)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


def normalize_provider_check(provider: str, result: dict[str, Any]) -> dict[str, Any]:
    """將 adapter 結果收斂為可供排程 fail-closed 判斷的 provider receipt。"""

    reason = result.get("reason")
    status = "PASS" if result.get("status") == "OK" else "BLOCKED"
    blocker_code = None if status == "PASS" else str(reason or "probe_not_ready")
    return {
        "provider": provider,
        "status": status,
        "provider_status": result.get("status"),
        "mode": "probe_only",
        "review_packet_sent": False,
        "blocker": None
        if blocker_code is None
        else {
            "code": blocker_code,
            "kind": classify_blocker(blocker_code, str(result.get("stderr_tail") or "")),
            "manual_action_required": blocker_code in {"session_expired", "composer_missing"},
        },
        "evidence": {
            "command": result.get("command"),
            "exit_code": result.get("exit_code"),
            "url": result.get("url"),
            "title": result.get("title"),
            "has_composer": result.get("has_composer"),
            "has_send_button": result.get("has_send_button"),
            "stderr_tail": str(result.get("stderr_tail") or "")[-1000:],
        },
    }


def classify_blocker(code: str, stderr_tail: str) -> str:
    """保留 authority/runtime 與 provider readiness 的差異，避免泛化為 crash。"""

    lowered = stderr_tail.lower()
    if "not authorized" in lowered or "not permitted" in lowered:
        return "runtime_authority"
    if "application isn't running" in lowered or "application is not running" in lowered:
        return "browser_runtime"
    if code == "session_expired":
        return "provider_session"
    if code in {"composer_missing", "gemini_conversation_id_missing"}:
        return "provider_readiness"
    if code == "probe_payload_missing":
        return "probe_protocol"
    return "provider_runtime"


def resolve_output(value: str | None, date_text: str) -> Path:
    if value:
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / "artifacts" / "external_review" / date_text / f"provider_preflight_{date_text}.json"


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
