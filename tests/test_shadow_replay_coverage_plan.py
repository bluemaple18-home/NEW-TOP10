from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import pandas as pd

from app.research import shadow_replay_coverage_plan as coverage
from app.research.contracts import canonical_json_bytes, content_hash


def test_selects_earliest_minimal_date_shared_by_both_horizons(monkeypatch) -> None:
    calls: list[int] = []

    def fake_helper(allowed_dates, episode_by_date, trade_dates, *, horizon, entry_delay_trade_days):
        calls.append(horizon)
        assert entry_delay_trade_days == 1
        return {
            10: {"2026-01-02", "2026-01-05"},
            20: {"2026-01-02"},
        }[horizon]

    monkeypatch.setattr(
        coverage.strategy_matrix,
        "exact_horizon_safe_ranking_dates",
        fake_helper,
    )

    selection = coverage.select_shared_dates(
        {"2026-01-02", "2026-01-05"},
        {"2026-01-02": "episode-a", "2026-01-05": "episode-a"},
        [date(2026, 1, 2), date(2026, 1, 5)],
    )

    assert calls == [10, 20]
    assert selection["shared_dates"] == ["2026-01-02"]
    assert selection["selected_dates"] == ["2026-01-02"]
    assert selection["selection_rule"] == "MIN_CARDINALITY_THEN_DATE_ASC"


def test_empty_horizon_intersection_is_auditable_no_go(monkeypatch) -> None:
    def fake_helper(allowed_dates, episode_by_date, trade_dates, *, horizon, entry_delay_trade_days):
        if horizon == 10:
            return {"2026-01-02"}
        raise ValueError("NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=20")

    monkeypatch.setattr(
        coverage.strategy_matrix,
        "exact_horizon_safe_ranking_dates",
        fake_helper,
    )

    selection = coverage.select_shared_dates(
        {"2026-01-02"}, {"2026-01-02": "episode-a"}, [date(2026, 1, 2)]
    )
    payload = coverage.no_go_plan(
        audit_record={"path": "audit.json", "sha256": "sha256:" + "a" * 64, "audit_id": "sha256:" + "b" * 64},
        source_hashes={"canonical_helper": "sha256:" + "c" * 64},
        selection=selection,
        parity={"fixed_sources_unchanged": True, "protected_surfaces_unchanged": True},
    )

    assert payload["status"] == "NO-GO_PLAN_UNAVAILABLE"
    assert payload["reason_codes"] == ["NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE"]
    assert payload["materialization"] is None
    assert payload["lineage_authority_status"] == "PENDING_MATERIALIZATION_AND_REPLAY"


def test_plan_validation_rejects_absolute_paths_and_false_lineage_claims() -> None:
    payload = coverage.no_go_plan(
        audit_record={"path": "audit.json", "sha256": "sha256:" + "a" * 64, "audit_id": "sha256:" + "b" * 64},
        source_hashes={"canonical_helper": "sha256:" + "c" * 64},
        selection={
            "horizon_safe_dates": {"10": [], "20": []},
            "shared_dates": [],
            "selected_dates": [],
            "selection_rule": "MIN_CARDINALITY_THEN_DATE_ASC",
        },
        parity={"fixed_sources_unchanged": True, "protected_surfaces_unchanged": True},
    )
    payload["audit"]["path"] = "/tmp/audit.json"
    payload["lineage_authority_status"] = "PROVEN"
    payload["plan_id"] = content_hash(payload, omit={"plan_id"})

    errors = coverage.validate_plan(payload)

    assert "ABSOLUTE_PATH_FORBIDDEN:/tmp/audit.json" in errors
    assert "LINEAGE_STATUS_MUST_REMAIN_PENDING" in errors


def test_canonical_encoder_is_byte_deterministic() -> None:
    payload = coverage.no_go_plan(
        audit_record={"path": "audit.json", "sha256": "sha256:" + "a" * 64, "audit_id": "sha256:" + "b" * 64},
        source_hashes={"canonical_helper": "sha256:" + "c" * 64},
        selection={
            "horizon_safe_dates": {"10": [], "20": []},
            "shared_dates": [],
            "selected_dates": [],
            "selection_rule": "MIN_CARDINALITY_THEN_DATE_ASC",
        },
        parity={"fixed_sources_unchanged": True, "protected_surfaces_unchanged": True},
    )

    assert coverage.encode_plan(payload) == canonical_json_bytes(payload) + b"\n"
    assert json.loads(coverage.encode_plan(payload)) == payload


def test_output_collision_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "ranking_2026-01-02.csv"
    target.write_text("stock_id\n2330\n", encoding="utf-8")

    with pytest.raises(coverage.CoveragePlanError, match="OUTPUT_COLLISION"):
        coverage.ensure_new_output(target, root=tmp_path)


def test_materialization_contract_binds_inputs_and_bounded_argv(tmp_path: Path) -> None:
    selected_date = "2099-01-02"
    (tmp_path / "data/clean").mkdir(parents=True)
    pd.DataFrame({"date": [selected_date], "stock_id": ["2330"]}).to_parquet(
        tmp_path / "data/clean/features.parquet", index=False
    )
    pd.DataFrame({"date": [selected_date], "stock_id": ["2330"]}).to_parquet(
        tmp_path / "data/clean/universe.parquet", index=False
    )
    (tmp_path / "models").mkdir()
    (tmp_path / "models/latest_lgbm.pkl").write_bytes(b"model")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/signals.yaml").write_text("signals: {}\n", encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/market_regime_history.json").write_text(
        json.dumps({"rows": [{"trade_date": selected_date}]}), encoding="utf-8"
    )
    (tmp_path / "data/reference").mkdir()
    (tmp_path / "data/reference/stock_industry_map.csv").write_text(
        "stock_id,industry_name\n2330,半導體\n", encoding="utf-8"
    )
    (tmp_path / coverage.BASELINE_ROOT).mkdir(parents=True)
    (tmp_path / coverage.CANDIDATE_ROOT).mkdir(parents=True)

    materialization = coverage._materialization(
        project_root=coverage.PROJECT_ROOT,
        authority_root=tmp_path,
        selected_date=selected_date,
    )

    assert materialization["execution_allowed_in_this_card"] is False
    assert materialization["baseline"]["expected_ranking_paths"] == [
        f"{coverage.BASELINE_ROOT.as_posix()}/ranking_{selected_date}.csv"
    ]
    assert materialization["candidate"]["expected_ranking_paths"] == [
        f"{coverage.CANDIDATE_ROOT.as_posix()}/ranking_{selected_date}.csv"
    ]
    assert materialization["baseline"]["argv"].count(selected_date) == 2
    assert materialization["candidate"]["argv"][-2:] == ["--limit", "1"]
    assert not any(Path(value).is_absolute() for value in materialization["baseline"]["argv"])


@pytest.mark.parametrize(
    "case",
    ["symlink_alias", "traversal", "nested_symlink", "path_escape"],
)
def test_cli_rejects_raw_authority_root_bypass_without_writes(
    tmp_path: Path,
    case: str,
) -> None:
    main_root = coverage.discover_authority_root()
    evidence = coverage.PROJECT_ROOT / coverage.EVIDENCE_RELATIVE
    before = evidence.read_bytes()
    if case == "symlink_alias":
        authority_root = tmp_path / "main-alias"
        authority_root.symlink_to(main_root, target_is_directory=True)
    elif case == "traversal":
        authority_root = main_root / "docs" / ".."
    elif case == "nested_symlink":
        parent_alias = tmp_path / "parent-alias"
        parent_alias.symlink_to(main_root.parent, target_is_directory=True)
        authority_root = parent_alias / main_root.name
    else:
        authority_root = tmp_path

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.research.shadow_replay_coverage_plan",
            "--authority-root",
            str(authority_root),
            "--verify",
            coverage.EVIDENCE_RELATIVE.as_posix(),
        ],
        cwd=coverage.PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0, completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "FAIL"
    assert any("AUTHORITY_ROOT" in error for error in result["errors"])
    assert evidence.read_bytes() == before


def test_cli_accepts_exact_main_authority_root() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.research.shadow_replay_coverage_plan",
            "--authority-root",
            str(coverage.discover_authority_root()),
            "--verify",
            coverage.EVIDENCE_RELATIVE.as_posix(),
        ],
        cwd=coverage.PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout) == {"errors": [], "status": "PASS"}
