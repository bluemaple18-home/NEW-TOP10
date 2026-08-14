from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.research.contracts import content_hash, validate_run_receipt
from app.research.run_receipts import (
    begin_topic_attempt,
    finish_topic_attempt,
    reconcile_orphan_attempts,
)


def topic(tmp_path: Path) -> SimpleNamespace:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    (baseline / "ranking_2026-01-02.csv").write_text("symbol,score\nA,1\n")
    (candidate / "ranking_2026-01-02.csv").write_text("symbol,score\nA,2\n")
    return SimpleNamespace(
        topic_id="test:receipt",
        baseline_dir=str(baseline),
        candidate_dir=str(candidate),
        validation_profile="test",
    )


def scenario() -> dict:
    return {
        "horizon": 5,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.15,
        "max_group_exposure": 0.35,
    }


def begin(tmp_path: Path):
    features = tmp_path / "features.parquet"
    features.write_bytes(b"fixture")
    return begin_topic_attempt(
        corpus_root=tmp_path / "corpus",
        project_root=tmp_path,
        topic=topic(tmp_path),
        scenarios=[scenario()],
        research_stage="DEVELOPMENT_SCREEN",
        regime_scope={"regime_id": "RISK_OFF|"},
        features_path="features.parquet",
        execution_settings={
            "max_ranking_files": 8,
            "top_n": 10,
            "max_gross_exposure": 0.65,
            "max_position_weight": 0.2,
            "fee_rate": 0.001425,
            "tax_rate": 0.003,
            "slippage_rate": 0.001,
            "same_day_hit_priority": "stop_loss",
            "runner_policy_version": "strategy-matrix-replay.v1",
        },
    )


def write_matrix(path: Path, context, role: str) -> None:
    trial_id = context.trial_ids_by_role[role][0]
    spec = context.trial_specs[trial_id]
    episode_authority = {
        "ok": True,
        "reason_code": "DEVELOPMENT_EPISODES_ONLY",
        "development_episode_ids": ["episode-dev"],
        "excluded_episode_ids_hash": content_hash({"excluded": []}),
        "sealed_trade_date_hash": content_hash({"sealed": []}),
    }
    row = {
        **scenario(),
        "execution_authority": {
            "research_stage": spec["research_stage"],
            "regime_scope": spec["regime_scope"],
            "episode_ids": ["episode-dev"],
            "episode_authority_hash": content_hash(episode_authority),
            "episode_authority": episode_authority,
            "dataset_hash": spec["dataset_authority"]["dataset_hash"],
            "dataset_manifest": spec["execution_profile"]["dataset_manifest"],
            "ranking_manifest": spec["execution_profile"]["ranking_manifest"],
            "execution_settings": spec["execution_profile"]["execution_settings"],
        },
    }
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
                "inputs": {
                    "development_scope": {
                        "ok": True,
                        "development_episode_ids": ["episode-dev"],
                    }
                },
                "scenarios": [row],
            }
        ),
        encoding="utf-8",
    )


def write_development_authority(path: Path, context) -> None:
    spec = next(iter(context.trial_specs.values()))
    path.write_text(
        json.dumps(
            {
                "research_stage": "DEVELOPMENT_SCREEN",
                "topic_id": spec["topic_id"],
                "regime_id": "RISK_OFF|",
                "dataset_hash": spec["dataset_authority"]["dataset_hash"],
                "execution_dataset_hash": spec["dataset_authority"]["dataset_hash"],
                "split_artifact_hash": content_hash({"split": "fixture"}),
                "research_contract_hash": content_hash({"contract": "fixture"}),
                "regime_history_hash": content_hash({"history": "fixture"}),
                "development_episode_ids": ["episode-dev"],
                "boundary": {
                    "exact_match_required": True,
                    "sealed_data_read_allowed": False,
                },
            }
        ),
        encoding="utf-8",
    )


def test_attempt_is_persisted_before_runner_execution(tmp_path: Path) -> None:
    context = begin(tmp_path)
    assert (context.root / "attempts" / f"{context.run_id}.started.json").is_file()
    assert (context.root / "intents" / f"{context.intent_id}.json").is_file()
    assert len(list((context.root / "trial_specs").glob("*.json"))) == 2


def test_complete_matrix_execution_writes_exact_success_receipt(tmp_path: Path) -> None:
    context = begin(tmp_path)
    baseline = tmp_path / "run_baseline_strategy_matrix.json"
    candidate = tmp_path / "run_candidate_strategy_matrix.json"
    write_matrix(baseline, context, "baseline")
    write_matrix(candidate, context, "candidate")
    authority = tmp_path / "development_authority.json"
    write_development_authority(authority, context)
    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
        lineage_authority_paths=[authority],
    )
    assert validate_run_receipt(receipt) == []
    assert receipt["terminal_status"] == "SUCCEEDED"
    assert receipt["identity_match_status"] == "EXACT"
    assert len(receipt["executed_units"]) == 2
    assert all(
        unit["lineage"]["sealed_usage_status"] == "PROVEN_NON_SEALED"
        for unit in receipt["executed_units"]
    )
    assert all(
        unit["executed_parameters"][field] is None
        for unit in receipt["executed_units"]
        for field in ("regime_gate", "risk_guard", "entry_filter")
    )


def test_missing_matrix_fails_closed_instead_of_claiming_success(tmp_path: Path) -> None:
    context = begin(tmp_path)
    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[],
    )
    assert validate_run_receipt(receipt) == []
    assert receipt["terminal_status"] == "FAILED"
    assert receipt["execution_observation_status"] == "UNKNOWN"
    assert receipt["failure"]["reason_code"] == "INCOMPLETE_EXECUTION_FACTS"


def test_unproven_lineage_never_becomes_proven_non_sealed(tmp_path: Path) -> None:
    context = begin(tmp_path)
    baseline = tmp_path / "run_baseline_strategy_matrix.json"
    candidate = tmp_path / "run_candidate_strategy_matrix.json"
    for path, role in ((baseline, "baseline"), (candidate, "candidate")):
        write_matrix(path, context, role)
        payload = json.loads(path.read_text())
        payload.pop("contract")
        path.write_text(json.dumps(payload), encoding="utf-8")
    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
    )
    assert all(
        unit["lineage"]["sealed_usage_status"] == "UNKNOWN"
        and unit["lineage_resolution_status"] == "INVALID_LINEAGE"
        for unit in receipt["executed_units"]
    )


def test_corrupt_artifact_still_terminalizes_attempt(tmp_path: Path) -> None:
    context = begin(tmp_path)
    corrupt = tmp_path / "run_baseline_strategy_matrix.json"
    corrupt.write_text("{truncated", encoding="utf-8")
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[corrupt],
        failure_reason="SUBPROCESS_FAILED",
    )
    assert validate_run_receipt(receipt) == []
    assert receipt["terminal_status"] == "FAILED"
    assert receipt["execution_observation_status"] == "UNKNOWN"
    assert receipt["artifact_errors"][0]["reason_code"] == "JSONDECODEERROR"
    error = receipt["artifact_errors"][0]
    assert error["corpus_path"].startswith("source_corpus/sha256/")
    assert (context.root / error["corpus_path"]).is_file()


def test_wrong_attempt_correlation_and_extra_scenario_fail_closed(tmp_path: Path) -> None:
    context = begin(tmp_path)
    matrix = tmp_path / "run_baseline_strategy_matrix.json"
    write_matrix(matrix, context, "baseline")
    payload = json.loads(matrix.read_text())
    payload["research_spine"]["run_id"] = "wrong-run"
    payload["scenarios"].append({**scenario(), "horizon": 10})
    matrix.write_text(json.dumps(payload), encoding="utf-8")
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[matrix],
        failure_reason="RUNNER_STEP_FAILED",
    )
    assert validate_run_receipt(receipt) == []
    assert receipt["executed_units"] == []
    assert receipt["artifact_errors"][0]["reason_code"] == "ATTEMPT_CORRELATION_MISMATCH"


def test_executed_stage_is_taken_from_artifact_and_mismatch_is_disclosed(tmp_path: Path) -> None:
    context = begin(tmp_path)
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    write_matrix(baseline, context, "baseline")
    write_matrix(candidate, context, "candidate")
    payload = json.loads(candidate.read_text())
    payload["scenarios"][0]["execution_authority"]["research_stage"] = "COARSE_SCREEN"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
    )
    candidate_unit = next(
        unit
        for unit in receipt["executed_units"]
        if unit["requested_trial_spec_id"] in context.trial_ids_by_role["candidate"]
    )
    assert candidate_unit["executed_research_stage"] == "COARSE_SCREEN"
    assert candidate_unit["lineage_resolution_status"] == "INVALID_LINEAGE"
    assert receipt["identity_match_status"] == "EXPLAINED_MISMATCH"
    assert any(event["field"] == "research_stage" for event in receipt["resolution_events"])


def test_forged_episode_authority_fails_before_units_are_materialized(tmp_path: Path) -> None:
    context = begin(tmp_path)
    matrix = tmp_path / "baseline.json"
    write_matrix(matrix, context, "baseline")
    payload = json.loads(matrix.read_text())
    payload["scenarios"][0]["execution_authority"]["episode_authority_hash"] = content_hash(
        {"forged": True}
    )
    matrix.write_text(json.dumps(payload), encoding="utf-8")

    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[matrix],
        failure_reason="RUNNER_STEP_FAILED",
    )
    assert receipt["executed_units"] == []
    assert receipt["artifact_errors"][0]["reason_code"] == "EPISODE_AUTHORITY_HASH_MISMATCH"


def test_malformed_hash_terminalizes_instead_of_crashing(tmp_path: Path) -> None:
    context = begin(tmp_path)
    matrix = tmp_path / "baseline.json"
    write_matrix(matrix, context, "baseline")
    payload = json.loads(matrix.read_text())
    authority = payload["scenarios"][0]["execution_authority"]
    authority["dataset_hash"] = "sha256:x"
    authority["dataset_manifest"]["files"][0]["hash"] = "sha256:x"
    matrix.write_text(json.dumps(payload), encoding="utf-8")

    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[matrix],
    )
    assert receipt["terminal_status"] == "FAILED"
    assert receipt["executed_units"] == []
    assert (context.root / "receipts" / f"{context.run_id}.json").is_file()


def test_malformed_nested_authority_terminalizes_instead_of_crashing(tmp_path: Path) -> None:
    for field, invalid in (("research_stage", {}), ("episode_ids", [{}])):
        case = tmp_path / field
        case.mkdir()
        context = begin(case)
        matrix = case / "baseline.json"
        write_matrix(matrix, context, "baseline")
        payload = json.loads(matrix.read_text())
        payload["scenarios"][0]["execution_authority"][field] = invalid
        matrix.write_text(json.dumps(payload), encoding="utf-8")
        receipt = finish_topic_attempt(
            context,
            terminal_status="FAILED",
            matrix_paths=[matrix],
            failure_reason="RUNNER_STEP_FAILED",
        )
        assert receipt["executed_units"] == []
        assert (context.root / "receipts" / f"{context.run_id}.json").is_file()


def test_orphan_reconciliation_is_unknown_and_idempotent(tmp_path: Path) -> None:
    context = begin(tmp_path)
    observed_at = datetime.fromisoformat(context.started_at) + timedelta(days=2)
    first = reconcile_orphan_attempts(context.root, observed_at=observed_at)
    second = reconcile_orphan_attempts(context.root, observed_at=observed_at)
    assert first == second
    payload = json.loads(first[0].read_text())
    assert payload["sealed_usage_status"] == "UNKNOWN"
    assert set(payload["facts_unknown"]) == {
        "executed_parameters", "executed_lineage", "result"
    }


def test_duplicate_role_artifact_is_partial_and_never_exact(tmp_path: Path) -> None:
    context = begin(tmp_path)
    first = tmp_path / "baseline-a.json"
    duplicate = tmp_path / "baseline-b.json"
    write_matrix(first, context, "baseline")
    write_matrix(duplicate, context, "baseline")
    payload = json.loads(duplicate.read_text())
    payload["generated_at"] = "2026-08-14T00:00:00+00:00"
    duplicate.write_text(json.dumps(payload), encoding="utf-8")

    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[first, duplicate],
    )
    assert receipt["terminal_status"] == "FAILED"
    assert receipt["execution_observation_status"] == "PARTIALLY_OBSERVED"
    assert receipt["identity_match_status"] == "EXPLAINED_MISMATCH"
    assert any(event["field"] == "artifact_set" for event in receipt["resolution_events"])
