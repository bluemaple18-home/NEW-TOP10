#!/usr/bin/env python3
"""驗證 research shadow run 只產生 shadow-only feature artifacts。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "research_shadow_runs_verification_latest.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def build_gate(path: Path) -> None:
    candidates = []
    for candidate_id, status in [
        ("candidate_persistence", "READY_FOR_SHADOW"),
        ("portfolio_risk_overlay", "READY_FOR_SHADOW"),
        ("regime_feature_group_ablation", "BLOCKED"),
        ("weekend_research_matrix", "BLOCKED"),
        ("market_context", "READY_FOR_SHADOW"),
    ]:
        candidates.append(
            {
                "id": candidate_id,
                "label": candidate_id,
                "shadow_status": status,
                "allowed_shadow_uses": [f"use {candidate_id} in shadow only"],
                "blocked_production_uses": ["do not change production ranking"],
                "promotion_requirements": [f"{candidate_id} promotion requires sealed evidence"],
                "evidence": {"synthetic": True},
                "blockers": [] if status == "READY_FOR_SHADOW" else ["synthetic gate blocker"],
            }
        )
    write_json(
        path,
        {
            "schema_version": "feature-experiment-gate.v1",
            "status": "READY_FOR_SHADOW_TESTS",
            "summary": {"ready_for_shadow": ["candidate_persistence", "portfolio_risk_overlay", "market_context"]},
            "candidates": candidates,
        },
    )


def build_config(path: Path, root: Path, gate_path: Path) -> None:
    payload = {
        "schema_version": "research-shadow-runs.v1",
        "window_id": "2026-01-01_2026-01-31",
        "dates_from_dir": "unused",
        "features": "unused",
        "market_regime_history": "unused",
        "industry_map": "unused",
        "sealed_start": "2026-01-01",
        "sealed_end": "2026-01-31",
        "variants": [],
        "baseline": {"id": "current", "replay_output": "unused"},
        "outputs": {
            "replay_comparison": str(root / "unused_replay_comparison.json"),
            "window_stability": str(root / "unused_window_stability.json"),
            "decision_report": str(root / "unused_decision_report.json"),
            "manifest": str(root / "research_shadow_run_manifest.json"),
        },
        "feature_experiments": {
            "feature_gate": str(gate_path),
            "output_prefix": str(root / "shadow_feature_experiment"),
            "run_output_prefix": str(root / "research_shadow_run"),
            "include_candidates": [
                "candidate_persistence",
                "portfolio_risk_overlay",
                "regime_feature_group_ablation",
                "weekend_research_matrix",
            ],
            "excluded_candidates": {
                "market_context": "synthetic exclusion",
            },
        },
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-research-shadow-runs-") as tmp:
        root = Path(tmp)
        gate_path = root / "feature_gate.json"
        config_path = root / "research_shadow_runs.yaml"
        build_gate(gate_path)
        build_config(config_path, root, gate_path)
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_research_shadow_runs.py"),
                "--config",
                str(config_path),
                "--feature-experiments-only",
                "--run-date",
                "2026-01-31",
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        manifest = json.loads((root / "research_shadow_run_manifest.json").read_text(encoding="utf-8"))
        outputs = {item["candidate_id"]: root / Path(item["output"]).name for item in manifest["feature_experiments"]}
        run_outputs = {item["candidate_id"]: root / Path(item["run_output"]).name for item in manifest["feature_experiments"]}
        checks = {
            "schema_ok": manifest["schema_version"] == "research-shadow-run-manifest.v1",
            "status_ok": manifest["status"] == "OK",
            "four_requested_candidates": sorted(outputs)
            == [
                "candidate_persistence",
                "portfolio_risk_overlay",
                "regime_feature_group_ablation",
                "weekend_research_matrix",
            ],
            "market_context_excluded": manifest["excluded_feature_experiments"][0]["candidate_id"] == "market_context",
            "market_context_not_written": not (root / "shadow_feature_experiment_market_context_2026-01-31.json").exists(),
            "production_contract_blocks": manifest["contract"]["production_score_change_allowed"] is False
            and manifest["contract"]["does_not_train_model"] is True
            and manifest["contract"]["does_not_change_production_ranking"] is True,
            "candidate_artifacts_exist": all(path.exists() for path in outputs.values()),
            "run_artifacts_exist": all(path.exists() for path in run_outputs.values()),
            "blocked_gate_preserved": json.loads(outputs["regime_feature_group_ablation"].read_text(encoding="utf-8"))["status"]
            == "BLOCKED_BY_GATE",
            "ready_gate_preserved": json.loads(outputs["candidate_persistence"].read_text(encoding="utf-8"))["status"]
            == "READY_FOR_SHADOW",
        }
        status = "OK" if all(checks.values()) else "FAILED"
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(
            json.dumps(
                {
                    "schema_version": "research-shadow-runs-verification.v1",
                    "status": status,
                    "checks": checks,
                    "note": "uses TemporaryDirectory synthetic gate/config; no ranking, model training, or production artifact writes",
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        if status == "OK":
            print(f"RESEARCH_SHADOW_RUNS_OK output={ARTIFACT_PATH}")
            return 0
        print(f"RESEARCH_SHADOW_RUNS_FAILED output={ARTIFACT_PATH}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
