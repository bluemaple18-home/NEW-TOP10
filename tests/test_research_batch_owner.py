from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from app.research.contracts import content_hash, validate_run_receipt
from app.research.eligibility import build_projection as build_eligibility
from app.research.observation_ingest import ingest_corpus
from app.research.batch_owner import (
    BatchOwnerAuthorityError,
    _git_head,
    build_batch_intent,
    load_batch_intent_reference,
    publish_batch_intent,
    verify_batch_owner_authority,
)
from app.research.receipt_store import ImmutableCollisionError
from app.research.run_receipts import begin_topic_attempt, finish_topic_attempt
from scripts import run_autonomous_research as runner
from scripts.verify_research_spine_batch import verify_batch
from tests.test_autonomous_research_receipts import (
    scenario,
    topic,
    write_development_authority,
    write_matrix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_git_head_accepts_only_validation_pinned_commit_without_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", "a" * 40)
    assert _git_head(tmp_path) == "a" * 40


def test_git_head_rejects_unpinned_no_git_validation_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", "not-a-commit")
    with pytest.raises(BatchOwnerAuthorityError, match="GIT_HEAD_UNAVAILABLE"):
        _git_head(tmp_path)


def test_batch_intent_can_pin_manager_root_separately_from_output_root(
    tmp_path: Path,
) -> None:
    output = tmp_path / "outputs" / "run.json"
    manager_root = tmp_path / "validation-manager"
    payload = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=tmp_path / "research_spine",
        batch_id="research-2026-08-14-010203-123",
        scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=RUN_ARGS,
        output_path=output,
        ledger_path=tmp_path / "research_ledger.duckdb",
        manager_root=manager_root,
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN"],
        policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
        catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
        execution_epoch="2026-08-14",
        created_at="2026-08-14T00:00:00Z",
    )

    assert payload["paths"]["output_root"]["resolved_path"] == str(output.parent)
    assert payload["paths"]["manager_paths"]["registry"]["resolved_path"] == str(
        manager_root / "topic_registry.json"
    )


def test_runner_resolves_distinct_manager_root_from_content_id_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "outputs" / "run.json"
    manager_root = tmp_path / "validation-manager"
    corpus = tmp_path / "research_spine"
    payload = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id="research-2026-08-14-010203-123",
        scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=RUN_ARGS,
        output_path=output,
        ledger_path=tmp_path / "research_ledger.duckdb",
        manager_root=manager_root,
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN"],
        policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
        catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
        execution_epoch="2026-08-14",
        created_at="2026-08-14T00:00:00Z",
    )
    publish_batch_intent(corpus_root=corpus, payload=payload)
    monkeypatch.setattr(runner, "RESEARCH_SPINE_ROOT", corpus)

    write_set = runner.resolve_runner_write_set(
        SimpleNamespace(research_batch_intent=payload["batch_intent_id"]),
        output,
    )

    assert write_set.manager_root == manager_root
    assert write_set.spine_root == corpus
RUN_ARGS = [
    "scripts/run_autonomous_research.py",
    "--date",
    "2026-08-14",
    "--research-batch-id",
    "research-2026-08-14-010203-123",
    "--execute",
    "--closed-regime-research",
    "--development-screen-on-sealed-exhaustion",
    "--output",
    "artifacts/autonomous_research/autonomous_research_daily_quota_2026-08-14.json",
]


def _intent(
    tmp_path: Path,
    *,
    execution_epoch: str = "2026-08-14",
    scheduler_entrypoint: Path | None = None,
    runner_argv: list[str] | None = None,
    output_path: Path | None = None,
    manager_root: Path | None = None,
) -> tuple[Path, dict[str, object]]:
    corpus = tmp_path / "research_spine"
    output = output_path or PROJECT_ROOT / "artifacts/autonomous_research/autonomous_research_daily_quota_2026-08-14.json"
    payload = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id="research-2026-08-14-010203-123",
        scheduler_entrypoint=scheduler_entrypoint or PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=runner_argv or RUN_ARGS,
        output_path=output,
        ledger_path=PROJECT_ROOT / "data/research/research_ledger.duckdb",
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN", "COARSE_SCREEN"],
        policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
        catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
        execution_epoch=execution_epoch,
        created_at="2026-08-14T00:00:00Z",
    )
    if manager_root is not None:
        manager_paths = payload["paths"]["manager_paths"]  # type: ignore[index]
        for name, relative in {
            "topic_bank": "topic_bank.json",
            "registry": "topic_registry.json",
            "history": "run_history.json",
            "queue": "next_action_queue.json",
            "summary": "manager_summary.json",
            "runner_registry": "runner_registry.json",
        }.items():
            target = manager_root / relative
            manager_paths[name] = {
                "repo_path": str(target.resolve(strict=False)),
                "resolved_path": str(target.resolve(strict=False)),
            }
        payload["batch_intent_id"] = content_hash(payload, omit={"batch_intent_id"})
    publish_batch_intent(corpus_root=corpus, payload=payload)
    return corpus, payload


def _republish(corpus: Path, payload: dict[str, object]) -> dict[str, object]:
    payload["batch_intent_id"] = content_hash(payload, omit={"batch_intent_id"})
    publish_batch_intent(corpus_root=corpus, payload=payload)
    return payload


def _verify(corpus: Path, reference: str | None) -> None:
    verify_batch_owner_authority(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id="research-2026-08-14-010203-123",
        batch_intent_reference=reference,
        runtime_argv=[*RUN_ARGS, "--research-batch-intent", reference or ""],
        output_path=PROJECT_ROOT / "artifacts/autonomous_research/autonomous_research_daily_quota_2026-08-14.json",
        ledger_path=PROJECT_ROOT / "data/research/research_ledger.duckdb",
        manager_root=PROJECT_ROOT / "artifacts/autonomous_research",
        requested_research_stage="DEVELOPMENT_SCREEN",
        execution_epoch="2026-08-14",
    )


def test_regex_valid_batch_id_without_intent_fails_for_canonical_write_set(tmp_path: Path) -> None:
    with pytest.raises(BatchOwnerAuthorityError, match="MISSING_BATCH_INTENT"):
        verify_batch_owner_authority(
            project_root=PROJECT_ROOT,
            corpus_root=PROJECT_ROOT / "artifacts/autonomous_research/research_spine",
            batch_id="research-2026-08-14-010203-123",
            batch_intent_reference=None,
            runtime_argv=RUN_ARGS,
            output_path=PROJECT_ROOT / "artifacts/autonomous_research/fixture.json",
            ledger_path=PROJECT_ROOT / "data/research/research_ledger.duckdb",
            manager_root=PROJECT_ROOT / "artifacts/autonomous_research",
            requested_research_stage="DEVELOPMENT_SCREEN",
            execution_epoch="2026-08-14",
        )


def test_complete_isolated_write_set_can_run_without_canonical_intent(tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    result = verify_batch_owner_authority(
        project_root=PROJECT_ROOT,
        corpus_root=isolated / "research_spine",
        batch_id="UNSCOPED",
        batch_intent_reference=None,
        runtime_argv=RUN_ARGS,
        output_path=isolated / "run.json",
        ledger_path=isolated / "research_ledger.duckdb",
        manager_root=isolated,
        requested_research_stage="DEVELOPMENT_SCREEN",
        execution_epoch="2026-08-14",
    )
    assert result.reason_code == "ISOLATED_WRITE_SET"


def test_partial_canonical_or_symlink_write_set_fails_without_intent(tmp_path: Path) -> None:
    with pytest.raises(BatchOwnerAuthorityError, match="MISSING_BATCH_INTENT"):
        verify_batch_owner_authority(
            project_root=PROJECT_ROOT,
            corpus_root=PROJECT_ROOT / "artifacts/autonomous_research/research_spine",
            batch_id="research-2026-08-14-010203-123",
            batch_intent_reference=None,
            runtime_argv=RUN_ARGS,
            output_path=tmp_path / "run.json",
            ledger_path=tmp_path / "research_ledger.duckdb",
            manager_root=tmp_path,
            requested_research_stage="DEVELOPMENT_SCREEN",
            execution_epoch="2026-08-14",
        )

    symlink_root = tmp_path / "link"
    os.symlink(PROJECT_ROOT / "artifacts", symlink_root)
    with pytest.raises(BatchOwnerAuthorityError, match="MISSING_BATCH_INTENT"):
        verify_batch_owner_authority(
            project_root=PROJECT_ROOT,
            corpus_root=symlink_root / "research_spine",
            batch_id="research-2026-08-14-010203-123",
            batch_intent_reference=None,
            runtime_argv=RUN_ARGS,
            output_path=tmp_path / "run.json",
            ledger_path=tmp_path / "research_ledger.duckdb",
            manager_root=tmp_path,
            requested_research_stage="DEVELOPMENT_SCREEN",
            execution_epoch="2026-08-14",
        )


def test_exact_daily_batch_owner_intent_passes(tmp_path: Path) -> None:
    corpus, payload = _intent(tmp_path)
    _verify(corpus, str(payload["batch_intent_id"]))


def test_forged_scheduler_entrypoint_owner_and_hash_fail_closed(tmp_path: Path) -> None:
    corpus, forged_entrypoint = _intent(tmp_path / "runner-entrypoint")
    forged_entrypoint["scheduler"]["entrypoint"] = "scripts/run_autonomous_research.py"  # type: ignore[index]
    forged_entrypoint["scheduler"]["entrypoint_hash"] = content_hash({"fake": "runner"})  # type: ignore[index]
    forged_entrypoint = _republish(corpus, forged_entrypoint)
    with pytest.raises(BatchOwnerAuthorityError, match="SCHEDULER_ENTRYPOINT_MISMATCH"):
        _verify(corpus, str(forged_entrypoint["batch_intent_id"]))

    corpus, forged_owner = _intent(tmp_path / "wrong-owner")
    forged_owner["scheduler"]["owner"] = "manual_runner"  # type: ignore[index]
    forged_owner = _republish(corpus, forged_owner)
    with pytest.raises(BatchOwnerAuthorityError, match="SCHEDULER_OWNER_MISMATCH"):
        _verify(corpus, str(forged_owner["batch_intent_id"]))

    corpus, stale_hash = _intent(tmp_path / "stale-hash")
    stale_hash["scheduler"]["entrypoint_hash"] = "sha256:" + "0" * 64  # type: ignore[index]
    stale_hash = _republish(corpus, stale_hash)
    with pytest.raises(BatchOwnerAuthorityError, match="SCHEDULER_ENTRYPOINT_HASH_MISMATCH"):
        _verify(corpus, str(stale_hash["batch_intent_id"]))


def test_publisher_cli_does_not_expose_scheduler_authoring_surface(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/publish_research_batch_intent.py",
            "--batch-id",
            "research-2026-08-14-010203-123",
            "--execution-epoch",
            "2026-08-14",
            "--requested-research-stage",
            "DEVELOPMENT_SCREEN",
            "--allowed-research-stage",
            "DEVELOPMENT_SCREEN",
            "--allowed-research-stage",
            "COARSE_SCREEN",
            "--output",
            str(tmp_path / "run.json"),
            "--corpus-root",
            str(tmp_path / "research_spine"),
            "--ledger",
            str(tmp_path / "research_ledger.duckdb"),
            "--scheduler",
            "scripts/run_autonomous_research.py",
            "--",
            *RUN_ARGS,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not (tmp_path / "research_spine" / "batch_intents").exists()


def test_publisher_cli_rejects_distinct_manager_root_outside_validation(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "research_spine"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/publish_research_batch_intent.py",
            "--batch-id",
            "research-2026-08-14-010203-123",
            "--execution-epoch",
            "2026-08-14",
            "--requested-research-stage",
            "DEVELOPMENT_SCREEN",
            "--allowed-research-stage",
            "DEVELOPMENT_SCREEN",
            "--output",
            str(tmp_path / "run.json"),
            "--corpus-root",
            str(corpus),
            "--ledger",
            str(tmp_path / "research_ledger.duckdb"),
            "--manager-root",
            str(tmp_path / "manager"),
            "--",
            *RUN_ARGS,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not (corpus / "batch_intents").exists()


def test_copied_stale_or_mismatched_intent_fails_closed(tmp_path: Path) -> None:
    corpus, payload = _intent(tmp_path, execution_epoch="2026-08-13")
    with pytest.raises(BatchOwnerAuthorityError, match="EXECUTION_EPOCH_MISMATCH"):
        _verify(corpus, str(payload["batch_intent_id"]))

    fresh_corpus, fresh = _intent(tmp_path / "fresh")
    with pytest.raises(BatchOwnerAuthorityError, match="RUNNER_ARGV_MISMATCH"):
        verify_batch_owner_authority(
            project_root=PROJECT_ROOT,
            corpus_root=fresh_corpus,
            batch_id="research-2026-08-14-010203-123",
            batch_intent_reference=str(fresh["batch_intent_id"]),
            runtime_argv=[*RUN_ARGS, "--max-topics", "999", "--research-batch-intent", str(fresh["batch_intent_id"])],
            output_path=PROJECT_ROOT / "artifacts/autonomous_research/autonomous_research_daily_quota_2026-08-14.json",
            ledger_path=PROJECT_ROOT / "data/research/research_ledger.duckdb",
            manager_root=PROJECT_ROOT / "artifacts/autonomous_research",
            requested_research_stage="DEVELOPMENT_SCREEN",
            execution_epoch="2026-08-14",
        )


def test_missing_path_body_mismatch_and_collision_intents_fail_closed(tmp_path: Path) -> None:
    corpus, payload = _intent(tmp_path)
    with pytest.raises(BatchOwnerAuthorityError, match="BATCH_INTENT_MISSING"):
        load_batch_intent_reference(corpus, "sha256:" + "0" * 64)

    wrong = corpus / "batch_intents" / ("f" * 64 + ".json")
    wrong.write_text((corpus / "batch_intents" / f"{str(payload['batch_intent_id'])[7:]}.json").read_text())
    with pytest.raises(BatchOwnerAuthorityError, match="BATCH_INTENT_PATH_BODY_MISMATCH"):
        load_batch_intent_reference(corpus, str(wrong))

    collision = corpus / "batch_intents" / f"{str(payload['batch_intent_id'])[7:]}.json"
    collision.write_text('{"different":true}\n', encoding="utf-8")
    with pytest.raises(ImmutableCollisionError):
        publish_batch_intent(corpus_root=corpus, payload=payload)


def test_runner_authority_gate_happens_before_output_or_manager_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "canonical-output.json"
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "scripts/run_autonomous_research.py",
            "--date",
            "2026-08-14",
            "--research-batch-id",
            "research-2026-08-14-010203-123",
            "--execute",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(runner, "PROJECT_ROOT", PROJECT_ROOT)
    monkeypatch.setattr(runner, "OUTPUT_DIR", PROJECT_ROOT / "artifacts/autonomous_research")
    assert runner.main() == 1
    assert not output.exists()


def test_runner_rejects_forged_scheduler_before_body_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "autonomous_research"
    output = output_dir / "autonomous_research_daily_quota_2026-08-14.json"
    raw_argv = [
        "scripts/run_autonomous_research.py",
        "--date",
        "2026-08-14",
        "--research-batch-id",
        "research-2026-08-14-010203-123",
        "--execute",
        "--closed-regime-research",
        "--development-screen-on-sealed-exhaustion",
        "--output",
        str(output),
    ]
    corpus, payload = _intent(
        output_dir,
        runner_argv=raw_argv,
        output_path=output,
        manager_root=output_dir,
    )
    payload["scheduler"]["entrypoint"] = "scripts/run_autonomous_research.py"  # type: ignore[index]
    payload["scheduler"]["entrypoint_hash"] = content_hash({"fake": "runner"})  # type: ignore[index]
    payload = _republish(corpus, payload)
    batch_intent_id = str(payload["batch_intent_id"])
    args = SimpleNamespace(
        date="2026-08-14",
        output=str(output),
        research_batch_id="research-2026-08-14-010203-123",
        research_batch_intent=batch_intent_id,
        execute=True,
        development_screen_on_sealed_exhaustion=True,
    )
    reached_body = False

    def fail_if_body_runs(*_args: object, **_kwargs: object) -> list[object]:
        nonlocal reached_body
        reached_body = True
        raise AssertionError("runner body must not run after scheduler authority refusal")

    monkeypatch.setattr(runner, "PROJECT_ROOT", PROJECT_ROOT)
    monkeypatch.setattr(runner, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(runner, "parse_args", lambda: args)
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [*raw_argv, "--research-batch-intent", batch_intent_id],
    )
    monkeypatch.setattr(runner, "generate_all_topics", fail_if_body_runs)

    assert runner.main() == 1
    assert reached_body is False
    assert not output.exists()
    assert not (output_dir / "topic_bank.json").exists()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tree_inventory(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        return {"exists": True, "kind": "file", "hash": _hash_file(path)}
    files = {
        item.relative_to(path).as_posix(): _hash_file(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
    return {"exists": True, "kind": "directory", "files": files}


def _canonical_research_inventory() -> dict[str, object]:
    policy = json.loads(
        (PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json").read_text(
            encoding="utf-8"
        )
    )
    relative_paths = {
        "artifacts/autonomous_research/research_spine",
        "artifacts/autonomous_research/topic_bank.json",
        "artifacts/autonomous_research/topic_registry.json",
        "artifacts/autonomous_research/run_history.json",
        "artifacts/autonomous_research/next_action_queue.json",
        "artifacts/autonomous_research/manager_summary.json",
        "artifacts/autonomous_research/runner_registry.json",
        "data/research/research_ledger.duckdb",
    }
    for group in ("production_paths", "storage_write_paths"):
        for row in policy["baseline_inventory"][group]:
            relative_paths.add(row["path"])
    return {
        relative: _tree_inventory(PROJECT_ROOT / relative)
        for relative in sorted(relative_paths)
    }


def _write_observed_matrix(path: Path, context: object, role: str) -> None:
    write_matrix(path, context, role)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["scenarios"][0].update(
        {
            "scenario_id": "h5_sl0p08_tp0p15_gc0p35",
            "total_return": 0.08,
            "max_drawdown": -0.12,
            "win_rate": 0.55,
            "avg_trade_return": 0.01,
            "trade_count": 25,
            "score": 0.2,
            "p_value": 0.04,
            "robust_neighbor_pass_count": 0,
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_runner_keyboard_interrupt_emits_single_cancelled_receipt_with_first_party_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cancelled"
    output_root = root / "output"
    corpus = root / "spine"
    ledger = root / "ledger" / "research_ledger.duckdb"
    output_root.mkdir(parents=True, exist_ok=True)
    (root / "features.parquet").write_bytes(b"fixture")
    baseline_dir = root / "baseline"
    candidate_dir = root / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    (baseline_dir / "ranking_2026-01-02.csv").write_text("symbol,score\nA,1\n", encoding="utf-8")
    (candidate_dir / "ranking_2026-01-02.csv").write_text("symbol,score\nA,2\n", encoding="utf-8")

    batch_id = "research-2026-08-14-010203-123"
    output = output_root / "autonomous_research_daily_quota_2026-08-14.json"
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
        str(root / "features.parquet"),
        "--execute-topic-count",
        "1",
        "--development-screen-topic-count",
        "1",
        "--max-topics",
        "1",
    ]
    batch_intent = build_batch_intent(
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
        created_at="2026-08-14T00:00:00Z",
    )
    publish_batch_intent(corpus_root=corpus, payload=batch_intent)

    selected_topic = runner.ResearchTopic(
        topic_id="test:cancel:development_screen",
        title="Keyboard interrupt canary",
        hypothesis="cancel path writes first-party evidence",
        validation_plan="stub raises KeyboardInterrupt",
        runner="strategy_matrix_comparison",
        candidate_dir=str(candidate_dir),
        baseline_dir=str(baseline_dir),
        score=1.0,
        reasons=["canary"],
        evidence_sources=[],
        ranking_file_count=1,
        validation_profile="canary",
        horizons="5",
        stop_loss_pcts="0.08",
        take_profit_pcts="0.15",
        max_group_exposures="0.35",
        regime_identity={"regime_id": "RISK_OFF|"},
        selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
    )

    def interrupting_execute_topic(args, active_topic, run_dir, *, on_execution_started=None, receipt_attempt=None):
        assert receipt_attempt is not None
        if on_execution_started is not None:
            on_execution_started()
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "build_daily_source_lineage", lambda **_: {"source": "canary"})
    monkeypatch.setattr(runner, "generate_all_topics", lambda args: [selected_topic])
    monkeypatch.setattr(runner, "apply_closed_experiment_capacity", lambda topics, args: topics)
    monkeypatch.setattr(runner, "execute_topic", interrupting_execute_topic)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            *runner_argv,
            "--research-batch-intent",
            str(corpus / "batch_intents" / f"{str(batch_intent['batch_intent_id']).removeprefix('sha256:')}.json"),
        ],
    )

    with pytest.raises(KeyboardInterrupt):
        runner.main()

    receipt_paths = list((corpus / "receipts").glob("*.json"))
    assert len(receipt_paths) == 1
    receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    assert validate_run_receipt(receipt) == []
    assert receipt["terminal_status"] == "CANCELLED"
    assert receipt["terminal_cause"]["reason_code"] == "INTERRUPTED_BY_USER"
    assert receipt["terminal_cause"]["observer"] == "autonomous-research-keyboard-interrupt-handler"
    assert receipt["terminal_cause"]["status_evidence"] == {
        "cancellation_request_id": f"keyboard-interrupt:{receipt['run_id']}",
        "accepted_at": receipt["terminal_cause"]["observed_at"],
        "typed_reason": "INTERRUPTED_BY_USER",
    }
    assert verify_batch(corpus_root=corpus, batch_id=batch_id)["receipt_count"] == 1


def test_isolated_native_evidence_batch_owner_canary_is_exact_idempotent_and_noncanonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _canonical_research_inventory()
    root = tmp_path / "canary"
    output_root = root / "output"
    corpus = root / "spine"
    ledger = root / "ledger" / "research_ledger.duckdb"
    logs = root / "logs"
    matrix_root = root / "matrix"
    comparison_root = root / "comparison"
    eligibility_root = root / "eligibility"
    for directory in (output_root, logs, matrix_root, comparison_root, eligibility_root):
        directory.mkdir(parents=True, exist_ok=True)
    (root / "features.parquet").write_bytes(b"fixture")
    baseline_dir = root / "baseline"
    candidate_dir = root / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    (baseline_dir / "ranking_2026-01-02.csv").write_text("symbol,score\nA,1\n", encoding="utf-8")
    (candidate_dir / "ranking_2026-01-02.csv").write_text("symbol,score\nA,2\n", encoding="utf-8")

    batch_id = "research-2026-08-14-010203-123"
    output = output_root / "autonomous_research_daily_quota_2026-08-14.json"
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
        str(root / "features.parquet"),
        "--execute-topic-count",
        "1",
        "--development-screen-topic-count",
        "1",
        "--max-topics",
        "1",
    ]
    batch_intent = build_batch_intent(
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
        created_at="2026-08-14T00:00:00Z",
    )
    publish_batch_intent(corpus_root=corpus, payload=batch_intent)

    selected_topic = runner.ResearchTopic(
        topic_id="test:receipt:development_screen",
        title="Native evidence canary",
        hypothesis="tmp-root evidence closes through the real Runner",
        validation_plan="stub only expensive matrix subprocesses",
        runner="strategy_matrix_comparison",
        candidate_dir=str(candidate_dir),
        baseline_dir=str(baseline_dir),
        score=1.0,
        reasons=["canary"],
        evidence_sources=[],
        ranking_file_count=1,
        validation_profile="canary",
        horizons="5",
        stop_loss_pcts="0.08",
        take_profit_pcts="0.15",
        max_group_exposures="0.35",
        regime_identity={"regime_id": "RISK_OFF|"},
        selection_rationale={"research_stage": "DEVELOPMENT_SCREEN"},
    )

    def fake_execute_topic(args, active_topic, run_dir, *, on_execution_started=None, receipt_attempt=None):
        assert receipt_attempt is not None
        assert active_topic.topic_id == selected_topic.topic_id
        if on_execution_started is not None:
            on_execution_started()
        run_dir.mkdir(parents=True, exist_ok=True)
        slug = runner.slugify(active_topic.topic_id)
        baseline = run_dir / f"{slug}_baseline_strategy_matrix.json"
        candidate = run_dir / f"{slug}_candidate_strategy_matrix.json"
        development_authority = run_dir / f"{slug}_development_screen_contract.json"
        _write_observed_matrix(baseline, receipt_attempt, "baseline")
        _write_observed_matrix(candidate, receipt_attempt, "candidate")
        write_development_authority(development_authority, receipt_attempt)
        return (
            [
                {"name": "baseline.strategy_matrix", "status": "OK"},
                {"name": "candidate.strategy_matrix", "status": "OK"},
                {"name": "compare.strategy_matrices", "status": "OK"},
            ],
            {"decision": "PARTIAL_SCORE_ONLY", "promotion_allowed": False},
            {
                "baseline_strategy_matrix": str(baseline),
                "candidate_strategy_matrix": str(candidate),
                "development_screen_contract": str(development_authority),
            },
        )

    monkeypatch.setattr(runner, "build_daily_source_lineage", lambda **_: {"source": "canary"})
    monkeypatch.setattr(runner, "generate_all_topics", lambda args: [selected_topic])
    monkeypatch.setattr(runner, "apply_closed_experiment_capacity", lambda topics, args: topics)
    monkeypatch.setattr(runner, "execute_topic", fake_execute_topic)
    monkeypatch.setattr(runner, "OUTPUT_DIR", runner.OUTPUT_DIR)
    monkeypatch.setattr(runner, "RESEARCH_LEDGER_PATH", runner.RESEARCH_LEDGER_PATH)
    monkeypatch.setattr(runner, "RESEARCH_SPINE_ROOT", runner.RESEARCH_SPINE_ROOT)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            *runner_argv,
            "--research-batch-intent",
            str(corpus / "batch_intents" / f"{str(batch_intent['batch_intent_id']).removeprefix('sha256:')}.json"),
        ],
    )
    assert runner.main() == 0

    assert len(list((corpus / "batch_intents").glob("*.json"))) == 1
    assert len(list((corpus / "intents").glob("*.json"))) == 1
    assert len(list((corpus / "attempts").glob("*.started.json"))) == 1
    assert len(list((corpus / "receipts").glob("*.json"))) == 1
    attempt = json.loads(
        next((corpus / "attempts").glob("*.started.json")).read_text(encoding="utf-8")
    )
    receipt = json.loads(next((corpus / "receipts").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["terminal_status"] == "SUCCEEDED"
    assert receipt["execution_observation_status"] == "OBSERVED"
    assert receipt["identity_match_status"] == "EXACT"
    assert attempt["executor"]["research_batch_id"] == batch_id
    assert len(receipt["executed_units"]) == 2
    assert set(receipt["requested"]["trial_spec_ids"]) == {
        unit["requested_trial_spec_id"] for unit in receipt["executed_units"]
    }
    assert all(
        unit["lineage_resolution_status"] == "VALID"
        and unit["lineage"]["sealed_usage_status"] == "PROVEN_NON_SEALED"
        for unit in receipt["executed_units"]
    )
    assert verify_batch(corpus_root=corpus, batch_id=batch_id)["status"] == "PASS"

    first_ingest = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    second_ingest = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        observation_count = connection.execute("SELECT count(*) FROM observations").fetchone()[0]
    finally:
        connection.close()
    assert first_ingest.observations_inserted == len(receipt["executed_units"])
    assert second_ingest.observations_inserted == 0
    assert observation_count == len(receipt["executed_units"])

    eligibility = build_eligibility(ledger_path=ledger, output_root=eligibility_root)
    assert eligibility["counts"] == {"ADAPTIVE_ELIGIBLE": observation_count}
    assert all(
        decision["eligibility_status"] == "ADAPTIVE_ELIGIBLE"
        and decision["evidence_weight"] == 1
        for decision in eligibility["decisions"]
    )

    control_ledger = root / "control" / "sealed_unknown.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=control_ledger)
    connection = duckdb.connect(str(control_ledger))
    try:
        units = [
            row[0]
            for row in connection.execute(
                "SELECT execution_unit_id FROM execution_units ORDER BY 1"
            ).fetchall()
        ]
        connection.execute(
            "UPDATE execution_units SET sealed_usage_status='SEALED' WHERE execution_unit_id=?",
            [units[0]],
        )
        connection.execute(
            "UPDATE execution_units SET sealed_usage_status='UNKNOWN' WHERE execution_unit_id=?",
            [units[1]],
        )
    finally:
        connection.close()
    control = build_eligibility(
        ledger_path=control_ledger,
        output_root=root / "control" / "eligibility",
    )
    assert control["counts"] == {"INVALID_LINEAGE": 1, "SEALED_VALIDATION_ONLY": 1}
    assert sum(item["evidence_weight"] for item in control["decisions"]) == 0

    for path in (output, corpus, ledger, output_root, logs, matrix_root, comparison_root, eligibility_root):
        assert path.resolve(strict=False).is_relative_to(root.resolve(strict=True))
    assert _canonical_research_inventory() == before
