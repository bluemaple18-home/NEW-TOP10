from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

from scripts import research_regime_shadow_ranking as shadow_ranking
from scripts.research_regime_shadow_ranking import PROJECT_ROOT, validate_research_output_dir
from scripts.run_weekend_research_matrix import matrix_commands


def test_shadow_output_accepts_isolated_backtest_directory() -> None:
    source = PROJECT_ROOT / "artifacts" / "backtest" / "historical_rankings_current_model"
    output = PROJECT_ROOT / "artifacts" / "backtest" / "shadow_rankings_test"

    assert validate_research_output_dir(source, output) == output


@pytest.mark.parametrize(
    "output",
    [
        PROJECT_ROOT / "artifacts",
        PROJECT_ROOT / "artifacts" / "backtest",
        PROJECT_ROOT / "data" / "clean",
        PROJECT_ROOT / "models",
    ],
)
def test_shadow_output_rejects_non_isolated_directory(output: Path) -> None:
    source = PROJECT_ROOT / "artifacts"

    with pytest.raises(ValueError, match="output-dir"):
        validate_research_output_dir(source, output)


def test_shadow_output_rejects_source_directory() -> None:
    source = PROJECT_ROOT / "artifacts" / "backtest" / "historical_rankings_current_model"

    with pytest.raises(ValueError, match="dates-from-dir"):
        validate_research_output_dir(source, source)


def test_shadow_forward_capture_requires_authority_before_ranking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    source = project / "artifacts" / "backtest" / "source"
    output = project / "artifacts" / "backtest" / "shadow"
    source.mkdir(parents=True)
    (source / "ranking_2026-09-01.csv").write_text("rank,stock_id,score\n1,1101,1\n", encoding="utf-8")
    monkeypatch.setattr(shadow_ranking, "PROJECT_ROOT", project)
    monkeypatch.setattr(shadow_ranking, "RESEARCH_OUTPUT_ROOT", project / "artifacts" / "backtest")

    with pytest.raises(shadow_ranking.RankingProvenanceError, match="capture-authority"):
        shadow_ranking.build_shadow(
            Namespace(
                dates_from_dir=str(source),
                output_dir=str(output),
                market_regime_history="artifacts/market_regime_history.json",
                industry_map="data/reference/stock_industry_map.csv",
                risk_profile="baseline",
                top_n=10,
                max_sector_count=None,
                sector_cap_column="industry_name",
                limit=None,
                data_dir="data/clean",
                model_dir="models",
                config="config/signals.yaml",
                scenario="regime_shadow_research",
                forward_capture=True,
                capture_trade_date="2026-09-01",
                capture_authority_artifact=None,
                run_identity="missing-authority",
            )
        )


def test_shadow_forward_capture_rejects_authority_replaced_after_validation_before_initial_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    source = project / "artifacts" / "backtest" / "source"
    output = project / "artifacts" / "backtest" / "shadow"
    data_dir = project / "data" / "clean"
    model_dir = project / "models"
    source.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    model_dir.mkdir()
    (source / "ranking_2026-09-01.csv").write_text("rank,stock_id,score\\n1,1101,1\\n", encoding="utf-8")
    for path in (data_dir / "features.parquet", data_dir / "universe.parquet", model_dir / "latest_lgbm.pkl", project / "signals.yaml", project / "artifacts" / "market_regime_history.json", project / "data" / "reference" / "stock_industry_map.csv"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    authority_path = project / "artifacts" / "automation_status.json"
    authority = {
        "status": "OK", "run_date": "2026-09-01",
        "steps": [{"name": "data.freshness.after_etl", "status": "OK"}, {"name": "ranking", "status": "OK"}],
        "metadata": {"data_freshness": {"datasets": {
            "features.parquet": {"latest_date": "2026-09-01", "latest_market_coverage": {"markets": [{"market_type": "TWSE", "status": "OK"}, {"market_type": "TPEX", "status": "OK"}]}},
            "universe.parquet": {"latest_date": "2026-09-01"},
        }}},
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    monkeypatch.setattr(shadow_ranking, "PROJECT_ROOT", project)
    monkeypatch.setattr(shadow_ranking, "RESEARCH_OUTPUT_ROOT", project / "artifacts" / "backtest")
    monkeypatch.setattr(shadow_ranking, "producer_source_lineage", lambda *_args: {"source_commit": "a" * 40, "dependencies": []})
    original_validate = shadow_ranking.validate_completed_trade_date_authority

    def validate_then_replace(**kwargs):
        result = original_validate(**kwargs)
        authority_path.write_text(json.dumps({**authority, "replacement": True}), encoding="utf-8")
        return result

    monkeypatch.setattr(shadow_ranking, "validate_completed_trade_date_authority", validate_then_replace)
    with pytest.raises(shadow_ranking.RankingProvenanceError, match="validation 與 initial snapshot 間漂移"):
        shadow_ranking.build_shadow(Namespace(
            dates_from_dir=str(source), output_dir=str(output), market_regime_history="artifacts/market_regime_history.json",
            industry_map="data/reference/stock_industry_map.csv", risk_profile="baseline", top_n=10,
            max_sector_count=None, sector_cap_column="industry_name", limit=None, data_dir="data/clean",
            model_dir="models", config="signals.yaml", scenario="regime_shadow_research", forward_capture=True,
            capture_trade_date="2026-09-01", capture_authority_artifact="artifacts/automation_status.json",
            run_identity="authority-replaced",
        ))


def test_weekend_matrix_contains_no_fetch_train_or_live_steps() -> None:
    args = Namespace(skip_heavy=False, features="data/clean/features.parquet", max_ranking_files=2)
    commands = matrix_commands(args)
    flattened = " ".join(part for _, command in commands for part in command).lower()

    assert "fetch" not in flattened
    assert "train_model" not in flattened
    assert "live" not in flattened
    assert "send" not in flattened
