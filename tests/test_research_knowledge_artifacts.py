from __future__ import annotations

import json
from pathlib import Path

from app.research.knowledge_artifacts import publish
from app.research.legacy_migration import LegacySource, build_migration
from app.research.observation_ingest import ingest_corpus
from scripts.verify_adaptive_learning import verify


def test_cold_start_knowledge_is_honest_and_verifiable(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output = tmp_path / "artifacts/autonomous_research"
    knowledge = publish(run_date="2026-08-14", ledger_path=ledger, output_root=output)
    assert knowledge["status"] == "INSUFFICIENT_EVIDENCE"
    assert knowledge["observation_funnel"]["adaptive_eligible"] == 0
    assert knowledge["next_phase_gate"]["card_b_allowed"] is False
    assert knowledge["research_only_contract"]["queue_change_allowed"] is False
    result = verify(run_date="2026-08-14", ledger=ledger, output_root=output)
    assert result["status"] == "PASS"


def test_dated_and_latest_are_pointers_to_immutable_canonical(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output = tmp_path / "artifacts/autonomous_research"
    first = publish(run_date="2026-08-14", ledger_path=ledger, output_root=output)
    second = publish(run_date="2026-08-14", ledger_path=ledger, output_root=output)
    assert first["knowledge_id"] == second["knowledge_id"]
    assert json.loads((output / "search_knowledge_2026-08-14.json").read_text()) == json.loads(
        (output / "search_knowledge_latest.json").read_text()
    )


def test_verifier_is_read_only_and_does_not_repair_corrupt_pointer(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output = tmp_path / "artifacts/autonomous_research"
    publish(run_date="2026-08-14", ledger_path=ledger, output_root=output)
    latest = output / "search_knowledge_latest.json"
    latest.write_text('{"corrupt":true}\n', encoding="utf-8")
    before = latest.read_bytes()
    result = verify(run_date="2026-08-14", ledger=ledger, output_root=output)
    assert result["status"] == "FAIL"
    assert latest.read_bytes() == before


def test_verifier_rejects_tampered_pm_answer_without_repair(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=tmp_path / "corpus", ledger_path=ledger)
    output = tmp_path / "artifacts/autonomous_research"
    publish(run_date="2026-08-14", ledger_path=ledger, output_root=output)
    summary = output / "adaptive_learning_summary_2026-08-14.md"
    summary.write_text(summary.read_text().replace("Q2 ADAPTIVE_ELIGIBLE\n\n0", "Q2 ADAPTIVE_ELIGIBLE\n\n999999"))
    before = summary.read_bytes()
    result = verify(run_date="2026-08-14", ledger=ledger, output_root=output)
    assert result["status"] == "FAIL"
    assert "PM_SUMMARY_CONTENT_MISMATCH" in result["errors"]
    assert summary.read_bytes() == before


def test_knowledge_q1_counts_unique_legacy_records_across_manifest_membership(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    first.write_text(json.dumps({"topic_id": "a"}) + "\n")
    second.write_text(json.dumps({"topic_id": "b"}) + "\n")
    corpus = tmp_path / "corpus"
    build_migration(corpus_root=corpus, sources=[LegacySource(first, "RUN_HISTORY_JSONL")])
    build_migration(corpus_root=corpus, sources=[
        LegacySource(first, "RUN_HISTORY_JSONL"), LegacySource(second, "RUN_HISTORY_JSONL")
    ])
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    knowledge = publish(run_date="2026-08-14", ledger_path=ledger, output_root=tmp_path / "out")
    assert knowledge["observation_funnel"]["unique_legacy_records"] == 2
    assert knowledge["observation_funnel"]["legacy_source_record_occurrences"] == 3
