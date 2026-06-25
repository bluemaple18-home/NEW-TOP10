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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight external review browser providers without sending packet.")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--provider", action="append", choices=PROVIDERS)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    providers = tuple(args.provider or PROVIDERS)
    checks = []
    for provider in providers:
        template = (
            "bash scripts/review_chatgpt_chrome.sh --date {date} --packet {packet}"
            if provider == "chatgpt"
            else "bash scripts/review_gemini_chrome.sh --date {date} --packet {packet}"
        )
        result = run_provider_preflight(provider=provider, command_template=template)
        checks.append({"provider": provider, **result})

    failed = [row for row in checks if row.get("status") != "OK"]
    payload: dict[str, Any] = {
        "schema_version": "external-review-provider-preflight.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not failed else "FAILED",
        "checks": checks,
        "summary": {
            "provider_count": len(checks),
            "ok_count": len(checks) - len(failed),
            "failed_count": len(failed),
            "failed_providers": [row["provider"] for row in failed],
        },
    }
    output = resolve_output(args.output, args.date)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


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
