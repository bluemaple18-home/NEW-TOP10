#!/usr/bin/env python3
"""驗證 PM research harness loop 的本機契約與 launchd plist。"""

from __future__ import annotations

import json
import plistlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def exists(rel: str) -> bool:
    return (PROJECT_ROOT / rel).exists()


def executable_entry() -> bool:
    text = (PROJECT_ROOT / "scripts/run_pm_research_harness_loop.sh").read_text(encoding="utf-8")
    return "run_pm_research_harness_loop.py" in text and "--send-cards" in text


def wrapper_safety_defaults_ok() -> bool:
    text = (PROJECT_ROOT / "scripts/run_pm_research_harness_loop.sh").read_text(encoding="utf-8")
    required = [
        'ENABLED="${TOP10_PM_RESEARCH_ENABLED:-0}"',
        'SEND_CARDS="${TOP10_PM_RESEARCH_SEND_CARDS:-0}"',
        'DRY_RUN_SEND="${TOP10_PM_RESEARCH_DRY_RUN_SEND:-1}"',
        'MAX_CONTINUATION_RUNS="${TOP10_PM_RESEARCH_MAX_CONTINUATION_RUNS:-8}"',
        'MIN_QUEUE_DEPTH="${TOP10_PM_RESEARCH_MIN_QUEUE_DEPTH:-12}"',
        'DISCOVERY_MAX_TOPICS="${TOP10_PM_RESEARCH_DISCOVERY_MAX_TOPICS:-30}"',
        "reason=disabled TOP10_PM_RESEARCH_ENABLED=",
        "fog research worker active",
    ]
    return all(item in text for item in required)


def plist_ok() -> bool:
    path = PROJECT_ROOT / "scripts/com.new-top10.pm-research-harness.plist"
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    env = payload.get("EnvironmentVariables") if isinstance(payload.get("EnvironmentVariables"), dict) else {}
    return (
        payload.get("Label") == "com.new-top10.pm-research-harness"
        and "__PROJECT_DIR__/scripts/run_pm_research_harness_loop.sh" in payload.get("ProgramArguments", [])
        and env.get("TOP10_PM_RESEARCH_ENABLED") == "1"
        and env.get("TOP10_PM_RESEARCH_SEND_CARDS") == "0"
        and env.get("TOP10_PM_RESEARCH_DRY_RUN_SEND") == "1"
        and env.get("TOP10_PM_RESEARCH_MAX_CONTINUATION_RUNS") == "8"
        and env.get("TOP10_PM_RESEARCH_MIN_QUEUE_DEPTH") == "12"
        and env.get("TOP10_PM_RESEARCH_DISCOVERY_MAX_TOPICS") == "30"
        and payload.get("StartInterval") == 900
        and payload.get("RunAtLoad") is True
    )


def setup_includes_job() -> bool:
    text = (PROJECT_ROOT / "scripts/setup_launchd.sh").read_text(encoding="utf-8")
    return (
        "com.new-top10.pm-research-harness.plist" in text
        and "PM approval research harness loop" in text
        and "launchd 明確啟用研究" in text
        and "Discord 送卡 dry-run" in text
    )


def domain_guard_ok() -> bool:
    loop_text = (PROJECT_ROOT / "scripts/run_pm_research_harness_loop.py").read_text(encoding="utf-8")
    core_text = (PROJECT_ROOT / "integrations/openclaw-top10-pm-review/core.js").read_text(encoding="utf-8")
    plugin_text = (PROJECT_ROOT / "integrations/openclaw-top10-pm-review/index.js").read_text(encoding="utf-8")
    queue_text = (PROJECT_ROOT / "scripts/build_pm_approved_work_queue.py").read_text(encoding="utf-8")
    loop_required = [
        'PROJECT_DOMAIN = "TOP10_STOCK"',
        "is_top10_stock_run_dir",
        "is_top10_stock_decision",
        "ai vibe radar",
        "ai-core",
        "artifacts/autonomous_research/",
        "artifacts/model_experiments/",
    ]
    core_required = [
        'PROJECT_DOMAIN = "TOP10_STOCK"',
        "validateProjectDomain",
        "project_domain: PROJECT_DOMAIN",
    ]
    plugin_required = [
        "assertTop10StockCardsPayload",
        "unsupported cards project_domain",
        "unsupported card project_domain",
        "project_domain: PROJECT_DOMAIN",
    ]
    queue_required = [
        'PROJECT_DOMAIN = "TOP10_STOCK"',
        'state.get("project_domain") != PROJECT_DOMAIN',
        '"status": "SKIPPED"',
        '"requires_project_domain": PROJECT_DOMAIN',
    ]
    return (
        all(item in loop_text for item in loop_required)
        and all(item in core_text for item in core_required)
        and all(item in plugin_text for item in plugin_required)
        and all(item in queue_text for item in queue_required)
    )


def loop_contract_ok() -> bool:
    text = (PROJECT_ROOT / "scripts/run_pm_research_harness_loop.py").read_text(encoding="utf-8")
    required = [
        '"requires_explicit_pm_approval": True',
        '"launchd_explicitly_enables_research": True',
        '"dry_run_send_does_not_skip_state_update": True',
        '"max_no_approval_continuation_runs": args.max_continuation_runs',
        '"auto_discovers_topics_when_queue_low": True',
        '"revisits_rejected_topics_when_queue_low": True',
        "discover_research_topics",
        "top_up_research_queue_from_registry",
        "--include-rejected",
        "queue_depth_before",
        "queue_depth_after_discovery",
        "queue_depth_after_run",
        "queue_top_up_after_run_count",
        "consecutive_no_approval_runs",
        "if pending_approvals or topic_runs > 0:",
    ]
    return all(item in text for item in required)


def fog_worker_boundary_ok() -> bool:
    text = (PROJECT_ROOT / "scripts/run_fog_research_worker.sh").read_text(encoding="utf-8")
    required = [
        'PM_LOCK_DIR="$LOG_DIR/pm_research_harness_loop.lock"',
        "PM research harness active",
    ]
    return all(item in text for item in required)


def main() -> int:
    checks = {
        "python_loop_exists": exists("scripts/run_pm_research_harness_loop.py"),
        "shell_wrapper_exists": exists("scripts/run_pm_research_harness_loop.sh"),
        "plist_exists": exists("scripts/com.new-top10.pm-research-harness.plist"),
        "shell_calls_python_loop_and_send_cards": executable_entry(),
        "wrapper_safety_defaults": wrapper_safety_defaults_ok(),
        "plist_contract": plist_ok(),
        "setup_launchd_includes_job": setup_includes_job(),
        "top10_stock_domain_guard": domain_guard_ok(),
        "loop_contract": loop_contract_ok(),
        "fog_worker_boundary": fog_worker_boundary_ok(),
    }
    result = {"status": "OK" if all(checks.values()) else "FAILED", "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
