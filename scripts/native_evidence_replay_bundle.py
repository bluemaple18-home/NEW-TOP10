#!/usr/bin/env python3
"""重跑兩個 development-only native evidence cycles 並輸出 compact bundle。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research.batch_owner import build_batch_intent, publish_batch_intent  # noqa: E402
from app.research.contracts import content_hash  # noqa: E402
from app.research.eligibility import build_projection as build_eligibility  # noqa: E402
from app.research.native_evidence_replay import (  # noqa: E402
    build_bundle,
    file_sha256,
    verify_bundle,
)
from app.research.observation_ingest import ingest_corpus  # noqa: E402
from app.research.parameter_learning import build_projection as build_learning  # noqa: E402
from scripts import run_autonomous_research as runner  # noqa: E402


EVIDENCE_ROOT = PROJECT_ROOT / "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1"
PARITY_PATHS = (
    "artifacts/autonomous_research/next_action_queue.json",
    "artifacts/autonomous_research/research_spine",
    "data/research/research_ledger.duckdb",
    "models/baseline_stats.json",
    "models/latest_lgbm.pkl",
    "app/modeling/model_runtime_promotion.py",
    "app/agent_b_ranking.py",
    "config/signals.yaml",
    "scripts/com.new-top10.pm-research-harness.plist",
    "scripts/com.new-top10.fog-research-worker.plist",
)


def _tree_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        return {"exists": True, "kind": "file", "sha256": file_sha256(path)}
    files = [
        {"path": item.relative_to(path).as_posix(), "sha256": file_sha256(item)}
        for item in sorted(path.rglob("*"))
        if item.is_file() and not item.is_symlink()
    ]
    return {"exists": True, "kind": "directory", "tree_hash": content_hash({"files": files})}


def parity_inventory() -> dict[str, Any]:
    return {relative: _tree_identity(PROJECT_ROOT / relative) for relative in PARITY_PATHS}


def _storage(root: Path) -> dict[str, int]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return {"bytes": sum(path.stat().st_size for path in files), "file_count": len(files)}


def _write_rankings(root: Path, label: str) -> tuple[Path, Path]:
    baseline = root / label / "baseline"
    candidate = root / label / "candidate"
    baseline.mkdir(parents=True)
    candidate.mkdir(parents=True)
    (baseline / "ranking_2026-01-02.csv").write_text("symbol,score\nA,1\n", encoding="utf-8")
    (candidate / "ranking_2026-01-02.csv").write_text("symbol,score\nA,2\n", encoding="utf-8")
    return baseline, candidate


def _write_observed_matrix(path: Path, context: Any, role: str, cycle: int) -> None:
    episode_id = f"episode-dev-{cycle}"
    episode_authority = {
        "ok": True,
        "reason_code": "DEVELOPMENT_EPISODES_ONLY",
        "development_episode_ids": [episode_id],
        "excluded_episode_ids_hash": content_hash({"excluded": []}),
        "sealed_trade_date_hash": content_hash({"sealed": []}),
    }
    scenarios = []
    for trial_id in context.trial_ids_by_role[role]:
        spec = context.trial_specs[trial_id]
        parameters = spec["parameters"]
        horizon = int(parameters["horizon"])
        role_offset = 0.02 if role == "candidate" else 0.0
        score = round(0.08 + horizon * 0.01 + role_offset, 6)
        scenarios.append(
            {
                "scenario_id": f"h{horizon}_sl0p08_tp0p15_gc0p35",
                "horizon": horizon,
                "stop_loss_pct": parameters["stop_loss_pct"],
                "take_profit_pct": parameters["take_profit_pct"],
                "max_group_exposure": parameters["max_group_exposure"],
                "total_return": round(score * 0.5, 6),
                "max_drawdown": round(-0.16 + horizon * 0.002, 6),
                "win_rate": round(0.50 + horizon * 0.003, 6),
                "avg_trade_return": round(score / 20, 6),
                "trade_count": 25 + horizon,
                "score": score,
                "p_value": 0.04,
                "robust_neighbor_pass_count": 0,
                "execution_authority": {
                    "research_stage": spec["research_stage"],
                    "regime_scope": spec["regime_scope"],
                    "episode_ids": [episode_id],
                    "episode_authority_hash": content_hash(episode_authority),
                    "episode_authority": episode_authority,
                    "dataset_hash": spec["dataset_authority"]["dataset_hash"],
                    "dataset_manifest": spec["execution_profile"]["dataset_manifest"],
                    "ranking_manifest": spec["execution_profile"]["ranking_manifest"],
                    "execution_settings": spec["execution_profile"]["execution_settings"],
                },
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "backtest-strategy-matrix.v1",
                "research_spine": {
                    "run_id": context.run_id,
                    "intent_id": context.intent_id,
                    "variant_role": role,
                    "requested_trial_spec_ids": context.trial_ids_by_role[role],
                },
                "contract": {
                    "research_stage": "DEVELOPMENT_SCREEN",
                    "development_only": True,
                    "sealed_data_read_allowed": False,
                },
                "inputs": {"development_scope": {"ok": True, "development_episode_ids": [episode_id]}},
                "scenarios": scenarios,
            },
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _write_development_authority(path: Path, context: Any, regime_id: str, cycle: int) -> None:
    spec = next(iter(context.trial_specs.values()))
    path.write_text(
        json.dumps(
            {
                "research_stage": "DEVELOPMENT_SCREEN",
                "topic_id": spec["topic_id"],
                "regime_id": regime_id,
                "dataset_hash": spec["dataset_authority"]["dataset_hash"],
                "execution_dataset_hash": spec["dataset_authority"]["dataset_hash"],
                "split_artifact_hash": content_hash({"split": cycle}),
                "research_contract_hash": content_hash({"contract": "native-evidence-replay.v1"}),
                "regime_history_hash": content_hash({"regime": regime_id}),
                "development_episode_ids": [f"episode-dev-{cycle}"],
                "boundary": {"exact_match_required": True, "sealed_data_read_allowed": False},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _run_cycle(root: Path, cycle: int, regime_id: str, horizons: str) -> dict[str, Any]:
    corpus = root / "research_spine"
    ledger = root / "ledger/research_ledger.duckdb"
    manager = root / "manager"
    manager.mkdir(parents=True, exist_ok=True)
    features = root / "features.parquet"
    if not features.exists():
        features.write_bytes(b"bounded-native-evidence-replay\n")
    baseline, candidate = _write_rankings(root, f"cycle-{cycle}")
    output = manager / f"cycle-{cycle}.json"
    batch_id = f"research-2026-08-14-12000{cycle}-910{cycle}"
    runner_argv = [
        "scripts/run_autonomous_research.py",
        "--date",
        "2026-08-14",
        "--research-batch-id",
        batch_id,
        "--execute",
        "--closed-regime-research",
        "--development-screen-on-sealed-exhaustion",
        "--output",
        str(output),
        "--features",
        str(features),
        "--execute-topic-count",
        "1",
        "--development-screen-topic-count",
        "1",
        "--max-topics",
        "1",
        "--no-manager-update",
    ]
    intent = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id=batch_id,
        scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=runner_argv,
        output_path=output,
        ledger_path=ledger,
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN"],
        policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
        catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
        execution_epoch="2026-08-14",
        created_at=f"2026-08-14T12:00:0{cycle}Z",
    )
    publish_batch_intent(corpus_root=corpus, payload=intent)
    topic = runner.ResearchTopic(
        topic_id="native_evidence_replay:representative",
        title="Native evidence replay",
        hypothesis="Bounded development evidence remains independently reproducible",
        validation_plan="Use the trusted Runner and immutable evidence lifecycle",
        runner="strategy_matrix_comparison",
        candidate_dir=str(candidate),
        baseline_dir=str(baseline),
        score=1.0,
        reasons=["native_evidence_replay"],
        evidence_sources=[],
        ranking_file_count=1,
        validation_profile="native_evidence_replay",
        horizons=horizons,
        stop_loss_pcts="0.08",
        take_profit_pcts="0.15",
        max_group_exposures="0.35",
        regime_identity={"regime_id": regime_id},
        selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
    )

    def execute_bounded_topic(
        _args: Any,
        active_topic: Any,
        run_dir: Path,
        *,
        on_execution_started: Any = None,
        receipt_attempt: Any = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        if receipt_attempt is None or active_topic.topic_id != topic.topic_id:
            raise RuntimeError("BOUNDED_REPLAY_ATTEMPT_MISMATCH")
        if on_execution_started is not None:
            on_execution_started()
        run_dir.mkdir(parents=True, exist_ok=True)
        slug = runner.slugify(active_topic.topic_id)
        baseline_path = run_dir / f"{slug}_baseline_strategy_matrix.json"
        candidate_path = run_dir / f"{slug}_candidate_strategy_matrix.json"
        authority_path = run_dir / f"{slug}_development_screen_contract.json"
        _write_observed_matrix(baseline_path, receipt_attempt, "baseline", cycle)
        _write_observed_matrix(candidate_path, receipt_attempt, "candidate", cycle)
        _write_development_authority(authority_path, receipt_attempt, regime_id, cycle)
        return (
            [
                {"name": "baseline.strategy_matrix", "status": "OK"},
                {"name": "candidate.strategy_matrix", "status": "OK"},
                {"name": "compare.strategy_matrices", "status": "OK"},
            ],
            {"decision": "PARTIAL_SCORE_ONLY", "promotion_allowed": False},
            {
                "baseline_strategy_matrix": str(baseline_path),
                "candidate_strategy_matrix": str(candidate_path),
                "development_screen_contract": str(authority_path),
            },
        )

    intent_path = corpus / "batch_intents" / f"{str(intent['batch_intent_id'])[7:]}.json"
    before_receipts = {path.name for path in (corpus / "receipts").glob("*.json")}
    with (
        patch.object(runner, "build_daily_source_lineage", return_value={"source": "bounded-replay"}),
        patch.object(runner, "generate_all_topics", return_value=[topic]),
        patch.object(runner, "apply_closed_experiment_capacity", side_effect=lambda topics, _args: topics),
        patch.object(runner, "execute_topic", side_effect=execute_bounded_topic),
        patch.object(runner, "OUTPUT_DIR", runner.OUTPUT_DIR),
        patch.object(runner, "RESEARCH_LEDGER_PATH", runner.RESEARCH_LEDGER_PATH),
        patch.object(runner, "RESEARCH_SPINE_ROOT", runner.RESEARCH_SPINE_ROOT),
        patch.object(sys, "argv", [*runner_argv, "--research-batch-intent", str(intent_path)]),
    ):
        if runner.main() != 0:
            raise RuntimeError(f"CYCLE_{cycle}_RUNNER_FAILED")
    new_receipts = [
        path for path in (corpus / "receipts").glob("*.json") if path.name not in before_receipts
    ]
    if len(new_receipts) != 1:
        raise RuntimeError(f"CYCLE_{cycle}_RECEIPT_COUNT_MISMATCH")
    receipt = json.loads(new_receipts[0].read_text(encoding="utf-8"))
    first = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    second = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    storage = _storage(root)
    return {
        "cycle_identity": f"native-evidence-replay-cycle-{cycle}",
        "action": "RUN_DEVELOPMENT_SCREEN",
        "research_batch_id": batch_id,
        "run_id": receipt["run_id"],
        "intent_id": receipt["intent_id"],
        "receipt_id": receipt["receipt_id"],
        "regime_id": regime_id,
        "terminal_status": receipt["terminal_status"],
        "observation_status": receipt["execution_observation_status"],
        "identity_match_status": receipt["identity_match_status"],
        "execution_unit_count": len(receipt["executed_units"]),
        "first_ingest_observations_inserted": first.observations_inserted,
        "second_ingest_observations_inserted": second.observations_inserted,
        "isolated_storage_bytes": storage["bytes"],
        "isolated_file_count": storage["file_count"],
    }


def run(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = json.loads(
        (PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json").read_text(encoding="utf-8")
    )
    budget = policy["capacity_budget"]
    before = parity_inventory()
    root = Path(tempfile.mkdtemp(prefix="nerb-replay-"))
    cleaned = False
    try:
        cycles = [
            _run_cycle(root, 1, "RISK_OFF|", "5"),
            _run_cycle(root, 2, "NARROW_LEADER|BIG_BULL", "3,5,10"),
        ]
        for cycle in cycles:
            if cycle["isolated_storage_bytes"] > budget["max_bytes_per_cycle"]:
                raise RuntimeError("CAPACITY_BYTES_EXCEEDED")
            if cycle["isolated_file_count"] > budget["max_files_per_cycle"]:
                raise RuntimeError("CAPACITY_FILES_EXCEEDED")
        ledger = root / "ledger/research_ledger.duckdb"
        eligibility = build_eligibility(ledger_path=ledger, output_root=root / "eligibility")
        learning = build_learning(
            ledger_path=ledger,
            eligibility_output_root=root / "eligibility",
            output_root=root / "learning",
        )
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
        generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        bundle = build_bundle(
            ledger_path=ledger,
            cycle_receipts=cycles,
            eligibility=eligibility,
            learning=learning,
            project_root=PROJECT_ROOT,
            source_commit=source_commit,
            generated_at=generated_at,
        )
        bundle_path = output_dir / "bundle.json"
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        first_verification = verify_bundle(bundle, project_root=PROJECT_ROOT)
        second_verification = verify_bundle(_load_bundle(bundle_path), project_root=PROJECT_ROOT)
        if first_verification != second_verification or first_verification["status"] != "PASS":
            raise RuntimeError("DETERMINISTIC_VERIFICATION_FAILED")
        after_cycles = parity_inventory()
        if before != after_cycles:
            raise RuntimeError("CANONICAL_PARITY_DRIFT")
    finally:
        shutil.rmtree(root)
        cleaned = not root.exists()
    post_cleanup_verification = verify_bundle(_load_bundle(bundle_path), project_root=PROJECT_ROOT)
    after_cleanup = parity_inventory()
    manifest = {
        "schema_version": "native-evidence-replay-manifest.v1",
        "generated_at": generated_at,
        "bundle_path": bundle_path.relative_to(PROJECT_ROOT).as_posix(),
        "bundle_sha256": file_sha256(bundle_path),
        "bundle_id": bundle["bundle_id"],
        "status": bundle["admission"]["status"],
        "verification": post_cleanup_verification,
        "deterministic_verification_runs": 2,
        "parity": {
            "before_hash": content_hash(before),
            "after_cycles_hash": content_hash(after_cycles),
            "after_cleanup_hash": content_hash(after_cleanup),
            "unchanged": before == after_cycles == after_cleanup,
            "paths": list(PARITY_PATHS),
        },
        "cleanup": {
            "status": "PASS" if cleaned else "FAIL",
            "isolated_root_removed": cleaned,
            "bundle_verified_after_cleanup": post_cleanup_verification["status"] == "PASS",
        },
        "capacity": {
            "status": "PASS",
            "max_bytes_per_cycle": budget["max_bytes_per_cycle"],
            "max_files_per_cycle": budget["max_files_per_cycle"],
            "observed_cycles": [
                {
                    "cycle_identity": cycle["cycle_identity"],
                    "bytes": cycle["isolated_storage_bytes"],
                    "file_count": cycle["isolated_file_count"],
                }
                for cycle in cycles
            ],
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _load_bundle(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("INVALID_BUNDLE_ROOT")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=EVIDENCE_ROOT)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify is not None:
        report = verify_bundle(_load_bundle(args.verify), project_root=PROJECT_ROOT)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["status"] == "PASS" else 2
    manifest = run(args.output_dir.resolve())
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
