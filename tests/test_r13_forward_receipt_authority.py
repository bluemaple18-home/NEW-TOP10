from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from app.research import r13_forward_receipt_authority as authority
from app.research import ranking_provenance_admission as admission
from app.research import ranking_provenance_receipt as receipts


def _git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "Test")


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _hash(raw: bytes) -> str:
    return receipts.sha256_bytes(raw).removeprefix("sha256:")


def _rehash_receipt(payload: dict) -> bytes:
    payload["receipt_identity"] = receipts.content_hash(
        {key: value for key, value in payload.items() if key != "receipt_identity"}
    )
    return receipts.canonical_encode(payload)


def _rehash_manifest(payload: dict) -> bytes:
    payload["manifest_identity"] = receipts.content_hash(
        {key: value for key, value in payload.items() if key != "manifest_identity"}
    )
    return receipts.canonical_encode(payload)


def _fixture(project: Path, *, commit: bool = True) -> authority._AuthorityContract:
    output_root = "artifacts/out"
    run_identity = "fixture-run"
    run_root = f"{output_root}/.ranking-provenance-v1/runs/{run_identity}"
    ranking_path = f"{output_root}/ranking_2026-09-01.csv"
    receipt_path = f"{run_root}/receipts/ranking_2026-09-01.receipt.json"
    model_path = f"{run_root}/model_snapshots/model-a.pkl"
    manifest_path = f"{run_root}/COMPLETE.manifest.json"
    ranking_raw = b"rank,stock_id,score\n1,1101,2\n2,2330,1\n"
    model_raw = b"model-fixture\n"
    batch_plan_id = receipts.batch_plan_id(
        run_identity=run_identity,
        scenario="fixture_forward",
        producer_entrypoint="scripts/producer.py",
        planned_rankings=["ranking_2026-09-01.csv"],
    )
    receipt = {
        "schema_version": receipts.SCHEMA_VERSION,
        "scenario": "fixture_forward",
        "ranking_date": "2026-09-01",
        "run_identity": run_identity,
        "batch_plan_id": batch_plan_id,
        "capture_mode": receipts.FORWARD_CAPTURE,
        "admission_eligible": "pending_registration",
        "ranking_artifact": {
            "path": ranking_path,
            "sha256": receipts.sha256_bytes(ranking_raw),
        },
        "producer": {
            "entrypoint": "scripts/producer.py",
            "source_commit": "a" * 40,
            "dependencies": [
                {"path": "scripts/producer.py", "sha256": "sha256:" + "1" * 64}
            ],
        },
        "model": {
            "path": model_path,
            "version": "model-a.pkl",
            "sha256": receipts.sha256_bytes(model_raw),
        },
        "config": {"path": "inputs/config.yaml", "sha256": "sha256:" + "2" * 64},
        "universe": {"path": "inputs/universe.parquet", "sha256": "sha256:" + "3" * 64},
        "feature_calendar": {"path": "inputs/features.parquet", "sha256": "sha256:" + "4" * 64},
        "top_n_policy": {
            "top_n": 2,
            "sort_policy": "score_desc",
            "tie_break_policy": "stock_id_asc",
            "rank_policy": "continuous_1_based",
            "score_column": "score",
        },
        "strict_inputs": {
            "market_regime_history": {"path": "inputs/regime.json", "sha256": "sha256:" + "5" * 64},
            "industry_map": {"path": "inputs/industry.csv", "sha256": "sha256:" + "6" * 64},
            "calendar_schedule_source": {"path": "inputs/calendar.csv", "sha256": "sha256:" + "7" * 64},
            "completed_trade_date_authority": {"path": "inputs/authority.json", "sha256": "sha256:" + "8" * 64},
        },
        "receipt_identity": "",
    }
    receipt_raw = _rehash_receipt(receipt)
    manifest = {
        "schema_version": receipts.MANIFEST_SCHEMA_VERSION,
        "status": "COMPLETE",
        "run_identity": run_identity,
        "batch_plan_id": batch_plan_id,
        "scenario": "fixture_forward",
        "producer_entrypoint": "scripts/producer.py",
        "capture_mode": receipts.FORWARD_CAPTURE,
        "entries": [
            {
                "ranking_date": "2026-09-01",
                "ranking_artifact": receipt["ranking_artifact"],
                "receipt": {
                    "path": receipt_path,
                    "sha256": receipts.sha256_bytes(receipt_raw),
                    "receipt_identity": receipt["receipt_identity"],
                },
            }
        ],
        "input_hashes_before": {"x": {"path": "inputs/x", "sha256": "sha256:" + "9" * 64}},
        "input_hashes_after": {"x": {"path": "inputs/x", "sha256": "sha256:" + "9" * 64}},
        "planned_rankings": ["ranking_2026-09-01.csv"],
        "manifest_identity": "",
    }
    manifest_raw = _rehash_manifest(manifest)
    _write(project / ranking_path, ranking_raw)
    _write(project / model_path, model_raw)
    _write(project / receipt_path, receipt_raw)
    _write(project / manifest_path, manifest_raw)
    _git(project, "add", ".")
    if commit:
        _git(project, "commit", "-qm", "fixture")
    return authority._AuthorityContract(
        output_root=output_root,
        manifest_path=manifest_path,
        scenario="fixture_forward",
        ranking_date="2026-09-01",
        run_identity=run_identity,
        batch_plan_id=batch_plan_id,
        manifest_identity=manifest["manifest_identity"],
        receipt_identity=receipt["receipt_identity"],
        capture_mode=receipts.FORWARD_CAPTURE,
        admission_eligible="pending_registration",
        expected_files=(
            authority._ExpectedFile(manifest_path, len(manifest_raw), _hash(manifest_raw)),
            authority._ExpectedFile(receipt_path, len(receipt_raw), _hash(receipt_raw)),
            authority._ExpectedFile(model_path, len(model_raw), _hash(model_raw)),
            authority._ExpectedFile(ranking_path, len(ranking_raw), _hash(ranking_raw)),
        ),
    )


def _verify(project: Path, contract: authority._AuthorityContract) -> dict:
    return authority._verify_with_contract(project_root=project, contract=contract)


def test_private_fixture_positive_verifies_committed_bytes_and_json_shape(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    result = _verify(tmp_path, contract)
    assert result["status"] == authority.STATUS_REGISTERED
    assert result["downstream_authority"] == "NONE"
    assert result["manifest"]["commit_status"] == "MATCHED"
    assert {item["commit_status"] for item in result["bundle_files"]} == {"MATCHED"}
    assert result["bundle_files"] == sorted(result["bundle_files"], key=lambda item: item["path"])
    assert json.loads(authority._encode_result(result)) == result


def test_real_r13_bundle_is_registered_after_implementation_commit() -> None:
    result = authority.verify_registered_r13_bundle()
    assert result["status"] == authority.STATUS_REGISTERED
    assert result["errors"] == []
    assert result["identity"] == {
        "scenario": "regime_shadow_research",
        "ranking_date": "2026-09-01",
        "run_identity": "r13-r2-20260901-af9c32b",
        "batch_plan_id": "sha256:7cb4ab0fc61758085f71a865de79e022633327894807322bea66a0535aef46aa",
        "manifest_identity": "sha256:a493c793a34a4598e0500de8dd3e80c8252033e5ab85d8f620b50d5fc63411cb",
        "receipt_identity": "sha256:c2487b57395f83ff3d266aab4fd0349784d6fa892701ba7235aa8ec3b7bf527f",
    }
    assert result["manifest"]["commit_status"] == "MATCHED"
    assert {item["commit_status"] for item in result["bundle_files"]} == {"MATCHED"}


def test_cli_is_fixed_contract_and_has_no_path_override() -> None:
    completed = subprocess.run(
        [".venv/bin/python", "-m", "app.research.r13_forward_receipt_authority", "--verify"],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == (0 if payload["status"] == authority.STATUS_REGISTERED else 1)
    assert payload["downstream_authority"] == "NONE"

    rejected = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "app.research.r13_forward_receipt_authority",
            "--verify",
            "--project-root",
            "/tmp",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda project, contract: (project / contract.manifest_path).unlink(), "SOURCE_UNREADABLE"),
        (
            lambda project, contract: _git(project, "rm", "--cached", contract.manifest_path),
            "SOURCE_STAGED_NOT_HEAD",
        ),
        (
            lambda project, contract: (project / contract.manifest_path).write_bytes(
                (project / contract.manifest_path).read_bytes() + b"\n"
            ),
            "SOURCE_WORKTREE_DRIFT",
        ),
        (
            lambda project, contract: (
                (project / contract.manifest_path).write_bytes(b"{}\n"),
                _git(project, "add", contract.manifest_path),
                _git(project, "commit", "-qm", "bad manifest"),
            ),
            "SOURCE_SIZE_MISMATCH",
        ),
        (
            lambda project, contract: (
                (project / next(item.path for item in contract.expected_files if item.path.endswith(".pkl"))).write_bytes(b"bad-model\n"),
                _git(project, "add", "."),
                _git(project, "commit", "-qm", "bad model"),
            ),
            "SOURCE_HASH_MISMATCH",
        ),
    ],
)
def test_file_commit_matrix_rejects_missing_untracked_drift_and_hash_mismatch(
    tmp_path: Path,
    mutate,
    expected: str,
) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    mutate(tmp_path, contract)
    result = _verify(tmp_path, contract)
    assert result["status"] == authority.STATUS_REJECTED
    assert any(error.startswith(expected) for error in result["errors"])
    assert result["downstream_authority"] == "NONE"


def test_staged_but_not_head_and_extra_tracked_files_are_rejected(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _git(tmp_path, "commit", "--allow-empty", "-qm", "empty-head")
    contract = _fixture(tmp_path, commit=False)
    staged = _verify(tmp_path, contract)
    assert staged["status"] == authority.STATUS_REJECTED
    assert any(error.startswith("SOURCE_NOT_COMMITTED:") for error in staged["errors"])

    _git(tmp_path, "commit", "-qm", "fixture")
    summary = tmp_path / contract.output_root / "regime_shadow_ranking.json"
    summary.write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", summary.relative_to(tmp_path).as_posix())
    _git(tmp_path, "commit", "-qm", "extra summary")
    extra = _verify(tmp_path, contract)
    assert any(error.startswith("EXTRA_TRACKED_FILE:") for error in extra["errors"])


def test_second_run_and_duplicate_manifest_identities_fail_closed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    second = tmp_path / contract.output_root / ".ranking-provenance-v1/runs/second/COMPLETE.manifest.json"
    second.parent.mkdir(parents=True)
    second.write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", second.relative_to(tmp_path).as_posix())
    _git(tmp_path, "commit", "-qm", "second run")
    result = _verify(tmp_path, contract)
    assert any(error.startswith("EXTRA_TRACKED_FILE:") for error in result["errors"])

    manifest_path = tmp_path / contract.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"].append(copy.deepcopy(manifest["entries"][0]))
    manifest_path.write_bytes(_rehash_manifest(manifest))
    _git(tmp_path, "add", contract.manifest_path)
    _git(tmp_path, "commit", "-qm", "duplicate entry")
    duplicate = _verify(tmp_path, contract)
    assert "BUNDLE_VERIFIER_DUPLICATE_DATE" in duplicate["errors"]
    assert "MANIFEST_ENTRY_COUNT_MISMATCH" in duplicate["errors"]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("scenario", "wrong", "SCENARIO_MISMATCH"),
        ("run_identity", "wrong-run", "RUN_IDENTITY_MISMATCH"),
        ("batch_plan_id", "sha256:" + "b" * 64, "BATCH_PLAN_ID_MISMATCH"),
        ("capture_mode", receipts.REPLAY_GENERATED, "CAPTURE_MODE_MISMATCH"),
    ],
)
def test_manifest_identity_locks_reject_wrong_plan_scenario_date_and_replay(
    tmp_path: Path,
    field: str,
    value: str,
    expected: str,
) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    manifest_path = tmp_path / contract.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    manifest_path.write_bytes(_rehash_manifest(manifest))
    _git(tmp_path, "add", contract.manifest_path)
    _git(tmp_path, "commit", "-qm", f"bad {field}")
    result = _verify(tmp_path, contract)
    assert expected in result["errors"]
    assert result["status"] == authority.STATUS_REJECTED


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("scenario", "wrong", "RECEIPT_SCENARIO_MISMATCH"),
        ("ranking_date", "2026-09-02", "RECEIPT_RANKING_DATE_MISMATCH"),
        ("run_identity", "wrong-run", "RECEIPT_RUN_IDENTITY_MISMATCH"),
        ("capture_mode", receipts.REPLAY_GENERATED, "RECEIPT_CAPTURE_MODE_MISMATCH"),
        ("admission_eligible", True, "RECEIPT_ADMISSION_ELIGIBLE_MISMATCH"),
    ],
)
def test_receipt_identity_locks_reject_wrong_date_replay_and_false_admission(
    tmp_path: Path,
    field: str,
    value,
    expected: str,
) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    receipt_path = next(item.path for item in contract.expected_files if item.path.endswith(".receipt.json"))
    payload = json.loads((tmp_path / receipt_path).read_text(encoding="utf-8"))
    payload[field] = value
    (tmp_path / receipt_path).write_bytes(_rehash_receipt(payload))
    _git(tmp_path, "add", receipt_path)
    _git(tmp_path, "commit", "-qm", f"bad receipt {field}")
    result = _verify(tmp_path, contract)
    assert expected in result["errors"]
    assert result["status"] == authority.STATUS_REJECTED


def test_noncanonical_rehash_swap_ranking_and_model_semantic_drift_reject(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    receipt_path = next(item.path for item in contract.expected_files if item.path.endswith(".receipt.json"))
    (tmp_path / receipt_path).write_text(
        json.dumps(json.loads((tmp_path / receipt_path).read_text(encoding="utf-8")), indent=2),
        encoding="utf-8",
    )
    _git(tmp_path, "add", receipt_path)
    _git(tmp_path, "commit", "-qm", "noncanonical")
    result = _verify(tmp_path, contract)
    assert "BUNDLE_VERIFIER_RECEIPT_NONCANONICAL" in result["errors"]

    _init_repo(tmp_path / "ranking-drift")
    drift_contract = _fixture(tmp_path / "ranking-drift")
    ranking_path = next(item.path for item in drift_contract.expected_files if item.path.endswith(".csv"))
    (tmp_path / "ranking-drift" / ranking_path).write_text(
        "rank,stock_id,score\n1,2330,2\n2,1101,1\n",
        encoding="utf-8",
    )
    _git(tmp_path / "ranking-drift", "add", ranking_path)
    _git(tmp_path / "ranking-drift", "commit", "-qm", "ranking drift")
    drift = _verify(tmp_path / "ranking-drift", drift_contract)
    assert any(error.startswith("SOURCE_HASH_MISMATCH:") for error in drift["errors"])
    assert "BUNDLE_VERIFIER_ARTIFACT_HASH_DRIFT" in drift["errors"]

    _init_repo(tmp_path / "model-drift")
    model_contract = _fixture(tmp_path / "model-drift")
    model_path = next(item.path for item in model_contract.expected_files if item.path.endswith(".pkl"))
    (tmp_path / "model-drift" / model_path).write_bytes(b"different-model\n")
    _git(tmp_path / "model-drift", "add", model_path)
    _git(tmp_path / "model-drift", "commit", "-qm", "model drift")
    model = _verify(tmp_path / "model-drift", model_contract)
    assert any(error.startswith("SOURCE_HASH_MISMATCH:") for error in model["errors"])
    assert "BUNDLE_VERIFIER_MODEL_SNAPSHOT_HASH_DRIFT" in model["errors"]


def test_contract_rejects_absolute_traversal_symlink_and_cli_arbitrary_path(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    bad = authority._AuthorityContract(
        **{
            **contract.__dict__,
            "manifest_path": "../escape.json",
            "expected_files": (
                authority._ExpectedFile("../escape.json", 0, "0" * 64),
            ),
        }
    )
    escaped = _verify(tmp_path, bad)
    assert any(error.startswith("PATH_ESCAPE:") for error in escaped["errors"])

    link_path = next(item.path for item in contract.expected_files if item.path.endswith(".csv"))
    (tmp_path / link_path).unlink()
    (tmp_path / link_path).symlink_to(tmp_path / contract.manifest_path)
    linked = _verify(tmp_path, contract)
    assert any(error.startswith("PATH_SYMLINK:") for error in linked["errors"])


def test_head_move_during_verification_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    original = authority._git_bytes
    moved = False

    def moving_git(project: Path, args) -> tuple[int, bytes]:
        nonlocal moved
        result = original(project, args)
        if not moved and list(args[:1]) == ["ls-tree"]:
            extra = project / contract.output_root / "regime_shadow_ranking.json"
            extra.write_text("{}\n", encoding="utf-8")
            _git(project, "add", extra.relative_to(project).as_posix())
            _git(project, "commit", "-qm", "move head")
            moved = True
        return result

    monkeypatch.setattr(authority, "_git_bytes", moving_git)
    result = _verify(tmp_path, contract)
    assert result["status"] == authority.STATUS_REJECTED
    assert "HEAD_CHANGED_DURING_VERIFICATION" in result["errors"]
    assert not any(error.startswith("EXTRA_TRACKED_FILE:") for error in result["errors"])


def test_staged_state_git_failure_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    contract = _fixture(tmp_path)
    original = authority._git_bytes

    def failing_git(project: Path, args) -> tuple[int, bytes]:
        if list(args[:2]) == ["diff", "--cached"]:
            return 128, b""
        return original(project, args)

    monkeypatch.setattr(authority, "_git_bytes", failing_git)
    result = _verify(tmp_path, contract)
    assert result["status"] == authority.STATUS_REJECTED
    assert result["errors"] == ["GIT_STAGED_STATE_UNAVAILABLE"]


def test_project_root_symlink_is_rejected_before_resolve(tmp_path: Path) -> None:
    real = tmp_path / "real"
    _init_repo(real)
    contract = _fixture(real)
    link = tmp_path / "repo-link"
    link.symlink_to(real, target_is_directory=True)
    result = _verify(link, contract)
    assert result["status"] == authority.STATUS_REJECTED
    assert result["errors"] == ["ROOT_SYMLINK"]


def test_historical_admission_regression_remains_fail_closed() -> None:
    payload = admission.build_audit()
    assert payload["record_count"] == 50
    assert payload["missing_lineage_field_count"] == 300
    assert {record["admission"] for record in payload["records"]} == {"REJECT"}
    assert admission.RECEIPT_AUTHORITY_CONFIGURED is False
    assert admission.validate_audit(payload) == []
