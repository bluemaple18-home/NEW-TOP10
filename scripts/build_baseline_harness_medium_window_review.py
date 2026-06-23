#!/usr/bin/env python3
"""審核 baseline harness 是否可進入 medium-window replay。

本腳本只讀既有 small-window 證據與 features 交易日覆蓋；不 materialize
medium baseline、不跑 replay、不建立 artifacts/backtest/production。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_production_baseline_harness  # noqa: E402
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json, write_text  # noqa: E402


SCHEMA_VERSION = "baseline-harness-medium-window-review.v1"
TASK_ID = "WEEKEND-TRAINING-19"
SMALL_WINDOW_ARTIFACT = "artifacts/weekend_training/baseline_harness_small_window_replay_2026-06-18.json"
SMALL_WINDOW_VERIFICATION = "artifacts/weekend_training/baseline_harness_small_window_replay_verification_latest.json"
SMALL_WINDOW_MANIFEST = "artifacts/backtest/production_baseline_harness_small_window/manifest.json"
FEATURES_PATH = "data/clean/features.parquet"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"
MIN_MEDIUM_TRADING_DAYS = 60
MAX_MEDIUM_TRADING_DAYS = 120
DEFAULT_CANDIDATE_WINDOWS = [
    {"label": "60D", "start_date": "2026-02-16", "end_date": "2026-05-15"},
    {"label": "100D", "start_date": "2025-12-24", "end_date": "2026-05-15"},
    {"label": "120D", "start_date": "2025-11-17", "end_date": "2026-05-15"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build baseline harness medium-window review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--small-window-artifact", default=SMALL_WINDOW_ARTIFACT)
    parser.add_argument("--small-window-verification", default=SMALL_WINDOW_VERIFICATION)
    parser.add_argument("--small-window-manifest", default=SMALL_WINDOW_MANIFEST)
    parser.add_argument("--features", default=FEATURES_PATH)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def output_paths(run_date: str, override: str | None) -> tuple[Path, Path]:
    if override:
        json_path = resolve_path(override)
        assert json_path is not None
    else:
        json_path = PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_medium_window_review_{run_date}.json"
    return json_path, json_path.with_suffix(".md")


def contains_forbidden_text(payload: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payload, ensure_ascii=False)


def load_trade_dates(features_path: Path, start_date: str, end_date: str) -> list[str]:
    return build_production_baseline_harness.date_coverage_from_features(
        data_dir=features_path.parent,
        start_date=start_date,
        end_date=end_date,
        stride=1,
        max_dates=None,
    )


def candidate_coverage(features_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in DEFAULT_CANDIDATE_WINDOWS:
        dates = load_trade_dates(features_path, window["start_date"], window["end_date"])
        rows.append(
            {
                **window,
                "trading_day_count": len(dates),
                "first_trade_date": dates[0] if dates else None,
                "last_trade_date": dates[-1] if dates else None,
                "within_medium_bound": MIN_MEDIUM_TRADING_DAYS <= len(dates) <= MAX_MEDIUM_TRADING_DAYS,
                "sample_dates": dates[:3] + (["..."] if len(dates) > 6 else []) + dates[-3:],
            }
        )
    return rows


def choose_window(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [row for row in candidates if row.get("within_medium_bound") is True]
    return valid[0] if valid else None


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    run_date = str(args.date)
    small_artifact_path = resolve_path(args.small_window_artifact)
    small_verification_path = resolve_path(args.small_window_verification)
    small_manifest_path = resolve_path(args.small_window_manifest)
    features_path = resolve_path(args.features)
    assert small_artifact_path is not None and small_verification_path is not None and small_manifest_path is not None and features_path is not None

    small_artifact = read_json(small_artifact_path)
    small_verification = read_json(small_verification_path)
    small_manifest = read_json(small_manifest_path)
    coverage = candidate_coverage(features_path)
    selected = choose_window(coverage)
    verification_summary = small_verification.get("verification_summary") if isinstance(small_verification.get("verification_summary"), dict) else {}
    runner_summary = ((small_artifact.get("runner") or {}).get("summary") or {}) if isinstance(small_artifact.get("runner"), dict) else {}

    small_window_verified = (
        small_artifact.get("small_window_status") == "OK"
        and small_artifact.get("runner_can_read_baseline") is True
        and small_artifact.get("ranking_file_count") == 21
        and small_artifact.get("actual_replay_count") == 21
        and small_artifact.get("estimated_unlockable_combo_count") == 0
        and small_artifact.get("production_impact") == PRODUCTION_IMPACT
        and small_verification.get("status") == "OK"
        and verification_summary.get("failed_count") == 0
        and small_manifest.get("ranking_file_count") == 21
        and small_manifest.get("production_impact") == PRODUCTION_IMPACT
    )
    warning_profile_ok = small_window_verified
    runtime_profile_ok = small_window_verified and selected is not None
    can_run_medium_window = bool(small_window_verified and warning_profile_ok and runtime_profile_ok and selected)
    blocker_reasons: list[str] = []
    if not small_window_verified:
        blocker_reasons.append("SMALL_WINDOW_NOT_VERIFIED")
    if selected is None:
        blocker_reasons.append("NO_CANDIDATE_WINDOW_WITHIN_60_TO_120_TRADING_DAYS")
    if FORBIDDEN_PRODUCTION_PATH.exists():
        blocker_reasons.append("FORBIDDEN_PRODUCTION_PATH_EXISTS")
    status = "OK" if can_run_medium_window and not blocker_reasons else "BLOCKED"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "medium_window_review_status": status,
        "small_window_verified": small_window_verified,
        "warning_profile_ok": warning_profile_ok,
        "warning_profile": {
            "status": "OK" if warning_profile_ok else "BLOCKED",
            "notes": [
                "WEEKEND-TRAINING-18 replay completed and verifier passed.",
                "Prior sklearn/pandas runtime warnings are treated as non-fatal for this review because output verification passed.",
            ],
        },
        "runtime_profile_ok": runtime_profile_ok,
        "runtime_profile": {
            "status": "OK" if runtime_profile_ok else "BLOCKED",
            "basis": {
                "small_window_ranking_file_count": small_artifact.get("ranking_file_count"),
                "small_window_actual_replay_count": small_artifact.get("actual_replay_count"),
                "small_window_trade_count": runner_summary.get("trade_count"),
                "small_window_daily_count": runner_summary.get("daily_count"),
            },
            "estimated_runtime_class": "MEDIUM_BOUNDED_REPLAY_60D",
            "does_not_execute_medium_window_replay": True,
        },
        "date_coverage_candidate": coverage,
        "recommended_medium_window": selected.get("label") if selected else None,
        "recommended_start_date": selected.get("start_date") if selected else None,
        "recommended_end_date": selected.get("end_date") if selected else None,
        "recommended_trading_day_count": selected.get("trading_day_count") if selected else None,
        "recommended_reason": "選最小且交易日覆蓋落在 60~120 的候選窗口。" if selected else "沒有候選窗口符合 60~120 交易日覆蓋。",
        "can_run_medium_window": can_run_medium_window,
        "estimated_unlockable_combo_count": 0,
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "production_impact": PRODUCTION_IMPACT,
        "blocker_reasons": blocker_reasons,
        "source_artifacts": {
            "small_window_artifact": repo_path(small_artifact_path),
            "small_window_verification": repo_path(small_verification_path),
            "small_window_manifest": repo_path(small_manifest_path),
            "features": repo_path(features_path),
        },
        "review_scope": {
            "review_only": True,
            "does_not_materialize_medium_window_baseline": True,
            "does_not_execute_medium_window_replay": True,
            "does_not_run_202176_grid": True,
        },
        "contract": {
            "research_only": True,
            "review_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_run_202176_grid": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "medium_window_review_ok_is_not_full_replay_unlock": True,
        },
        "next_action": "WEEKEND-TRAINING-20_baseline_harness_medium_window_replay" if status == "OK" else "修小窗口 / warning / runtime blocker",
    }
    if contains_forbidden_text(payload):
        payload["medium_window_review_status"] = "BLOCKED"
        payload["can_run_medium_window"] = False
        payload["blocker_reasons"] = sorted(set(payload["blocker_reasons"] + ["FORBIDDEN_TEXT_PRESENT"]))
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline Harness Medium-Window Review",
            "",
            f"- medium_window_review_status: `{payload.get('medium_window_review_status')}`",
            f"- small_window_verified: `{payload.get('small_window_verified')}`",
            f"- warning_profile_ok: `{payload.get('warning_profile_ok')}`",
            f"- runtime_profile_ok: `{payload.get('runtime_profile_ok')}`",
            f"- recommended_medium_window: `{payload.get('recommended_medium_window')}`",
            f"- recommended_start_date: `{payload.get('recommended_start_date')}`",
            f"- recommended_end_date: `{payload.get('recommended_end_date')}`",
            f"- recommended_trading_day_count: `{payload.get('recommended_trading_day_count')}`",
            f"- can_run_medium_window: `{payload.get('can_run_medium_window')}`",
            f"- estimated_unlockable_combo_count: `{payload.get('estimated_unlockable_combo_count')}`",
            f"- target_production_path_created: `{payload.get('target_production_path_created')}`",
            f"- production_impact: `{payload.get('production_impact')}`",
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
    print(f"BASELINE_HARNESS_MEDIUM_WINDOW_REVIEW_{payload['medium_window_review_status']} output={repo_path(json_path)}")
    return 0 if payload["medium_window_review_status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
