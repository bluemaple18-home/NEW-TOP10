#!/usr/bin/env python3
"""驗證 daily publish wrapper 的 fail-loud 與 catch-up 日期契約。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_SOURCE = PROJECT_ROOT / "scripts" / "run_daily_publish.sh"
SCHEMA_VERSION = "daily-publish-wrapper-guards.v1"
CATCH_UP_DATE = "2000-01-03"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily publish wrapper guard behavior without live send")
    parser.add_argument("--output", default="artifacts/daily_publish_wrapper_guard_verification_latest.json")
    return parser.parse_args()


def write_text(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def build_fake_project(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    (root / "artifacts").mkdir()
    (root / "config").mkdir()
    (root / "logs").mkdir()
    (root / ".venv" / "bin").mkdir(parents=True)
    python_target = PROJECT_ROOT / ".venv" / "bin" / "python"
    write_text(
        root / ".venv" / "bin" / "python",
        f"""#!/usr/bin/env bash
exec "{python_target if python_target.exists() else Path(sys.executable)}" "$@"
""",
        executable=True,
    )
    shutil.copy2(WRAPPER_SOURCE, root / "scripts" / "run_daily_publish.sh")

    write_text(
        root / "config" / "automation.yaml",
        """
timezone: Asia/Taipei
notify:
  clawd_enabled: true
  clawd_dry_run: false
""".lstrip(),
    )
    write_text(
        root / "scripts" / "run_daily.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ "${{TOP10_RUN_DATE:-}}" != "{CATCH_UP_DATE}" ]; then
  echo "unexpected TOP10_RUN_DATE=${{TOP10_RUN_DATE:-}}" >&2
  exit 42
fi
mkdir -p "$PROJECT_DIR/artifacts" "$PROJECT_DIR/logs"
cat > "$PROJECT_DIR/artifacts/automation_status.json" <<JSON
{{
  "schema_version": "daily-run-status.v1",
  "mode": "daily",
  "status": "OK",
  "dry_run": false,
  "started_at": "2000-01-03T09:30:00+00:00",
  "run_date": "{CATCH_UP_DATE}",
  "finished_at": "2000-01-03T09:31:00+00:00",
  "metadata": {{
    "clawd_publish_message": "$PROJECT_DIR/artifacts/clawd_publish_message_{CATCH_UP_DATE}.md"
  }}
}}
JSON
printf '# Top10 {CATCH_UP_DATE}\\n' > "$PROJECT_DIR/artifacts/clawd_publish_message_{CATCH_UP_DATE}.md"
cat > "$PROJECT_DIR/artifacts/clawd_publish_payload_{CATCH_UP_DATE}.json" <<JSON
{{
  "ranking_date": "{CATCH_UP_DATE}",
  "delivery": {{"status": "READY_FOR_CLAWD", "channel": "fake", "to": "fake"}},
  "artifacts": {{"message": "$PROJECT_DIR/artifacts/clawd_publish_message_{CATCH_UP_DATE}.md"}}
}}
JSON
""",
        executable=True,
    )
    write_text(
        root / "scripts" / "send_clawd_publish_message.py",
        f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[1]
date = os.environ.get("TOP10_RUN_DATE", "{CATCH_UP_DATE}")
exit_code = int(os.environ.get("FAKE_SEND_EXIT", "0"))
args_path = project / "artifacts" / "fake_send_args.json"
args_path.write_text(json.dumps({{"args": sys.argv[1:]}}, ensure_ascii=False, indent=2), encoding="utf-8")
status = "OK" if exit_code == 0 else "FAILED"
(project / "artifacts" / f"clawd_send_status_{{date}}.json").write_text(
    json.dumps(
        {{
            "schema_version": "clawd-send-status.v1",
            "message_date": date,
            "status": status,
            "dry_run": False,
            "send_attempted": True,
            "exit_code": exit_code,
        }},
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"FAKE_CLAWD_SEND_STATUS status={{status}} exit_code={{exit_code}}")
raise SystemExit(exit_code)
""",
        executable=True,
    )


def run_wrapper_case(name: str, send_exit: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"top10_publish_guard_{name}_") as temp:
        project = Path(temp)
        build_fake_project(project)
        env = os.environ.copy()
        env["TOP10_RUN_DATE"] = CATCH_UP_DATE
        env["FAKE_SEND_EXIT"] = str(send_exit)
        completed = subprocess.run(
            ["bash", str(project / "scripts" / "run_daily_publish.sh")],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        args_path = project / "artifacts" / "fake_send_args.json"
        send_args = json.loads(args_path.read_text(encoding="utf-8"))["args"] if args_path.exists() else []
        status_path = project / "artifacts" / "automation_status.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        publish_logs = "\n".join(path.read_text(encoding="utf-8") for path in sorted((project / "logs").glob("daily_publish_*.log")))
        expected_exit = send_exit
        checks = [
            {"name": "wrapper_exit_code", "ok": completed.returncode == expected_exit, "value": completed.returncode},
            {"name": "run_date_preserved", "ok": status.get("run_date") == CATCH_UP_DATE, "value": status.get("run_date")},
            {"name": "stale_send_requires_flag", "ok": "--allow-stale-send" in send_args, "value": send_args},
        ]
        return {
            "name": name,
            "status": "OK" if all(check["ok"] for check in checks) else "FAILED",
            "send_exit": send_exit,
            "wrapper_exit": completed.returncode,
            "checks": checks,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "publish_logs": publish_logs,
        }


def main() -> int:
    args = parse_args()
    cases = [
        run_wrapper_case("send_failure_fails_publish", send_exit=7),
        run_wrapper_case("catch_up_date_reaches_sender", send_exit=0),
    ]
    failed = [case for case in cases if case["status"] != "OK"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "cases": cases,
        "summary": {"case_count": len(cases), "failed_count": len(failed)},
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failed_count": len(failed), "output": str(output)}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
