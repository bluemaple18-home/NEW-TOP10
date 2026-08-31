from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.research.a6_closure import (
    REQUIRED_BRIDGE_FIELDS,
    SOURCE_SURFACE_MANIFEST,
    canonical_closure_receipt,
    bridge_inventory_rows,
    scope_guards,
    scan_source_surfaces,
    validate_bridge_inventory,
    verify_a6_closure,
    verify_new_run_truth,
)
from app.research.run_receipts import finish_topic_attempt
from app.research.legacy_migration import LegacySource, build_migration
from tests.test_autonomous_research_receipts import begin, write_development_authority, write_matrix
from tests.test_research_ledger import corpus_with_receipt
from tests.test_research_legacy_migration import write_matrix as write_legacy_matrix


def _failed_corpus(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    context = begin(root)
    finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[],
        failure_reason="RUNNER_STEP_FAILED",
    )
    return context.root


def _orphan_corpus(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return begin(root).root


def test_bridge_inventory_is_complete_and_machine_checkable() -> None:
    rows = bridge_inventory_rows()
    result = validate_bridge_inventory(rows)
    assert result["status"] == "PASS"
    assert len(rows) >= 10
    assert {field for row in rows for field in REQUIRED_BRIDGE_FIELDS if field in row} == REQUIRED_BRIDGE_FIELDS
    assert all(row["authority"] != "TRUTH_AUTHORITY" for row in rows)
    assert {
        "history_compatibility_projection",
        "legacy_run_history_jsonl_migration",
        "research_map_run_history_backfill",
        "fog_map_run_history_reader",
        "legacy_run_history_appenders",
    }.issubset({row["bridge_id"] for row in rows})


def test_bridge_inventory_rejects_missing_metadata_and_authority_inversion() -> None:
    rows = bridge_inventory_rows()
    rows[0] = {**rows[0], "owner": ""}
    rows[1] = {**rows[1], "authority": "TRUTH_AUTHORITY"}
    result = validate_bridge_inventory(rows)
    assert result["status"] == "FAIL"
    assert "MISSING_OWNER" in result["error_codes"]
    assert "RUN_HISTORY_AUTHORITY_INVERSION" in result["error_codes"]


def test_bridge_inventory_fails_closed_when_a_source_derived_surface_is_omitted() -> None:
    rows = [row for row in bridge_inventory_rows() if row["bridge_id"] != "fog_map_run_history_reader"]
    result = validate_bridge_inventory(rows)
    assert result["status"] == "FAIL"
    assert "MISSING_SOURCE_BRIDGE" in result["error_codes"]


def test_source_scan_fails_closed_when_a_direct_reader_surface_is_unmapped() -> None:
    manifest = dict(SOURCE_SURFACE_MANIFEST)
    del manifest["scripts/verify_research_fog_map.py"]
    scan = scan_source_surfaces(manifest=manifest)
    assert scan["status"] == "FAIL"
    assert "scripts/verify_research_fog_map.py" in scan["unmapped"]


def test_new_run_truth_rejects_cross_file_intent_membership_mismatch(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    attempt_path = next((corpus / "attempts").glob("*.started.json"))
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempt["intent_id"] = "intent-not-in-corpus"
    attempt_path.write_text(json.dumps(attempt), encoding="utf-8")

    result = verify_new_run_truth(corpus_root=corpus)
    assert result["status"] == "FAIL"
    assert any(error["reason"] == "ATTEMPT_INTENT_MEMBERSHIP_MISMATCH" for error in result["errors"])


def test_a6_closure_rebuilds_a1_to_a5_and_history_projection_deterministically(
    tmp_path: Path,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    result = verify_a6_closure(corpus_root=corpus, output_root=tmp_path / "closure")

    assert result["status"] == "PASS"
    assert result["scope_guards"] == {
        "card_b_started": False,
        "card_c_started": False,
        "production_changed": False,
        "scheduler_changed": False,
        "ranking_or_backtest_math_changed": False,
    }
    assert result["rebuild"]["checks"] == {
        "ledger_snapshot_equal": True,
        "input_corpus_hash_equal": True,
        "table_counts_equal": True,
        "eligibility_projection_equal": True,
        "failure_projection_equal": True,
        "learning_projection_equal": True,
        "history_projection_bytes_equal": True,
        "history_projection_manifest_identity_equal": True,
    }
    assert result["rebuild"]["first"]["counts"]["observations"] == 2
    assert result["new_run_truth"]["normal_new_run_backfill_dependency"] is False
    assert result["new_run_truth"]["run_history_truth_authority"] is False
    assert result["bridge_inventory"]["status"] == "PASS"
    assert result["ai_core_proposals"]


def test_a6_closure_fixture_includes_a3_migration_rebuild(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    legacy_source = tmp_path / "legacy" / "matrix.json"
    write_legacy_matrix(legacy_source)
    build_migration(corpus_root=corpus, sources=[LegacySource(legacy_source, "STRATEGY_MATRIX")])

    result = verify_a6_closure(corpus_root=corpus, output_root=tmp_path / "closure")
    assert result["status"] == "PASS"
    assert result["rebuild"]["first"]["counts"]["migration_manifests"] == 1
    assert result["rebuild"]["first"]["counts"]["migrated_records"] == 1


def test_new_run_truth_success_failure_and_orphan_do_not_use_history_or_backfill(
    tmp_path: Path,
) -> None:
    success_corpus, _ = corpus_with_receipt(tmp_path / "success")
    failure_corpus = _failed_corpus(tmp_path / "failure")
    orphan_corpus = _orphan_corpus(tmp_path / "orphan")

    for corpus, expected in (
        (success_corpus, "success"),
        (failure_corpus, "failure"),
        (orphan_corpus, "orphan"),
    ):
        (corpus.parent / "run_history.jsonl").write_text("{not-json}\n", encoding="utf-8")
        result = verify_new_run_truth(corpus_root=corpus)
        assert result["status"] == "PASS"
        assert result["cases"][expected]["status"] == "PASS"
        assert result["run_history_truth_authority"] is False
        assert result["normal_new_run_backfill_dependency"] is False
        assert "run_history" not in result["sources_consumed"]


def test_closure_fails_closed_when_first_party_receipt_is_missing(tmp_path: Path) -> None:
    corpus = _orphan_corpus(tmp_path / "orphan-only")
    result = verify_a6_closure(corpus_root=corpus, output_root=tmp_path / "closure")
    assert result["status"] == "FAIL"
    assert "NEW_RUN_TRUTH_FAIL_CLOSED" in result["error_codes"]


def test_closure_rejects_output_root_that_contains_corpus(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    with pytest.raises(ValueError, match="A6_OUTPUT_ROOT"):
        verify_a6_closure(corpus_root=corpus, output_root=corpus)


def test_closure_rejects_repository_child_as_destructive_output_root(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="A6_OUTPUT_ROOT"):
        verify_a6_closure(corpus_root=corpus, output_root=repository / "app")


def test_scope_guards_are_derived_from_the_candidate_diff() -> None:
    guards = scope_guards(
        base_ref="bb617e98aabefcc52bbf7cb1834fb5fba715d60a",
        candidate_ref="HEAD",
    )
    assert set(guards) == {
        "card_b_started", "card_c_started", "production_changed", "scheduler_changed",
        "ranking_or_backtest_math_changed",
    }
    assert not any(guards.values())


def test_checked_in_closure_receipt_canonically_matches_fixed_fixture_recompute(tmp_path: Path) -> None:
    expected = Path("docs/evidence/CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES/closure_receipt.json")
    actual = tmp_path / "closure_receipt.json"
    completed = subprocess.run(
        [sys.executable, "scripts/verify_research_spine_a6_fixed_fixture.py", "--output", str(actual)],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert canonical_closure_receipt(json.loads(actual.read_text(encoding="utf-8"))) == canonical_closure_receipt(
        json.loads(expected.read_text(encoding="utf-8"))
    )
