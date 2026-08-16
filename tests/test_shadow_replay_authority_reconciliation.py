from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from app.research import shadow_replay_authority_reconciliation as reconciliation
from app.research.contracts import canonical_json_bytes, content_hash


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / reconciliation.PLAN_RELATIVE.parent).mkdir(parents=True)
    (root / reconciliation.AUDIT_RELATIVE.parent).mkdir(parents=True)
    features = root / "data/clean/features.parquet"
    regime = root / "artifacts/market_regime_history.json"
    features.parent.mkdir(parents=True)
    regime.parent.mkdir(parents=True)
    features.write_bytes(b"ignored-features")
    regime.write_bytes(b'{"rows":[]}\n')
    fixed_sources = {
        "features": {
            "path": "data/clean/features.parquet",
            "sha256": _sha(features.read_bytes()),
            "status": "AVAILABLE",
            "date_coverage": {"count": 1, "first": "2026-01-02", "last": "2026-01-02"},
        },
        "regime": {
            "path": "artifacts/market_regime_history.json",
            "sha256": _sha(regime.read_bytes()),
            "status": "AVAILABLE",
        },
    }
    audit = {
        "schema_version": "shadow-replay-availability.v1",
        "audit_id": "",
        "verdict": "NO-GO_EVIDENCE_UNAVAILABLE",
        "parity": {
            "fixed_sources_before": fixed_sources,
            "fixed_sources_after": fixed_sources,
        },
    }
    audit["audit_id"] = content_hash(audit, omit={"audit_id"})
    audit_bytes = canonical_json_bytes(audit) + b"\n"
    (root / reconciliation.AUDIT_RELATIVE).write_bytes(audit_bytes)
    plan = {
        "schema_version": "horizon-safe-evidence-coverage-plan.v1",
        "status": "NO-GO_PLAN_UNAVAILABLE",
        "audit": {
            "path": reconciliation.AUDIT_RELATIVE.as_posix(),
            "sha256": _sha(audit_bytes),
            "audit_id": audit["audit_id"],
        },
    }
    (root / reconciliation.PLAN_RELATIVE).write_bytes(canonical_json_bytes(plan) + b"\n")
    (root / ".gitignore").write_text("data/clean/*\nartifacts/*\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".gitignore", reconciliation.PLAN_RELATIVE.as_posix(), reconciliation.AUDIT_RELATIVE.as_posix())
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    return root, root


def test_ignored_sources_are_accepted_only_through_committed_hash_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, authority_root = _fixture(tmp_path)
    monkeypatch.setattr(reconciliation.coverage, "authorize_explicit_authority_root", lambda _project, authority: authority)
    monkeypatch.setattr(reconciliation, "snapshot_protected_surfaces", lambda **_kwargs: {})

    receipt = reconciliation.build_receipt(project_root=project_root, authority_root=authority_root)

    assert receipt["status"] == "READY_FOR_FEASIBILITY_AUDIT"
    assert {item["commit_status"] for item in receipt["runtime_sources"].values()} == {"IGNORED_HASH_BOUND"}
    assert reconciliation.validate_receipt(receipt) == []


def test_runtime_hash_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, authority_root = _fixture(tmp_path)
    (authority_root / "data/clean/features.parquet").write_bytes(b"mutated")
    monkeypatch.setattr(reconciliation.coverage, "authorize_explicit_authority_root", lambda _project, authority: authority)
    monkeypatch.setattr(reconciliation, "snapshot_protected_surfaces", lambda **_kwargs: {})

    with pytest.raises(reconciliation.AuthorityReconciliationError, match="RUNTIME_SOURCE_HASH_MISMATCH"):
        reconciliation.build_receipt(project_root=project_root, authority_root=authority_root)


def test_committed_audit_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, authority_root = _fixture(tmp_path)
    (project_root / reconciliation.AUDIT_RELATIVE).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(reconciliation.coverage, "authorize_explicit_authority_root", lambda _project, authority: authority)

    with pytest.raises(reconciliation.AuthorityReconciliationError, match="COMMITTED_SOURCE_DRIFT"):
        reconciliation.build_receipt(project_root=project_root, authority_root=authority_root)


def test_nested_symlink_source_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, authority_root = _fixture(tmp_path)
    original = authority_root / "data/clean"
    external = tmp_path / "external"
    external.mkdir()
    (external / "features.parquet").write_bytes((original / "features.parquet").read_bytes())
    (original / "features.parquet").unlink()
    original.rmdir()
    original.symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(reconciliation.coverage, "authorize_explicit_authority_root", lambda _project, authority: authority)
    monkeypatch.setattr(reconciliation, "snapshot_protected_surfaces", lambda **_kwargs: {})

    with pytest.raises(reconciliation.AuthorityReconciliationError, match="SOURCE_SYMLINK"):
        reconciliation.build_receipt(project_root=project_root, authority_root=authority_root)


def test_false_lineage_claim_is_rejected() -> None:
    payload = {
        "schema_version": reconciliation.SCHEMA_VERSION,
        "receipt_id": "",
        "status": "READY_FOR_FEASIBILITY_AUDIT",
        "lineage_authority_status": "PROVEN",
        "runtime_sources": {},
        "source": "/tmp/forbidden",
    }
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})

    errors = reconciliation.validate_receipt(payload)

    assert "LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN" in errors
    assert "RUNTIME_SOURCE_STATUS_INVALID" in errors
    assert "ABSOLUTE_PATH_FORBIDDEN" in errors
    assert "CHAIN_IDENTITY_INVALID" in errors
    assert "PARITY_INVALID" in errors


def test_cli_io_error_is_structured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        reconciliation,
        "parse_args",
        lambda _argv=None: type("Args", (), {"verify": None, "output": Path("evidence.json"), "authority_root": None})(),
    )
    monkeypatch.setattr(reconciliation, "write_receipt", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("/private/path")))

    assert reconciliation.main([]) == 2
    assert json.loads(capsys.readouterr().out) == {"status": "FAIL", "errors": ["IO_ERROR"]}
