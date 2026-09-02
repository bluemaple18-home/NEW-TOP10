from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_capacity_only_strategy_matrix_harness as harness


def test_bounded_capacity_harness_preserves_canonical_id_parity(tmp_path: Path) -> None:
    work_root = tmp_path / "capacity-run"
    receipt_path = work_root / "receipt.json"

    receipt = harness.run_capacity_probe(
        work_root=work_root,
        output=receipt_path,
        max_scenarios=2,
    )

    assert receipt["schema_version"] == "capacity-only-strategy-matrix-harness.v1"
    assert receipt["boundary"]["purpose"] == "CAPACITY_ONLY"
    assert receipt["boundary"]["research_evidence_status"] == "NOT_RESEARCH_EVIDENCE"
    assert receipt["formal_family"]["expected_count"] == 720
    assert receipt["requested"]["scenario_count"] == 2
    assert receipt["executed"]["scenario_count"] == 2
    assert receipt["parity"]["status"] == "PASS"
    assert receipt["parity"]["requested_executed_match"] is True
    assert receipt["metrics"]["wall_time_seconds"] >= 0
    assert receipt["metrics"]["candidate_per_second"] >= 0
    assert receipt["metrics"]["peak_rss"] >= 0
    assert receipt["io"]["output_sizes"]["matrix_json_bytes"] > 0
    assert receipt["cleanup"]["temp_fixture_removed"] is True
    assert Path(receipt["outputs"]["matrix_json"]).is_relative_to(work_root)
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["parity"]["status"] == "PASS"


def test_parity_attacks_fail_closed() -> None:
    family = harness.formal_family()
    selected = harness.select_requested_scenarios(family, max_scenarios=2)
    requested_ids = [row["combination_id"] for row in selected]
    executed = [row["parameters"] for row in selected]

    duplicate = [executed[0], executed[0]]
    with pytest.raises(ValueError, match="DUPLICATE_EXECUTED_COMBINATION_IDS"):
        harness.validate_requested_executed_parity(
            family=family,
            requested_ids=requested_ids,
            executed_scenarios=duplicate,
        )

    missing = [executed[0]]
    with pytest.raises(ValueError, match="REQUESTED_EXECUTED_MISMATCH"):
        harness.validate_requested_executed_parity(
            family=family,
            requested_ids=requested_ids,
            executed_scenarios=missing,
        )

    extra = [*executed, {"horizon": 99, "stop_loss_pct": None, "take_profit_pct": None, "max_group_exposure": None}]
    with pytest.raises(ValueError, match="UNKNOWN_EXECUTED_COMBINATION_IDS"):
        harness.validate_requested_executed_parity(
            family=family,
            requested_ids=requested_ids,
            executed_scenarios=extra,
        )

    with pytest.raises(ValueError, match="UNKNOWN_REQUESTED_COMBINATION_IDS"):
        harness.select_requested_scenarios(family, requested_ids=[*requested_ids, "sha256:unknown"])


def test_requested_manifest_must_be_complete_canonical_order() -> None:
    family = harness.formal_family()
    canonical_ids = [row["combination_id"] for row in family["combinations"]]

    assert len(harness.select_requested_scenarios(family, requested_ids=canonical_ids)) == 720

    with pytest.raises(ValueError, match="REQUESTED_IDS_NOT_FULL_CANONICAL_FAMILY"):
        harness.select_requested_scenarios(family, requested_ids=canonical_ids[:-1])

    with pytest.raises(ValueError, match="DUPLICATE_REQUESTED_COMBINATION_IDS"):
        harness.select_requested_scenarios(
            family,
            requested_ids=[canonical_ids[0], canonical_ids[0], *canonical_ids[2:]],
        )

    with pytest.raises(ValueError, match="UNKNOWN_REQUESTED_COMBINATION_IDS"):
        harness.select_requested_scenarios(
            family,
            requested_ids=[*canonical_ids[:-1], "sha256:unknown"],
        )

    with pytest.raises(ValueError, match="REQUESTED_IDS_ORDER_MISMATCH"):
        harness.select_requested_scenarios(
            family,
            requested_ids=[canonical_ids[1], canonical_ids[0], *canonical_ids[2:]],
        )


def test_invalid_requested_manifest_does_not_create_work_root(tmp_path: Path) -> None:
    family = harness.formal_family()
    canonical_ids = [row["combination_id"] for row in family["combinations"]]
    work_root = tmp_path / "capacity-run"

    with pytest.raises(ValueError, match="REQUESTED_IDS_NOT_FULL_CANONICAL_FAMILY"):
        harness.run_capacity_probe(
            work_root=work_root,
            output=work_root / "receipt.json",
            requested_ids=canonical_ids[:-1],
        )

    assert not work_root.exists()


def test_capacity_harness_rejects_repo_write_roots(tmp_path: Path) -> None:
    project_root = harness.PROJECT_ROOT.resolve()

    with pytest.raises(ValueError, match="UNSAFE_REPO_WRITE_ROOT"):
        harness.run_capacity_probe(
            work_root=project_root / "artifacts" / "capacity-probe",
            output=tmp_path / "receipt.json",
            max_scenarios=1,
        )

    with pytest.raises(ValueError, match="OUTPUT_OUTSIDE_WORK_ROOT"):
        harness.run_capacity_probe(
            work_root=tmp_path / "capacity-run",
            output=tmp_path / "outside.json",
            max_scenarios=1,
        )

    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_FILE_INSIDE_WORK_ROOT"):
        harness.run_capacity_probe(
            work_root=tmp_path / "capacity-run-output-root",
            output=tmp_path / "capacity-run-output-root",
            max_scenarios=1,
        )

    non_empty = tmp_path / "non-empty"
    non_empty.mkdir()
    (non_empty / "keep.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(ValueError, match="WORK_ROOT_MUST_BE_EMPTY"):
        harness.run_capacity_probe(
            work_root=non_empty,
            output=non_empty / "receipt.json",
            max_scenarios=1,
        )

    with pytest.raises(ValueError, match="UNSAFE_BROAD_WORK_ROOT"):
        harness.ensure_safe_work_root(Path("/"))

    with pytest.raises(ValueError, match="UNSAFE_BROAD_WORK_ROOT"):
        harness.ensure_safe_work_root(Path.home())


def test_capacity_harness_manifest_and_cleanup_schema(tmp_path: Path) -> None:
    receipt = harness.run_capacity_probe(
        work_root=tmp_path / "capacity-run",
        output=tmp_path / "capacity-run" / "receipt.json",
        max_scenarios=1,
    )

    assert receipt["fixture"]["top_n"] == 10
    assert receipt["fixture"]["max_horizon"] == 20
    assert receipt["fixture"]["ranking_file_count"] >= 1
    assert receipt["fixture"]["stock_count"] == 10
    assert receipt["fixture"]["trade_day_count"] >= 22
    assert receipt["io"]["pre_manifest_hash"] == receipt["io"]["post_manifest_hash"]
    assert receipt["io"]["manifest_parity"] == "PASS"
    assert receipt["cleanup"]["status"] == "PASS"
    assert receipt["non_extrapolation_boundary"] == (
        "capacity-only fixture validates harness mechanics; not research-valid workload or full-720 benchmark"
    )


def test_capacity_harness_cleans_fixture_after_runner_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work_root = tmp_path / "capacity-run"

    def boom(_args):
        raise RuntimeError("runner exploded")

    monkeypatch.setattr(harness.strategy_matrix, "build_payload", boom)
    with pytest.raises(RuntimeError, match="runner exploded"):
        harness.run_capacity_probe(
            work_root=work_root,
            output=work_root / "receipt.json",
            max_scenarios=1,
        )

    assert not (work_root / "fixture").exists()
