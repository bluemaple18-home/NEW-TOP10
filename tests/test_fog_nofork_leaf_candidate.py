"""固定 Fog no-fork 葉節點候選；只驗 validation-only 接點。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.research import batch_owner
from scripts import run_fog_nofork_leaf as leaf_cli
from scripts import run_fog_representative_validation as representative
from scripts.storage_validation import boundary
from tests.test_fog_owned_root import parent_contract
from tests.test_storage_lifecycle_boundaries import tmp_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PINNED_HEAD = "a" * 40


def test_supplied_validation_head_avoids_git_and_round_trips_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", PINNED_HEAD)
    monkeypatch.setattr(
        batch_owner.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("supplied validation head 不得再呼叫 Git"),
    )
    batch_id = "research-2026-08-31-010203-123"
    output = tmp_path / "fixture" / "run.json"
    corpus = tmp_path / "fixture" / "research_spine"
    ledger = tmp_path / "fixture" / "research_ledger.duckdb"
    manager = tmp_path / "fixture"
    runner_argv = [
        str(PROJECT_ROOT / "scripts/run_autonomous_research.py"),
        "--date",
        "2026-08-31",
        "--research-batch-id",
        batch_id,
        "--execute",
        "--output",
        str(output),
    ]

    payload = batch_owner.build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id=batch_id,
        scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=runner_argv,
        output_path=output,
        ledger_path=ledger,
        manager_root=manager,
        requested_research_stage="DEVELOPMENT_SCREEN",
        allowed_research_stages=["DEVELOPMENT_SCREEN"],
        policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
        catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
        execution_epoch="2026-08-31",
        created_at="2026-08-31T00:00:00Z",
        project_head=PINNED_HEAD,
    )
    batch_owner.publish_batch_intent(corpus_root=corpus, payload=payload)

    result = batch_owner.verify_batch_owner_authority(
        project_root=PROJECT_ROOT,
        corpus_root=corpus,
        batch_id=batch_id,
        batch_intent_reference=str(payload["batch_intent_id"]),
        runtime_argv=[
            *runner_argv,
            "--research-batch-intent",
            str(payload["batch_intent_id"]),
        ],
        output_path=output,
        ledger_path=ledger,
        manager_root=manager,
        requested_research_stage="DEVELOPMENT_SCREEN",
        execution_epoch="2026-08-31",
        project_head=PINNED_HEAD,
    )

    assert result.status == "PASS"
    assert payload["project"]["head"] == PINNED_HEAD


def test_supplied_validation_head_must_match_pinned_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", PINNED_HEAD)
    with pytest.raises(batch_owner.BatchOwnerAuthorityError, match="VALIDATION_PROJECT_HEAD_MISMATCH"):
        batch_owner.build_batch_intent(
            project_root=PROJECT_ROOT,
            corpus_root=tmp_path / "spine",
            batch_id="research-2026-08-31-010203-123",
            scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
            runner_argv=[str(PROJECT_ROOT / "scripts/run_autonomous_research.py")],
            output_path=tmp_path / "run.json",
            ledger_path=tmp_path / "ledger.duckdb",
            requested_research_stage="DEVELOPMENT_SCREEN",
            allowed_research_stages=["DEVELOPMENT_SCREEN"],
            policy_path=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
            catalog_path=PROJECT_ROOT / "config/research_parameter_catalog.json",
            execution_epoch="2026-08-31",
            project_head="b" * 40,
        )


def test_fixed_matrix_and_compare_steps_use_callables_without_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []
    original_argv = list(sys.argv)

    def matrix_main(argv: list[str] | None = None) -> int:
        assert argv is not None
        calls.append(("matrix", list(argv)))
        output = Path(argv[argv.index("--output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"scenarios": []}), encoding="utf-8")
        print("matrix-ok")
        return 0

    def compare_main(argv: list[str] | None = None) -> int:
        assert argv is not None
        calls.append(("compare", list(argv)))
        output = Path(argv[argv.index("--output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": []}), encoding="utf-8")
        print("compare-ok")
        return 0

    matrix = SimpleNamespace(main=matrix_main)
    compare = SimpleNamespace(main=compare_main)
    monkeypatch.setitem(sys.modules, "scripts.run_backtest_strategy_matrix", matrix)
    monkeypatch.setitem(sys.modules, "scripts.compare_strategy_matrices", compare)
    monkeypatch.setattr(
        representative.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("no-fork step runner 不得呼叫 subprocess"),
    )

    matrix_output = tmp_path / "matrix.json"
    matrix_step = representative.run_research_step_inprocess(
        "baseline.strategy_matrix",
        [
            sys.executable,
            "scripts/run_backtest_strategy_matrix.py",
            "--output",
            str(matrix_output),
        ],
    )
    compare_output = tmp_path / "comparison.json"
    compare_step = representative.run_research_step_inprocess(
        "compare.strategy_matrices",
        [
            sys.executable,
            "scripts/compare_strategy_matrices.py",
            "--variant",
            f"baseline={matrix_output}",
            "--variant",
            f"candidate={matrix_output}",
            "--output",
            str(compare_output),
        ],
    )

    assert matrix_step["status"] == "OK"
    assert compare_step["status"] == "OK"
    assert calls == [
        ("matrix", ["--output", str(matrix_output)]),
        (
            "compare",
            [
                "--variant",
                f"baseline={matrix_output}",
                "--variant",
                f"candidate={matrix_output}",
                "--output",
                str(compare_output),
            ],
        ),
    ]
    assert sys.argv == original_argv

    blocked = representative.run_research_step_inprocess(
        "unknown",
        [sys.executable, "scripts/arbitrary.py"],
    )
    assert blocked["status"] == "BLOCKED"
    assert len(calls) == 2


@pytest.fixture
def candidate_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_contract) -> tuple[Path, Path]:
    source = tmp_path / "source"
    validation = parent_contract[0]
    (source / "artifacts").mkdir(parents=True)
    (source / "artifacts/market_regime_history.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "trade_date": representative.FIXTURE_DATE,
                        **representative.FIXTURE_IDENTITY,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(representative, "PROJECT_ROOT", source)
    monkeypatch.setattr(representative, "FIXTURE_ROOT", Path("fixture"))
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", PINNED_HEAD)
    return source, validation


def test_prepare_and_execute_share_pinned_plan_and_candidate_runner(
    candidate_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, validation = candidate_roots
    calls: list[tuple[str, str | None, object | None]] = []

    def inprocess(
        command: list[str],
        *,
        project_head: str | None = None,
        step_runner: object | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script = Path(command[1]).name
        calls.append((script, project_head, step_runner))
        if script == "publish_research_batch_intent.py":
            return subprocess.CompletedProcess(command, 0, "sha256:fixed-intent\n", "")
        if script == "run_autonomous_research.py":
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps({"topic_runs": [{"topic": {"topic_id": "fixture"}}]}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "execute\n", "")
        return subprocess.CompletedProcess(command, 0, "verify\n", "")

    monkeypatch.setattr(representative, "run_inprocess", inprocess)
    batch_id = "research-2026-08-31-010203-123"

    assert representative.prepare_nofork_candidate(
        validation_root=validation,
        source_commit=PINNED_HEAD,
        batch_id=batch_id,
    ) == 0
    plan_path = validation / "fixture" / representative.NOFORK_PLAN_NAME
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["source_commit"] == PINNED_HEAD
    assert plan["batch_id"] == batch_id
    assert plan["batch_intent_id"] == "sha256:fixed-intent"

    assert representative.execute_nofork_candidate(
        validation_root=validation,
        source_commit=PINNED_HEAD,
    ) == 0
    assert [name for name, _, _ in calls] == [
        "publish_research_batch_intent.py",
        "run_autonomous_research.py",
        "verify_research_spine_batch.py",
    ]
    assert all(head == PINNED_HEAD for _, head, _ in calls[:2])
    assert calls[1][2] is representative.run_research_step_inprocess
    assert calls[2][2] is None
    final_output = validation / "fixture" / f"fog_representative_validation_{representative.FIXTURE_DATE}.json"
    result = json.loads(final_output.read_text(encoding="utf-8"))
    assert result["production_promotion_allowed"] is False
    assert result["batch_intent_id"] == "sha256:fixed-intent"


def test_execute_rejects_plan_source_identity_change(
    candidate_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, validation = candidate_roots
    monkeypatch.setattr(
        representative,
        "run_inprocess",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            "sha256:fixed-intent\n",
            "",
        ),
    )
    assert representative.prepare_nofork_candidate(
        validation_root=validation,
        source_commit=PINNED_HEAD,
        batch_id="research-2026-08-31-010203-123",
    ) == 0
    plan_path = validation / "fixture" / representative.NOFORK_PLAN_NAME
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["source_commit"] = "b" * 40
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="NOFORK_PLAN_SOURCE_IDENTITY_MISMATCH"):
        representative.execute_nofork_candidate(
            validation_root=validation,
            source_commit=PINNED_HEAD,
        )


def test_leaf_cli_uses_lifecycle_owned_root_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parent_contract,
) -> None:
    root = parent_contract[0]
    seen: list[tuple[str, Path, str]] = []
    monkeypatch.setenv("AI_CORE_TMP_ARTIFACT_ACTIVE", "1")
    monkeypatch.setenv("TMP_ARTIFACT_ROOT", str(root))
    monkeypatch.setattr(
        representative,
        "prepare_nofork_candidate",
        lambda *, validation_root, source_commit: (
            seen.append(("prepare", validation_root, source_commit)) or 0
        ),
    )
    monkeypatch.setattr(
        representative,
        "execute_nofork_candidate",
        lambda *, validation_root, source_commit: (
            seen.append(("execute", validation_root, source_commit)) or 0
        ),
    )
    argv = [
        "prepare",
        "--source-root",
        str(PROJECT_ROOT),
        "--source-commit",
        PINNED_HEAD,
    ]
    assert leaf_cli.main(argv) == 0
    argv[0] = "execute"
    assert leaf_cli.main(argv) == 0
    assert seen == [
        ("prepare", root, PINNED_HEAD),
        ("execute", root, PINNED_HEAD),
    ]


def test_leaf_cli_rejects_direct_invocation_before_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_CORE_TMP_ARTIFACT_ACTIVE", raising=False)
    monkeypatch.delenv("TMP_ARTIFACT_ROOT", raising=False)
    with pytest.raises(SystemExit) as error:
        leaf_cli.main(
            [
                "prepare",
                "--source-root",
                str(PROJECT_ROOT),
                "--source-commit",
                PINNED_HEAD,
            ]
        )
    assert error.value.code == 2


@pytest.mark.parametrize("phase", ["prepare", "execute"])
@pytest.mark.parametrize("entry", ["leaf", "representative"])
@pytest.mark.parametrize("case", ["owner_missing", "volume_missing", "marker_missing", "root_mismatch", "scope_missing", "spoof_tmp"])
def test_nofork_refuses_unowned_root_before_first_writer(parent_contract, monkeypatch, phase, entry, case):
    """沿實際 boundary 拒絕偽造 flag、缺卷或非 exact scope；writer 不得先被呼叫。"""
    root, marker_path, marker = parent_contract
    target = root
    if case == "owner_missing":
        monkeypatch.delenv("AI_CORE_EXTERNAL_DEV_REPO")
    elif case == "volume_missing":
        monkeypatch.setattr(Path, "is_mount", lambda _: False)
    elif case == "marker_missing":
        marker_path.unlink()
    elif case == "root_mismatch":
        target = root.parent / "other"
        target.mkdir()
    elif case == "scope_missing":
        del marker["write_confinement"]
        marker_path.write_text(json.dumps(marker))
        # legacy owned root 可經原 helper 驗證；no-fork 仍須額外要求 exact scope。
        monkeypatch.setattr(representative, "owned_validation_paths", lambda _: root)
    else:
        target = Path("/private/tmp")
        monkeypatch.setenv("TMP_ARTIFACT_ROOT", str(target))
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SOURCE_COMMIT", PINNED_HEAD)
    monkeypatch.setattr(representative, "_prepare_fixture_commands", lambda *_: pytest.fail("拒絕前不得準備 fixture"))
    monkeypatch.setattr(representative, "run_inprocess", lambda *_a, **_k: pytest.fail("拒絕前不得執行 workload"))
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    with pytest.raises((ValueError, OSError)):
        if entry == "leaf":
            # leaf 的 root 只能來自 env；root mismatch 由 owner marker 原路驗出。
            monkeypatch.setenv("TMP_ARTIFACT_ROOT", str(target))
            leaf_cli.main([phase, "--source-root", str(PROJECT_ROOT), "--source-commit", PINNED_HEAD])
        else:
            call = representative.prepare_nofork_candidate if phase == "prepare" else representative.execute_nofork_candidate
            call(validation_root=target, source_commit=PINNED_HEAD)
    assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before
