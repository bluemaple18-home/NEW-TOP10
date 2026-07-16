from pathlib import Path

import pandas as pd
import pytest

from app.research_auditor import AuditInputs, build_audit, write_audit


def _write_ranking(path: Path, *, duplicate: bool = False) -> None:
    ids = ["2330", "2317"]
    if duplicate:
        ids[1] = ids[0]
    pd.DataFrame(
        {
            "stock_id": ids,
            "rank": [1, 2],
            "final_score": [0.9, 0.8],
            "model_prob": [0.8, 0.7],
            "prediction_score": [0.8, 0.7],
            "quality_score": [0.9, 0.8],
            "reasons": ["模型分數穩定", "基本面改善"],
        }
    ).to_csv(path, index=False, encoding="utf-8-sig")


def test_build_audit_is_research_only_and_tracks_input(tmp_path: Path) -> None:
    ranking = tmp_path / "ranking_2026-07-17.csv"
    _write_ranking(ranking)
    payload = build_audit(AuditInputs(ranking=ranking))

    assert payload["status"] == "GO"
    assert payload["contract"]["research_only"] is True
    assert payload["contract"]["production_mutation"] is False
    assert payload["inputs"]["ranking"]["sha256"]
    assert payload["summary"]["ranking_stock_count"] == 2


def test_duplicate_stock_id_is_blocking(tmp_path: Path) -> None:
    ranking = tmp_path / "ranking.csv"
    _write_ranking(ranking, duplicate=True)

    payload = build_audit(AuditInputs(ranking=ranking))

    assert payload["status"] == "NO-GO"
    assert "ranking_stock_id_unique" in payload["conclusion"]["blocking_reasons"]


def test_audit_cannot_overwrite_input(tmp_path: Path) -> None:
    ranking = tmp_path / "ranking.csv"
    _write_ranking(ranking)
    payload = build_audit(AuditInputs(ranking=ranking))

    with pytest.raises(ValueError, match="must not overwrite"):
        write_audit(payload, ranking)


def test_date_alignment_passes_for_historical_source(tmp_path: Path) -> None:
    ranking = tmp_path / "ranking_2026-07-17.csv"
    source = tmp_path / "features.csv"
    _write_ranking(ranking)
    pd.DataFrame({"stock_id": ["2330", "2317"], "date": ["2026-07-16", "2026-07-17"]}).to_csv(source, index=False)

    payload = build_audit(AuditInputs(ranking=ranking, features=source))

    date_check = next(item for item in payload["checks"] if item["name"] == "features_date_consistency")
    assert date_check["ok"] is True


def test_future_source_date_is_blocking(tmp_path: Path) -> None:
    ranking = tmp_path / "ranking_2026-07-17.csv"
    source = tmp_path / "features.csv"
    _write_ranking(ranking)
    pd.DataFrame({"stock_id": ["2330", "2317"], "date": ["2026-07-18", "2026-07-18"]}).to_csv(source, index=False)

    payload = build_audit(AuditInputs(ranking=ranking, features=source))

    assert payload["status"] == "NO-GO"
    assert "features_date_consistency" in payload["conclusion"]["blocking_reasons"]
