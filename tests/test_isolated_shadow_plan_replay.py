from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.research import isolated_shadow_plan_replay as replay


EVIDENCE_NAMES = (
    "execution_plan.json",
    "run_receipt.json",
    "batch_intent.json",
    "execution_receipt.json",
    "result.json",
    "final_result.json",
)


def _copy_committed_evidence(tmp_path: Path) -> Path:
    source = replay.PROJECT_ROOT / replay.EVIDENCE_RELATIVE
    for name in EVIDENCE_NAMES:
        payload = replay.load_json(source / name)
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path / "final_result.json"


def _real_inputs(tmp_path: Path) -> dict[str, Path]:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    for role, root in (("baseline", baseline), ("candidate", candidate)):
        for index in range(3):
            (root / f"ranking_2026-01-0{index + 2}.csv").write_text(
                f"symbol,score\n2330,{index + (1 if role == 'candidate' else 0)}\n",
                encoding="utf-8",
            )
    features = tmp_path / "features.parquet"
    features.write_bytes(b"real-fixture-identity")
    history = tmp_path / "regime_history.json"
    history.write_text('{"rows":[]}', encoding="utf-8")
    return {
        "baseline_dir": baseline,
        "candidate_dir": candidate,
        "features": features,
        "regime_history": history,
    }


def test_plan_is_exact_deterministic_two_by_two_matrix(tmp_path: Path) -> None:
    inputs = _real_inputs(tmp_path)
    first = replay.build_execution_plan(**inputs, execution_date="2026-05-12")
    second = replay.build_execution_plan(**inputs, execution_date="2026-05-12")

    assert first == second
    assert replay.validate_execution_plan(first) == []
    assert [(row["role"], row["horizon"]) for row in first["matrix"]] == [
        ("baseline", 10),
        ("baseline", 20),
        ("candidate", 10),
        ("candidate", 20),
    ]
    assert len({row["unit_id"] for row in first["matrix"]}) == 4


def test_plan_rejects_scope_or_parameter_expansion(tmp_path: Path) -> None:
    plan = replay.build_execution_plan(
        **_real_inputs(tmp_path), execution_date="2026-05-12"
    )
    plan["matrix"][0]["scope"] = "RISK_OFF|"
    plan["matrix"][1]["stop_loss_pct"] = 0.12
    plan["plan_id"] = replay.content_hash(plan, omit={"plan_id"})

    assert "SCOPE_EXPANDED" in replay.validate_execution_plan(plan)
    assert "NON_HORIZON_PARAMETER_DRIFT" in replay.validate_execution_plan(plan)


@pytest.mark.parametrize("path", [Path("../proposal.json"), Path("external.json")])
def test_proposal_admission_rejects_non_authoritative_path(path: Path) -> None:
    with pytest.raises(replay.IsolatedReplayError, match="PROPOSAL_NOT_COMMITTED_PATH"):
        replay._require_exact_proposal(path)


def test_authoritative_proposal_admission_passes() -> None:
    payload = replay._require_exact_proposal(replay.PROPOSAL_RELATIVE)

    assert payload["proposal_set_id"] == replay.EXPECTED_PROPOSAL_SET_ID


def test_verifier_requires_all_four_exact_non_sealed_observations(tmp_path: Path) -> None:
    plan = replay.build_execution_plan(
        **_real_inputs(tmp_path), execution_date="2026-05-12"
    )
    units = []
    for index, row in enumerate(plan["matrix"]):
        units.append(
            {
                "execution_unit_id": f"unit-{index}",
                "terminal_status": "SUCCEEDED",
                "observation_status": "OBSERVED",
                "identity_match_status": "EXACT",
                "lineage_resolution_status": "VALID",
                "sealed_usage_status": "PROVEN_NON_SEALED",
                "lineage_id": "baseline-lineage" if row["role"] == "baseline" else "candidate-lineage",
                "horizon": row["horizon"],
                "score": float(row["horizon"]),
                "total_return": float(row["horizon"]) / 100,
                "max_drawdown": -0.1,
                "trade_count": 10,
                "observation_id": f"observation-{index}",
            }
        )
    parity = {"canonical_queue": [], "scheduler": [], "production": []}
    result = replay.verify_result(
        plan=plan,
        units=units,
        capacity={"observed": {"bytes": 1024, "file_count": 4}},
        parity_before=parity,
        parity_after=copy.deepcopy(parity),
    )

    assert result["status"] == "DELIVERED_CANDIDATE"
    assert result["unit_count"] == 4
    assert result["lineage_count"] == 2
    assert len(result["matched_contrasts"]) == 2

    units[0]["sealed_usage_status"] = "UNKNOWN"
    failed = replay.verify_result(
        plan=plan,
        units=units,
        capacity={"observed": {"bytes": 1024, "file_count": 4}},
        parity_before=parity,
        parity_after=parity,
    )
    assert failed["status"] == "NO-GO_EVIDENCE_UNAVAILABLE"
    assert "UNIT_0:SEALED_USAGE_STATUS_MISMATCH" in failed["reason_codes"]


def test_capacity_and_parity_fail_closed(tmp_path: Path) -> None:
    plan = replay.build_execution_plan(
        **_real_inputs(tmp_path), execution_date="2026-05-12"
    )
    result = replay.verify_result(
        plan=plan,
        units=[],
        capacity={"observed": {"bytes": replay.MAX_BYTES + 1, "file_count": 0}},
        parity_before={"queue": "sha256:a"},
        parity_after={"queue": "sha256:b"},
    )

    assert result["status"] == "NO-GO_EVIDENCE_UNAVAILABLE"
    assert "CAPACITY_BUDGET_EXCEEDED" in result["reason_codes"]
    assert "PROTECTED_SURFACE_DRIFT" in result["reason_codes"]


def test_execution_receipt_binds_commands_return_codes_and_attempt() -> None:
    run_receipt = {
        "run_id": "run-" + "a" * 32,
        "intent_id": "intent-" + "b" * 32,
        "attempt_event_id": "sha256:" + "c" * 64,
        "receipt_id": "sha256:" + "d" * 64,
        "terminal_status": "FAILED",
    }
    steps = [
        {
            "name": "baseline.strategy_matrix",
            "status": "FAILED",
            "command": ["python", "scripts/run_backtest_strategy_matrix.py"],
            "returncode": 1,
            "started_at": "2026-08-15T00:00:00+00:00",
            "ended_at": "2026-08-15T00:00:01+00:00",
        }
    ] + [
        {
            "name": name,
            "status": "SKIPPED",
            "command": ["python", script],
            "returncode": None,
            "started_at": "2026-08-15T00:00:01+00:00",
            "ended_at": "2026-08-15T00:00:01+00:00",
        }
        for name, script in (
            ("candidate.strategy_matrix", "scripts/run_backtest_strategy_matrix.py"),
            ("compare.strategy_matrices", "scripts/compare_strategy_matrices.py"),
        )
    ]
    receipt = replay.build_execution_receipt(
        plan_id="sha256:" + "e" * 64,
        batch_id="research-2026-05-12-000000-1",
        batch_intent_id="sha256:" + "f" * 64,
        run_receipt=run_receipt,
        steps=steps,
    )

    assert replay.validate_execution_receipt(receipt) == []
    assert receipt["commands"][0]["return_code"] == 1
    assert receipt["attempt_event_id"] == run_receipt["attempt_event_id"]


def test_evidence_root_is_fixed_to_card_path() -> None:
    with pytest.raises(replay.IsolatedReplayError, match="EVIDENCE_ROOT_NOT_CARD_PATH"):
        replay._authorize_evidence_root(Path("../outside"))


def test_evidence_verifier_rejects_tampered_summary(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": replay.SCHEMA_VERSION,
                "status": "DELIVERED_CANDIDATE",
                "unit_count": 3,
                "lineage_count": 2,
                "matched_contrasts": [],
                "capacity": {"observed": {"bytes": 1, "file_count": 1}},
                "protected_surface_parity": {"unchanged": True, "before": {}, "after": {}},
            }
        ),
        encoding="utf-8",
    )

    report = replay.verify_evidence(path)

    assert report["status"] == "FAIL"
    assert "RESULT_MATRIX_INCOMPLETE" in report["errors"]


def test_evidence_verifier_accepts_formal_runner_no_go(tmp_path: Path) -> None:
    path = _copy_committed_evidence(tmp_path)

    assert replay.verify_evidence(path) == {"status": "PASS", "errors": []}


def test_evidence_verifier_rejects_zero_unit_classification_and_reason_tampering(
    tmp_path: Path,
) -> None:
    path = _copy_committed_evidence(tmp_path)

    payload = replay.load_json(path)
    payload["classification"] = "HORIZON_20_BETTER"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = replay.verify_evidence(path)
    assert "RESULT_CLASSIFICATION_MISMATCH" in report["errors"]

    payload["classification"] = "NO_COMPARISON"
    payload["reason_codes"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = replay.verify_evidence(path)
    assert "RESULT_REASON_CODES_MISMATCH" in report["errors"]

    path.write_text(json.dumps(replay.load_json(tmp_path / "result.json")), encoding="utf-8")
    sibling = replay.load_json(tmp_path / "result.json")
    sibling["classification"] = "MIXED_LINEAGES"
    (tmp_path / "result.json").write_text(json.dumps(sibling), encoding="utf-8")
    report = replay.verify_evidence(path)
    assert "RESULT_FINAL_RESULT_MISMATCH" in report["errors"]


def test_evidence_verifier_rejects_synchronized_identifier_forgery(
    tmp_path: Path,
) -> None:
    path = _copy_committed_evidence(tmp_path)
    run_receipt = replay.load_json(tmp_path / "run_receipt.json")
    run_receipt["run_id"] = "run-" + "f" * 32
    run_receipt["receipt_id"] = replay.content_hash(run_receipt, omit={"receipt_id"})
    (tmp_path / "run_receipt.json").write_text(
        json.dumps(run_receipt), encoding="utf-8"
    )

    execution_receipt = replay.load_json(tmp_path / "execution_receipt.json")
    execution_receipt["run_id"] = run_receipt["run_id"]
    execution_receipt["research_receipt_id"] = run_receipt["receipt_id"]
    execution_receipt["execution_receipt_id"] = replay.content_hash(
        execution_receipt, omit={"execution_receipt_id"}
    )
    (tmp_path / "execution_receipt.json").write_text(
        json.dumps(execution_receipt), encoding="utf-8"
    )

    for name in ("result.json", "final_result.json"):
        result = replay.load_json(tmp_path / name)
        result["run_id"] = run_receipt["run_id"]
        result["receipt_id"] = run_receipt["receipt_id"]
        result["execution_receipt_id"] = execution_receipt["execution_receipt_id"]
        (tmp_path / name).write_text(json.dumps(result), encoding="utf-8")

    report = replay.verify_evidence(path)

    assert "RESULT_RUN_RECEIPT_COMMAND_RUN_MISMATCH" in report["errors"]


@pytest.mark.parametrize(
    ("artifact", "expected_error"),
    [
        ("execution_plan.json", "RESULT_EXECUTION_PLAN_MISSING"),
        ("run_receipt.json", "RESULT_RUN_RECEIPT_MISSING"),
        ("batch_intent.json", "RESULT_BATCH_INTENT_MISSING"),
        ("execution_receipt.json", "RESULT_EXECUTION_RECEIPT_MISSING"),
    ],
)
def test_evidence_verifier_requires_complete_sibling_chain(
    tmp_path: Path, artifact: str, expected_error: str
) -> None:
    path = _copy_committed_evidence(tmp_path)
    (tmp_path / artifact).unlink()

    report = replay.verify_evidence(path)

    assert expected_error in report["errors"]


@pytest.mark.parametrize(
    ("artifact", "field", "value"),
    [
        ("execution_plan.json", "execution_date", "2026-05-13"),
        ("run_receipt.json", "run_id", "run-" + "e" * 32),
        ("batch_intent.json", "batch_id", "research-2026-05-12-000000-1"),
        ("execution_receipt.json", "terminal_status", "SUCCEEDED"),
    ],
)
def test_evidence_verifier_rejects_tampered_sibling_identity(
    tmp_path: Path, artifact: str, field: str, value: str
) -> None:
    path = _copy_committed_evidence(tmp_path)
    sibling_path = tmp_path / artifact
    sibling = replay.load_json(sibling_path)
    sibling[field] = value
    sibling_path.write_text(json.dumps(sibling), encoding="utf-8")

    assert replay.verify_evidence(path)["status"] == "FAIL"
