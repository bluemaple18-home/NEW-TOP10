#!/usr/bin/env python3
"""驗證 autonomous research runner 的安全邊界與發題能力。"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_autonomous_research as auto  # noqa: E402


ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research_verification_latest.json"


def write_ranking(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_id",
                "stock_name",
                "model_prob",
                "risk_adjusted_score",
                "suggested_weight",
                "max_position_weight",
                "gross_exposure",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "stock_id": "2330",
                "stock_name": "台積電",
                "model_prob": "0.7",
                "risk_adjusted_score": "1.0",
                "suggested_weight": "0.2",
                "max_position_weight": "0.2",
                "gross_exposure": "0.4",
            }
        )


def make_args(**overrides: Any) -> Any:
    class Args:
        date = "2026-01-05"
        output = None
        features = "data/clean/features.parquet"
        baseline_dir = auto.BASELINE_RANKINGS_DIR
        candidate_dir = None
        topic_index = 0
        max_topics = 12
        min_ranking_files = 3
        max_ranking_files = 3
        horizons = "3,5"
        stop_loss_pcts = "none,0.08"
        take_profit_pcts = "none,0.15"
        max_group_exposures = "none,0.35"
        execute = False
        execute_topic_count = 1
        from_queue = False
        rerun = False
        include_rejected = False
        no_manager_update = False

    args = Args()
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def verify_topic_generation() -> dict[str, bool]:
    original_root = auto.PROJECT_ROOT
    original_artifacts = auto.ARTIFACTS_DIR
    original_ledger = auto.LEDGER_PATH
    with tempfile.TemporaryDirectory(prefix="top10-autonomous-research-") as tmp:
        root = Path(tmp)
        auto.PROJECT_ROOT = root
        auto.ARTIFACTS_DIR = root / "artifacts"
        auto.LEDGER_PATH = auto.ARTIFACTS_DIR / "model_experiments" / "model_experiment_ledger.json"
        try:
            for index in range(3):
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "historical_rankings_current_model" / f"ranking_2026-01-0{index + 1}.csv")
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "shadow_rankings_big_bull_candidate" / f"ranking_2026-01-0{index + 1}.csv")
            auto.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
            auto.LEDGER_PATH.write_text(
                json.dumps(
                    {
                        "schema_version": "model-experiment-ledger.v1",
                        "ledger_role": "state_memory",
                        "production_promotion_allowed": False,
                        "experiments": [
                            {
                                "candidate": "big_bull_candidate",
                                "status": "pending",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            topics = auto.generate_topics(make_args())
            selected = auto.selected_topic(topics, 0)
            selected_topics = auto.select_topics_for_run(topics, make_args())
            payload = auto.build_payload(make_args(), topics, selected_topics, [], [], {"decision": "DRY_RUN_TOPIC_SELECTED", "promotion_allowed": False}, {})
        finally:
            auto.PROJECT_ROOT = original_root
            auto.ARTIFACTS_DIR = original_artifacts
            auto.LEDGER_PATH = original_ledger
    return {
        "topic_generated": bool(topics),
        "baseline_excluded_from_topics": all("historical_rankings_current_model" not in topic.candidate_dir for topic in topics),
        "selected_big_bull_candidate": selected is not None and "big_bull" in selected.candidate_dir,
        "ledger_signal_scored": selected is not None and any("ledger" in reason for reason in selected.reasons),
        "contract_blocks_promotion": payload["contract"]["production_promotion_allowed"] is False,
        "dry_run_has_no_steps": payload["steps"] == [],
    }


def verify_runner_allowlist() -> dict[str, bool]:
    allowed_matrix = auto.command_allowed([sys.executable, "scripts/run_backtest_strategy_matrix.py"])
    allowed_compare = auto.command_allowed([sys.executable, "scripts/compare_strategy_matrices.py"])
    blocked = auto.command_allowed([sys.executable, "scripts/run_training_candidate_flow.py"])
    return {
        "strategy_matrix_allowed": allowed_matrix,
        "comparison_allowed": allowed_compare,
        "training_flow_blocked": blocked is False,
    }


def verify_outcome_decision() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="top10-autonomous-outcome-") as tmp:
        path = Path(tmp) / "comparison.json"
        path.write_text(
            json.dumps(
                {
                    "summary": [
                        {"variant": "baseline", "best_score": 0.1, "best_total_return": 0.05, "best_max_drawdown": -0.08},
                        {"variant": "candidate", "best_score": 0.2, "best_total_return": 0.06, "best_max_drawdown": -0.07},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        outcome = auto.outcome_from_comparison(path)
    return {
        "positive_candidate_confirmed_for_next_replay": outcome["decision"] == "CONFIRMED_FOR_NEXT_REPLAY",
        "outcome_never_promotes": outcome["promotion_allowed"] is False,
        "score_delta_positive": outcome["score_delta"] == 0.1,
    }


def verify_manager_update() -> dict[str, bool]:
    original_root = auto.PROJECT_ROOT
    original_artifacts = auto.ARTIFACTS_DIR
    original_output = auto.OUTPUT_DIR
    original_ledger = auto.LEDGER_PATH
    with tempfile.TemporaryDirectory(prefix="top10-autonomous-manager-") as tmp:
        root = Path(tmp)
        auto.PROJECT_ROOT = root
        auto.ARTIFACTS_DIR = root / "artifacts"
        auto.OUTPUT_DIR = auto.ARTIFACTS_DIR / "autonomous_research"
        auto.LEDGER_PATH = auto.ARTIFACTS_DIR / "model_experiments" / "model_experiment_ledger.json"
        try:
            for index in range(3):
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "historical_rankings_current_model" / f"ranking_2026-01-0{index + 1}.csv")
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "shadow_rankings_big_bull_candidate" / f"ranking_2026-01-0{index + 1}.csv")
            args = make_args(execute=True)
            topics = auto.generate_topics(args)
            selected = auto.selected_topic(topics, 0)
            selected_topics = auto.select_topics_for_run(topics, args)
            payload = auto.build_payload(
                args,
                topics,
                selected_topics,
                [
                    {
                        "topic": auto.topic_to_json(selected),
                        "status": "OK",
                        "outcome": {"decision": "PARTIAL_SCORE_ONLY", "score_delta": 0.01, "promotion_allowed": False},
                        "steps": [],
                        "outputs": {},
                    }
                ],
                [],
                {"decision": "PARTIAL_SCORE_ONLY", "score_delta": 0.01, "promotion_allowed": False},
                {"run_dir": "artifacts/autonomous_research/run_test"},
            )
            run_output = auto.OUTPUT_DIR / "autonomous_research_2026-01-05.json"
            manager = auto.update_manager(payload, run_output)
            summary = auto.load_json(auto.OUTPUT_DIR / "manager_summary.json")
            registry = auto.load_json(auto.OUTPUT_DIR / "topic_registry.json")
            history = auto.load_json(auto.OUTPUT_DIR / "run_history.json")
            queue = auto.load_json(auto.OUTPUT_DIR / "next_action_queue.json")
            runner_registry = auto.load_json(auto.OUTPUT_DIR / "runner_registry.json")
            selected_row = next((row for row in registry.get("topics", []) if row.get("topic_id") == selected.topic_id), {})
        finally:
            auto.PROJECT_ROOT = original_root
            auto.ARTIFACTS_DIR = original_artifacts
            auto.OUTPUT_DIR = original_output
            auto.LEDGER_PATH = original_ledger
    return {
        "manager_status_ok": manager["status"] == "OK",
        "manager_summary_written": summary.get("schema_version") == auto.MANAGER_SCHEMA_VERSION,
        "registry_written": bool(registry.get("topics")),
        "history_written": bool(history.get("runs")),
        "queue_written": bool(queue.get("actions")),
        "selected_status_partial": selected_row.get("manager_status") == "partial_needs_followup",
        "selected_run_count_incremented": selected_row.get("run_count") == 1,
        "manager_never_promotes": summary.get("contract", {}).get("production_promotion_allowed") is False,
        "runner_registry_written": runner_registry.get("schema_version") == auto.RUNNER_REGISTRY_SCHEMA_VERSION,
        "runner_registry_blocks_promotion": runner_registry.get("contract", {}).get("production_promotion_allowed") is False,
    }


def verify_queue_selection_and_cooldown() -> dict[str, bool]:
    original_root = auto.PROJECT_ROOT
    original_artifacts = auto.ARTIFACTS_DIR
    original_output = auto.OUTPUT_DIR
    original_ledger = auto.LEDGER_PATH
    with tempfile.TemporaryDirectory(prefix="top10-autonomous-queue-") as tmp:
        root = Path(tmp)
        auto.PROJECT_ROOT = root
        auto.ARTIFACTS_DIR = root / "artifacts"
        auto.OUTPUT_DIR = auto.ARTIFACTS_DIR / "autonomous_research"
        auto.LEDGER_PATH = auto.ARTIFACTS_DIR / "model_experiments" / "model_experiment_ledger.json"
        try:
            for index in range(3):
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "historical_rankings_current_model" / f"ranking_2026-01-0{index + 1}.csv")
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "shadow_rankings_big_bull_candidate_a" / f"ranking_2026-01-0{index + 1}.csv")
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "shadow_rankings_big_bull_candidate_b" / f"ranking_2026-01-0{index + 1}.csv")
                write_ranking(auto.ARTIFACTS_DIR / "backtest" / "shadow_rankings_big_bull_candidate_c" / f"ranking_2026-01-0{index + 1}.csv")
            topics = auto.generate_topics(make_args(max_topics=10))
            first = topics[0]
            second = topics[1]
            third = topics[2]
            auto.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (auto.OUTPUT_DIR / "topic_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-topic-registry.v1",
                        "topics": [
                            {
                                **auto.topic_to_json(first),
                                "manager_status": "partial_needs_followup",
                                "run_count": 1,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (auto.OUTPUT_DIR / "next_action_queue.json").write_text(
                json.dumps(
                    {
                        "schema_version": "autonomous-research-next-action-queue.v1",
                        "actions": [
                            {
                                "topic_id": first.topic_id,
                                "manager_status": "partial_needs_followup",
                                "next_action": "rerun_with_larger_window_or_add_risk_check",
                            },
                            {
                                "topic_id": third.topic_id,
                                "manager_status": "candidate",
                                "next_action": "run_autonomous_research_execute_smoke",
                            },
                            {
                                "topic_id": second.topic_id,
                                "manager_status": "candidate",
                                "next_action": "run_autonomous_research_execute_smoke",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            cooled = auto.select_topics_for_run(topics, make_args(execute=True, from_queue=True, execute_topic_count=2))
            rerun = auto.select_topics_for_run(topics, make_args(execute=True, from_queue=True, execute_topic_count=2, rerun=True))
            no_queue_path = auto.OUTPUT_DIR / "next_action_queue.json"
            no_queue_path.unlink()
            no_queue = auto.select_topics_for_run(topics, make_args(execute=True, from_queue=True, execute_topic_count=2))
        finally:
            auto.PROJECT_ROOT = original_root
            auto.ARTIFACTS_DIR = original_artifacts
            auto.OUTPUT_DIR = original_output
            auto.LEDGER_PATH = original_ledger
    return {
        "queue_selects_two_topics": len(cooled) == 2,
        "cooldown_skips_previously_run_topic": all(topic.topic_id != first.topic_id for topic in cooled),
        "rerun_allows_previously_run_topic": any(topic.topic_id == first.topic_id for topic in rerun),
        "from_queue_uses_queue_order": [topic.topic_id for topic in cooled] == [third.topic_id, second.topic_id],
        "rerun_starts_from_queue_head": bool(rerun) and rerun[0].topic_id == first.topic_id,
        "missing_queue_does_not_fallback_to_generated_topics": no_queue == [],
    }


def main() -> int:
    checks = {
        **verify_topic_generation(),
        **verify_runner_allowlist(),
        **verify_outcome_decision(),
        **verify_manager_update(),
        **verify_queue_selection_and_cooldown(),
    }
    status = "OK" if all(checks.values()) else "FAILED"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "autonomous-research-verification.v1",
                "status": status,
                "checks": checks,
                "note": "synthetic ranking dirs; does not run real backtest",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if status == "OK":
        print(f"AUTONOMOUS_RESEARCH_OK output={ARTIFACT_PATH}")
        return 0
    print(f"AUTONOMOUS_RESEARCH_FAILED output={ARTIFACT_PATH}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
