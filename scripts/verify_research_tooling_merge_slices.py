#!/usr/bin/env python3
"""驗證 research tooling dirty tree 不被半套 stage。

這支 verifier 只讀 git 狀態與檔案存在狀態，不修改工作樹。
用途是把 2026-06-08 merge-risk review 的拆線規則變成機器可查。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


SLICE_GROUPS: dict[str, dict[str, Any]] = {
    "production_ranking_overlay": {
        "files": [
            "app/agent_b_ranking.py",
            "config/signals.yaml",
            "scripts/verify_production_ranking_overlay.py",
            "docs/tasks/2026-06-04_RANKING-QUALITY-11_promote_k9_with_baseline_k8_controls.md",
        ],
        "kind": "promotion_review_required",
        "note": "正式 Top10 overlay 升級包，不能混進 research tooling commit。",
    },
    "factor_registry": {
        "files": [
            "app/modeling/factor_registry.py",
            "app/modeling/__init__.py",
            "app/modeling/feature_contract.py",
            "scripts/build_factor_run_manifest.py",
            "scripts/verify_model_foundation.py",
        ],
        "kind": "model_contract",
        "note": "模型因子合約與 leakage guard，必須獨立 review。",
    },
    "daily_shadow_monitor": {
        "files": [
            "config/automation.yaml",
            "scripts/run_automation.py",
            "scripts/build_gross55_daily_shadow_monitor.py",
            "scripts/build_gross55_daily_shadow_monitor_batch.py",
            "scripts/build_capital_entry_quality_daily_shadow_monitor.py",
            "scripts/build_capital_entry_quality_daily_shadow_monitor_batch.py",
            "scripts/build_shadow_historical_evidence_report.py",
            "scripts/build_daily_shadow_status_report.py",
            "scripts/verify_gross55_daily_shadow_monitor.py",
            "scripts/verify_gross55_daily_shadow_monitor_batch.py",
            "scripts/verify_capital_entry_quality_daily_shadow_monitor.py",
            "scripts/verify_capital_entry_quality_daily_shadow_monitor_batch.py",
            "scripts/verify_shadow_historical_evidence_report.py",
            "scripts/verify_daily_shadow_status_report.py",
        ],
        "kind": "automation_shadow_monitor",
        "note": "daily automation shadow monitor 與其產物/verifier 必須成套。",
    },
    "portfolio_replay_exit_rule": {
        "files": [
            "scripts/run_backtest_replay.py",
            "scripts/run_portfolio_replay.py",
            "scripts/verify_portfolio_replay.py",
            "scripts/verify_backtest_replay.py",
            "scripts/build_high_choppy_context_overlay.py",
            "scripts/research_regime_family_training_candidates.py",
        ],
        "kind": "replay_tooling",
        "note": "portfolio replay / exit-rule / regime exposure tooling 必須成套。",
    },
    "clawd_timeout": {
        "files": [
            "scripts/report_stock_status.sh",
        ],
        "kind": "ops_hardening",
        "note": "Clawd timeout wrapper 可獨立收。",
    },
}


def git_names(args: list[str]) -> set[str]:
    completed = subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def existing(files: list[str]) -> list[str]:
    return [path for path in files if (PROJECT_ROOT / path).exists()]


def missing(files: list[str]) -> list[str]:
    return [path for path in files if not (PROJECT_ROOT / path).exists()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify research tooling merge slices")
    parser.add_argument("--staged", action="store_true", help="檢查 staged set 是否半套；預設檢查 dirty/untracked workspace")
    parser.add_argument("--self-test", action="store_true", help="執行 verifier 自測，不讀 git 狀態")
    parser.add_argument(
        "--allow-multiple-slices",
        action="store_true",
        help="staged 模式允許一次收多個完整 slice；預設一次只能收一個 slice",
    )
    return parser.parse_args()


def touched_files(staged: bool) -> set[str]:
    if staged:
        return git_names(["diff", "--cached", "--name-only"])
    modified = git_names(["diff", "--name-only"])
    untracked = git_names(["ls-files", "--others", "--exclude-standard"])
    return modified | untracked


def dirty_files() -> set[str]:
    """回傳目前工作樹中真正有變動的檔案，排除 tracked unchanged 檔。"""
    modified = git_names(["diff", "--name-only"])
    staged = git_names(["diff", "--cached", "--name-only"])
    untracked = git_names(["ls-files", "--others", "--exclude-standard"])
    return modified | staged | untracked


def build_report(
    staged: bool,
    allow_multiple_slices: bool = False,
    touched_override: set[str] | None = None,
) -> dict[str, Any]:
    touched = touched_files(staged) if touched_override is None else touched_override
    dirty = dirty_files() if touched_override is None else touched_override
    checks: list[dict[str, Any]] = []
    touched_slice_names: list[str] = []
    for name, spec in SLICE_GROUPS.items():
        files = list(spec["files"])
        touched_in_slice = sorted(set(files) & touched)
        if not touched_in_slice:
            checks.append(
                {
                    "name": name,
                    "status": "OK",
                    "kind": spec["kind"],
                    "message": "slice untouched",
                    "touched": [],
                    "missing_files": [],
                }
            )
            continue
        touched_slice_names.append(name)
        missing_files = missing(files)
        present_files = existing(files)
        if staged:
            staged_files = sorted(set(files) & touched)
            required_if_staged = set(files) & dirty
            missing_from_stage = sorted(required_if_staged - touched)
            ok = not missing_from_stage
            message = "complete staged slice" if ok else "partial staged slice"
            checks.append(
                {
                    "name": name,
                    "status": "OK" if ok else "FAILED",
                    "kind": spec["kind"],
                    "message": message,
                    "staged": staged_files,
                    "missing_from_stage": missing_from_stage,
                    "note": spec["note"],
                }
            )
        else:
            ok = not missing_files
            checks.append(
                {
                    "name": name,
                    "status": "OK" if ok else "FAILED",
                    "kind": spec["kind"],
                    "message": "workspace slice dependencies present" if ok else "workspace slice dependencies missing",
                    "touched": touched_in_slice,
                    "present_files": present_files,
                    "missing_files": missing_files,
                    "note": spec["note"],
                }
            )
    if staged and not allow_multiple_slices:
        ok = len(touched_slice_names) <= 1
        checks.append(
            {
                "name": "single_staged_slice",
                "status": "OK" if ok else "FAILED",
                "kind": "commit_boundary",
                "message": "single staged slice" if ok else "multiple staged slices require --allow-multiple-slices",
                "touched_slices": touched_slice_names,
                "allow_multiple_slices": allow_multiple_slices,
            }
        )
    failed = [row for row in checks if row["status"] != "OK"]
    return {
        "schema_version": "research-tooling-merge-slices-verification.v1",
        "mode": "staged" if staged else "workspace",
        "allow_multiple_slices": allow_multiple_slices,
        "status": "OK" if not failed else "FAILED",
        "failed_count": len(failed),
        "checks": checks,
    }


def self_test() -> int:
    one_slice = set(SLICE_GROUPS["production_ranking_overlay"]["files"])
    two_slices = one_slice | set(SLICE_GROUPS["clawd_timeout"]["files"])
    checks = [
        (
            "one_complete_slice_ok",
            build_report(staged=True, touched_override=one_slice)["status"] == "OK",
        ),
        (
            "two_complete_slices_blocked",
            build_report(staged=True, touched_override=two_slices)["status"] == "FAILED",
        ),
        (
            "two_complete_slices_allowed",
            build_report(staged=True, allow_multiple_slices=True, touched_override=two_slices)["status"] == "OK",
        ),
    ]
    failed = [name for name, ok in checks if not ok]
    print(
        json.dumps(
            {
                "status": "FAILED" if failed else "OK",
                "checks": [{"name": name, "ok": ok} for name, ok in checks],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()
    report = build_report(args.staged, allow_multiple_slices=args.allow_multiple_slices)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
