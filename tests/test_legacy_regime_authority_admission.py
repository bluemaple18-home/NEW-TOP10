from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from app.research import legacy_regime_authority_admission as admission


def _legacy_row(day: str, label: str = "BROAD_RISK_ON") -> dict:
    return {
        "trade_date": day,
        "regime_label": label,
        "risk_tone": "aggressive",
        "equal_weight_return": 0.01,
        "value_weight_return": 0.01,
        "breadth_ma20": 0.7,
        "breadth_ma60": 0.65,
        "advance_ratio": 0.7,
        "breakout_ratio": 0.08,
        "breakdown_ratio": 0.01,
        "volume_spike_ratio": 0.1,
        "long_upper_shadow_ratio": 0.02,
        "avg_rsi": 58.0,
        "top_sector": "科技",
        "top_sector_value_share": 0.5,
        "top_strong_sector": "科技",
        "top_strong_sector_value_share": 0.5,
        "notes": "fixture",
    }


def _payload(schema: str, rows: list[dict], *, inputs: dict | None = None) -> dict:
    return {
        "schema_version": schema,
        "inputs": inputs or {},
        "summary": {
            "trade_days": len(rows),
            "start_date": rows[0]["trade_date"],
            "end_date": rows[-1]["trade_date"],
        },
        "rows": rows,
    }


def _write_fixture(root: Path, *, with_hash: bool = True, drift: bool = False) -> None:
    days = [(date(2026, 1, 2) + timedelta(days=index)).isoformat() for index in range(25)]
    rows = [_legacy_row(day) for day in days]
    source = root / "data/source/features.parquet"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"immutable-source")
    inputs = {"features": "data/source/features.parquet"}
    if with_hash:
        inputs["features_sha256"] = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    legacy = _payload("market-regime-history.v1", rows, inputs=inputs)
    legacy_path = root / admission.LEGACY_RELATIVE
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = admission._migrate(rows)
    if drift:
        migrated[-1] = {**migrated[-1], "base_regime": "RISK_OFF", "regime_label": "RISK_OFF", "family_tags": []}
    current = _payload("market-regime-history.v2", migrated)
    current_path = root / admission.CURRENT_RELATIVE
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_text(json.dumps(current), encoding="utf-8")


def test_ready_when_lineage_identity_and_h20_episode_are_proven(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = admission.build_audit(project_root=tmp_path)
    assert payload["status"] == "READY_FOR_STAGED_MIGRATION"
    assert payload["reason_codes"] == []
    assert payload["feasible_identities"] == ["BROAD_RISK_ON|BIG_BULL"]
    assert payload["episodes"][0]["h20_safe_ranking_date_count"] == 5
    assert admission.validate_audit(payload) == []


def test_missing_recorded_hash_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, with_hash=False)
    payload = admission.build_audit(project_root=tmp_path)
    assert payload["status"] == "BLOCKED_AUTHORITY_NOT_ADMISSIBLE"
    assert "LEGACY_INPUT_HASH_NOT_RECORDED" in payload["reason_codes"]
    assert payload["lineage_authority_status"] == "UNPROVEN"


def test_overlap_identity_drift_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, drift=True)
    payload = admission.build_audit(project_root=tmp_path)
    assert payload["status"] == "BLOCKED_AUTHORITY_NOT_ADMISSIBLE"
    assert payload["overlap_reconciliation"]["exact_identity_drift_count"] == 1
    assert "OVERLAP_EXACT_IDENTITY_DRIFT" in payload["reason_codes"]


def test_written_evidence_is_recomputable_and_canonical(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = admission.write_audit(admission.EVIDENCE_RELATIVE, project_root=tmp_path)
    target = tmp_path / admission.EVIDENCE_RELATIVE
    assert target.stat().st_size <= admission.MAX_EVIDENCE_BYTES
    assert json.loads(target.read_bytes()) == payload
    assert admission.verify_audit(admission.EVIDENCE_RELATIVE, project_root=tmp_path) == {
        "status": "PASS",
        "errors": [],
    }
