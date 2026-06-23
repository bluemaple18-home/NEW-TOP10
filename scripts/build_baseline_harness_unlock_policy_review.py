#!/usr/bin/env python3
"""建立 baseline harness 自跑 unlock policy review。

這裡只把已通過的 medium-window replay 轉成 host runner 可執行的 allowlist；
不執行 replay、不建立 production、不解鎖全量。
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, now_utc, repo_path, resolve_path, write_json, write_text


SCHEMA_VERSION = "baseline-harness-unlock-policy-review.v1"
TASK_ID = "WEEKEND-TRAINING-21"
MEDIUM_REPLAY_ARTIFACT = "artifacts/weekend_training/baseline_harness_medium_window_replay_2026-06-18.json"
MEDIUM_REPLAY_VERIFICATION = "artifacts/weekend_training/baseline_harness_medium_window_replay_verification_latest.json"
TARGET_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_medium_window"
FORBIDDEN_PRODUCTION_PATH = Path("artifacts/backtest/production")
FORBIDDEN_TEXT = "PROMOTION_READY"
ACTION_ID = "baseline_harness_medium_window_replay_100D"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build baseline harness unlock policy review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--medium-replay-artifact", default=MEDIUM_REPLAY_ARTIFACT)
    parser.add_argument("--medium-replay-verification", default=MEDIUM_REPLAY_VERIFICATION)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def output_paths(run_date: str, override: str | None) -> tuple[Path, Path]:
    if override:
        json_path = resolve_path(override)
        assert json_path is not None
    else:
        json_path = resolve_path(f"artifacts/weekend_training/baseline_harness_unlock_policy_review_{run_date}.json")
        assert json_path is not None
    return json_path, json_path.with_suffix(".md")


def has_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifact_path = resolve_path(args.medium_replay_artifact)
    verification_path = resolve_path(args.medium_replay_verification)
    production_path = resolve_path(FORBIDDEN_PRODUCTION_PATH)
    assert artifact_path is not None and verification_path is not None and production_path is not None

    replay = read_json(artifact_path)
    verification = read_json(verification_path)
    window = replay.get("window") if isinstance(replay.get("window"), dict) else {}
    verification_summary = verification.get("verification_summary") if isinstance(verification.get("verification_summary"), dict) else {}
    blockers: list[str] = []
    if replay.get("medium_window_status") != "OK":
        blockers.append("MEDIUM_REPLAY_NOT_OK")
    if verification.get("status") != "OK" or verification_summary.get("failed_count") != 0:
        blockers.append("MEDIUM_REPLAY_VERIFICATION_NOT_OK")
    if replay.get("input_baseline_path") != TARGET_BASELINE_PATH:
        blockers.append("BASELINE_PATH_NOT_ALLOWED")
    if window.get("start") != "2025-12-24" or window.get("end") != "2026-05-15":
        blockers.append("WINDOW_NOT_ALLOWED")
    if int(replay.get("ranking_file_count") or 0) < 60 or int(replay.get("actual_replay_count") or 0) < 60:
        blockers.append("MEDIUM_REPLAY_TOO_SMALL")
    if replay.get("estimated_unlockable_combo_count") != 0:
        blockers.append("UNLOCKABLE_COMBO_COUNT_NOT_ZERO")
    if replay.get("production_impact") != PRODUCTION_IMPACT:
        blockers.append("PRODUCTION_IMPACT_NOT_SAFE")
    if production_path.exists() or replay.get("target_production_path_created") is not False:
        blockers.append("FORBIDDEN_PRODUCTION_PATH_EXISTS")
    if has_forbidden_text(replay):
        blockers.append("FORBIDDEN_TEXT_PRESENT")

    policy_status = "OK" if not blockers else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "task_id": TASK_ID,
        "policy_review_status": policy_status,
        "controlled_self_run_enabled": policy_status == "OK",
        "source_artifacts": {
            "medium_replay_artifact": repo_path(artifact_path),
            "medium_replay_verification": repo_path(verification_path),
        },
        "allowlist": [
            {
                "action_id": ACTION_ID,
                "description": "只跑已驗證 100D medium-window baseline harness bounded replay。",
                "runner": "scripts/run_baseline_harness_medium_window_replay.py",
                "verifier": "scripts/verify_baseline_harness_medium_window_replay.py",
                "target_baseline_path": TARGET_BASELINE_PATH,
                "start_date": "2025-12-24",
                "end_date": "2026-05-15",
                "min_ranking_file_count": 60,
                "max_ranking_file_count": 120,
                "max_replay_grid_count": 1,
                "estimated_unlockable_combo_count": 0,
                "command_template": [".venv/bin/python", "scripts/run_baseline_harness_medium_window_replay.py", "--date", "{run_date}"],
                "verify_command_template": [".venv/bin/python", "scripts/verify_baseline_harness_medium_window_replay.py", "--date", "{run_date}"],
            }
        ],
        "denylist": [
            "artifacts/backtest/production",
            "202176_grid_replay",
            "full_universe_replay",
            "window_auto_expand",
            "model_training",
            "models/latest_lgbm.pkl_write",
            "production_ranking_write",
            "clawd_live_send",
        ],
        "host_runner_policy": {
            "lockfile": "artifacts/host_runner/baseline_harness.lock",
            "timeout_seconds": 1800,
            "require_policy_ok": True,
            "require_verifier_after_runner": True,
            "write_status_and_summary": True,
            "status_dir_template": "artifacts/host_runner/{run_date}",
            "production_guard_path": "artifacts/backtest/production",
        },
        "safety": {
            "target_production_path_created": production_path.exists(),
            "production_impact": PRODUCTION_IMPACT,
            "estimated_unlockable_combo_count": 0,
            "medium_replay_ok_is_not_full_replay_unlock": True,
        },
        "blocker_reasons": blockers,
        "next_action": "baseline_harness_host_runner_self_run" if policy_status == "OK" else "修 medium replay / policy blocker",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline Harness Unlock Policy Review",
            "",
            f"- policy_review_status: `{payload.get('policy_review_status')}`",
            f"- controlled_self_run_enabled: `{payload.get('controlled_self_run_enabled')}`",
            f"- allowlist_count: `{len(payload.get('allowlist') or [])}`",
            f"- target_production_path_created: `{(payload.get('safety') or {}).get('target_production_path_created')}`",
            f"- estimated_unlockable_combo_count: `{(payload.get('safety') or {}).get('estimated_unlockable_combo_count')}`",
            f"- production_impact: `{(payload.get('safety') or {}).get('production_impact')}`",
            f"- next_action: `{payload.get('next_action')}`",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    json_path, md_path = output_paths(str(args.date), args.output)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(f"BASELINE_HARNESS_UNLOCK_POLICY_REVIEW_{payload['policy_review_status']} output={repo_path(json_path)}")
    return 0 if payload["policy_review_status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
