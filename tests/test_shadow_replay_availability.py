from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.research import shadow_replay_availability as availability
from app.research.contracts import canonical_json_bytes
from scripts import run_autonomous_research


def _write_fixture(root: Path, *, with_sources: bool = True) -> None:
    evidence = root / availability.CARD_D_RELATIVE
    evidence.parent.mkdir(parents=True)
    episode_ids: list[str] = []
    if with_sources:
        dates = pd.bdate_range("2026-01-02", periods=35).date
        features = root / availability.FEATURES_RELATIVE
        features.parent.mkdir(parents=True)
        pd.DataFrame({"trade_date": dates}).to_parquet(features, index=False)
        rows = [
            {
                "trade_date": item.isoformat(),
                "as_of_date": item.isoformat(),
                "base_regime": "NARROW_LEADER",
                "family_tags": ["BIG_BULL"],
                "is_transition": False,
            }
            for item in dates
        ]
        history = root / availability.REGIME_RELATIVE
        history.parent.mkdir(parents=True)
        history.write_text(json.dumps({"rows": rows}), encoding="utf-8")
        episode_ids = [run_autonomous_research.build_regime_episodes(rows)[0]["episode_id"]]
        for relative in availability.RANKING_ROOTS.values():
            directory = root / relative
            directory.mkdir(parents=True)
            for ranking_date in dates[:2]:
                (directory / f"ranking_{ranking_date.isoformat()}.csv").write_text(
                    "stock_id,score\n2330,1\n", encoding="utf-8"
                )
    units = [
        {
            "terminal_status": "SUCCEEDED",
            "observation_status": "OBSERVED",
            "identity_match_status": "EXACT",
            "lineage_resolution_status": "VALID",
            "sealed_usage_status": "PROVEN_NON_SEALED",
            "lineage_id": lineage,
            "horizon": horizon,
        }
        for lineage in ("baseline-lineage", "candidate-lineage")
        for horizon in availability.HORIZONS
    ]
    card_d = {
        "units": units,
        "runner": {
            "steps": [
                {
                    "command": [
                        "python",
                        "scripts/run_backtest_strategy_matrix.py",
                        "--allowed-episode-ids",
                        ",".join(episode_ids),
                    ]
                }
            ]
        },
    }
    evidence.write_text(json.dumps(card_d), encoding="utf-8")


def test_build_audit_reuses_canonical_helper_and_can_go(tmp_path: Path, monkeypatch) -> None:
    _write_fixture(tmp_path)
    calls: list[int] = []
    original = availability.strategy_matrix.exact_horizon_safe_ranking_dates

    def tracked(*args, **kwargs):
        calls.append(int(kwargs["horizon"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        availability.strategy_matrix, "exact_horizon_safe_ranking_dates", tracked
    )
    audit = availability.build_audit(project_root=tmp_path)

    assert audit["verdict"] == "GO_REPLAY_INPUTS_AVAILABLE"
    assert calls == [10, 20]
    assert audit["minimum_gap"] is None
    assert all(audit["matched_intersection_by_horizon"][str(item)] for item in (10, 20))
    assert all(
        row["exact_regime_episode_id"]
        for matrix in audit["availability_matrix"]
        for row in matrix["dates"]
        if row["status"] == "ACCEPTED"
    )


def test_missing_fixed_inputs_are_auditable_no_go(tmp_path: Path) -> None:
    _write_fixture(tmp_path, with_sources=False)

    audit = availability.build_audit(project_root=tmp_path)

    assert audit["verdict"] == "NO-GO_EVIDENCE_UNAVAILABLE"
    assert audit["minimum_gap"]["primary_reason_code"] == "MISSING_RANKING_DATE"
    assert "MISSING_EXACT_REGIME" in audit["reason_codes"]
    assert audit["sources"]["ranking_roots"]["baseline"]["status"] == "MISSING"


def test_output_is_byte_deterministic_and_verifiable(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    output = tmp_path / availability.EVIDENCE_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)

    first = availability.write_audit(
        availability.EVIDENCE_RELATIVE, project_root=tmp_path
    )
    first_bytes = output.read_bytes()
    second = availability.write_audit(
        availability.EVIDENCE_RELATIVE, project_root=tmp_path
    )

    assert first == second
    assert output.read_bytes() == first_bytes == canonical_json_bytes(first) + b"\n"
    assert availability.verify_audit(
        availability.EVIDENCE_RELATIVE, project_root=tmp_path
    ) == {"status": "PASS", "errors": []}


def test_symlink_source_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, with_sources=False)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    ranking = tmp_path / availability.RANKING_ROOTS["baseline"]
    ranking.parent.mkdir(parents=True, exist_ok=True)
    ranking.symlink_to(outside, target_is_directory=True)

    try:
        availability.build_audit(project_root=tmp_path)
    except availability.AvailabilityAuditError as error:
        assert str(error).startswith("SOURCE_SYMLINK")
    else:
        raise AssertionError("symlink source should fail closed")


def test_verifier_rejects_tampered_identity(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    availability.write_audit(availability.EVIDENCE_RELATIVE, project_root=tmp_path)
    output = tmp_path / availability.EVIDENCE_RELATIVE
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["verdict"] = "NO-GO_EVIDENCE_UNAVAILABLE"
    output.write_text(json.dumps(payload), encoding="utf-8")

    result = availability.verify_audit(
        availability.EVIDENCE_RELATIVE, project_root=tmp_path
    )

    assert result["status"] == "FAIL"
    assert "AUDIT_ID_MISMATCH" in result["errors"]
