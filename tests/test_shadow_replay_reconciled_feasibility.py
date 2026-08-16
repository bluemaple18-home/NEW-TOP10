from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.research import shadow_replay_reconciled_feasibility as reconciled
from app.research.contracts import content_hash


def _authority() -> dict[str, object]:
    return {
        "status": "READY_FOR_FEASIBILITY_AUDIT",
        "receipt_id": "sha256:" + "a" * 64,
        "runtime_sources": {
            "regime": {"path": "artifacts/market_regime_history.json", "sha256": "sha256:" + "b" * 64},
            "features": {"path": "data/clean/features.parquet", "sha256": "sha256:" + "c" * 64},
        },
    }


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    matrix: list[dict[str, object]],
) -> Path:
    root = tmp_path / "repo"
    regime = root / "artifacts/market_regime_history.json"
    features = root / "data/clean/features.parquet"
    regime.parent.mkdir(parents=True)
    features.parent.mkdir(parents=True)
    regime.write_text(
        json.dumps({"rows": [{"trade_date": "2026-01-02", "as_of_date": "2026-01-02", "base_regime": "RISK_OFF", "family_tags": []}]}),
        encoding="utf-8",
    )
    features.write_bytes(b"features")
    authority = _authority()
    authority["runtime_sources"]["regime"]["sha256"] = reconciled.reconciliation._sha256_file(regime)  # type: ignore[index]
    authority["runtime_sources"]["features"]["sha256"] = reconciled.reconciliation._sha256_file(features)  # type: ignore[index]
    monkeypatch.setattr(reconciled.coverage, "authorize_explicit_authority_root", lambda _project, authority_root: authority_root)
    monkeypatch.setattr(reconciled.reconciliation, "build_receipt", lambda **_kwargs: authority)
    monkeypatch.setattr(reconciled.reconciliation, "validate_receipt", lambda _payload: [])
    monkeypatch.setattr(
        reconciled.reconciliation,
        "_committed_json",
        lambda _root, _relative: (
            authority,
            {
                "path": reconciled.reconciliation.EVIDENCE_RELATIVE.as_posix(),
                "sha256": "sha256:" + "d" * 64,
                "commit_status": "MATCHED",
            },
        ),
    )
    monkeypatch.setattr(reconciled.availability, "_feature_inventory", lambda _root: ({}, [date(2026, 1, 2)]))
    monkeypatch.setattr(reconciled.feasibility, "episode_matrix", lambda _rows, _dates: matrix)
    return root


def test_zero_feasible_identities_is_legitimate_no_go(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepare(
        tmp_path,
        monkeypatch,
        [{
            "identity": "RISK_OFF",
            "episode_id": "episode-1",
            "start_date": "2026-01-02",
            "end_date": "2026-01-02",
            "trade_date_count": 1,
            "trade_dates": ["2026-01-02"],
            "horizon_safe_dates": {"10": [], "20": []},
            "shared_dates": [],
        }],
    )

    result = reconciled.build_audit(project_root=root, authority_root=root)

    assert result["status"] == "NO-GO_NO_ELIGIBLE_REGIME"
    assert result["reason_codes"] == ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"]
    assert result["episode_count"] == 1
    assert reconciled.validate_audit(result) == []


def test_feasible_identity_becomes_scope_decision_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepare(
        tmp_path,
        monkeypatch,
        [{
            "identity": "RISK_OFF",
            "episode_id": "episode-1",
            "start_date": "2026-01-02",
            "end_date": "2026-01-02",
            "trade_date_count": 1,
            "trade_dates": ["2026-01-02"],
            "horizon_safe_dates": {"10": ["2026-01-02"], "20": ["2026-01-02"]},
            "shared_dates": ["2026-01-02"],
        }],
    )

    result = reconciled.build_audit(project_root=root, authority_root=root)

    assert result["status"] == "READY_FOR_SCOPE_DECISION"
    assert result["feasible_identities"] == ["RISK_OFF"]
    assert result["lineage_authority_status"] == "UNPROVEN"


def test_non_ready_reconciliation_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(reconciled.coverage, "authorize_explicit_authority_root", lambda _project, authority_root: authority_root)
    monkeypatch.setattr(reconciled.reconciliation, "build_receipt", lambda **_kwargs: {"status": "BLOCKED_AUTHORITY_CONFLICT"})
    monkeypatch.setattr(reconciled.reconciliation, "validate_receipt", lambda _payload: ["blocked"])

    with pytest.raises(reconciled.ReconciledFeasibilityError, match="AUTHORITY_RECONCILIATION_NOT_READY"):
        reconciled.build_audit(project_root=root, authority_root=root)


def test_validator_rejects_false_ready_and_absolute_path() -> None:
    payload = {
        "schema_version": reconciled.SCHEMA_VERSION,
        "audit_id": "",
        "status": "READY_FOR_SCOPE_DECISION",
        "lineage_authority_status": "PROVEN",
        "episode_count": 0,
        "episodes": [],
        "feasible_identities": [],
        "reconciliation": {"path": "/tmp/forbidden", "status": "READY_FOR_FEASIBILITY_AUDIT"},
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})

    errors = reconciled.validate_audit(payload)

    assert "FALSE_READY_STATUS" in errors
    assert "LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN" in errors
    assert "ABSOLUTE_PATH_FORBIDDEN" in errors
