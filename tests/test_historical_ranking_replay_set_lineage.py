from argparse import Namespace
import json
from pathlib import Path

import pytest

from scripts import build_historical_ranking_replay_set as ranking_set


def test_manifest_records_current_model_source_lineage(tmp_path, monkeypatch):
    monkeypatch.setattr(ranking_set, "PROJECT_ROOT", tmp_path)
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    model_dir.mkdir()
    (data_dir / "features.parquet").write_bytes(b"features-v1")
    (data_dir / "universe.parquet").write_bytes(b"universe-v1")
    (model_dir / "latest_lgbm.pkl").write_bytes(b"model-v1")
    config_path = tmp_path / "signals.yaml"
    config_path.write_bytes(b"signals-v1")

    class FakeRanker:
        def __init__(self, *, artifact_dir, **_kwargs):
            self.artifact_dir = Path(artifact_dir)
            self.top_n = 10

        def load_model(self, _filename=None):
            return None

    monkeypatch.setattr(ranking_set, "StockRanker", FakeRanker)
    monkeypatch.setattr(ranking_set, "load_trade_dates", lambda **_kwargs: ["2026-03-13"])
    universe = ranking_set.pd.DataFrame({"stock_id": ["1101"]})
    monkeypatch.setattr(ranking_set, "load_universe", lambda *_args, **_kwargs: universe)
    monkeypatch.setattr(ranking_set, "prepare_batch_frames", lambda _ranker: (object(), universe))
    monkeypatch.setattr(
        ranking_set,
        "producer_source_lineage",
        lambda *_args: {"source_commit": "a" * 40, "dependencies": [{"path": "scripts/producer.py", "sha256": "sha256:" + "1" * 64}]},
    )
    ranking_csv = "rank,stock_id,risk_adjusted_score\n" + "".join(
        f"{index},{1000 + index},{11 - index}\n" for index in range(1, 11)
    )
    monkeypatch.setattr(
        ranking_set,
        "run_batch_ranking_for_date",
        lambda ranker, *_args: (ranker.artifact_dir.mkdir(parents=True, exist_ok=True), (ranker.artifact_dir / "ranking_2026-03-13.csv").write_text(ranking_csv, encoding="utf-8"), ranker.artifact_dir / "ranking_2026-03-13.csv")[-1],
    )

    payload = ranking_set.build_payload(
        Namespace(
            start_date="2026-03-13",
            end_date="2026-03-13",
            data_dir=str(data_dir),
            model_dir=str(model_dir),
            config=str(config_path),
            output_dir=str(output_dir),
            stride=1,
            max_dates=None,
            top_n=10,
                legacy_per_date_load=False,
                manifest=str(output_dir / "manifest.json"),
                scenario="baseline_research",
                forward_capture=False,
                capture_trade_date=None,
                capture_authority_artifact=None,
                run_identity="fixture-run",
            )
    )

    lineage = payload["source_lineage"]
    assert lineage["features_path"] == "data/features.parquet"
    assert lineage["features_sha256"] == ranking_set.sha256_file(data_dir / "features.parquet")
    assert lineage["universe_path"] == "data/universe.parquet"
    assert lineage["universe_sha256"] == ranking_set.sha256_file(data_dir / "universe.parquet")
    assert lineage["model_path"] == "models/latest_lgbm.pkl"
    assert lineage["model_sha256"] == ranking_set.sha256_file(model_dir / "latest_lgbm.pkl")
    assert lineage["config_path"] == "signals.yaml"
    assert lineage["config_sha256"] == ranking_set.sha256_file(config_path)


def test_forward_capture_uses_completion_authority_not_wall_clock(tmp_path, monkeypatch):
    monkeypatch.setattr(ranking_set, "PROJECT_ROOT", tmp_path)
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    output_dir = tmp_path / "output"
    artifacts = tmp_path / "artifacts"
    data_dir.mkdir()
    model_dir.mkdir()
    artifacts.mkdir()
    (data_dir / "features.parquet").write_bytes(b"features-v1")
    (data_dir / "universe.parquet").write_bytes(b"universe-v1")
    (model_dir / "latest_lgbm.pkl").write_bytes(b"model-v1")
    config_path = tmp_path / "signals.yaml"
    config_path.write_bytes(b"signals-v1")
    authority_path = artifacts / "automation_status_2026-09-01.json"
    authority_path.write_text(
        json.dumps(
            {
                "schema_version": "automation-status.v1",
                "run_date": "2026-09-01",
                "status": "OK",
                "steps": [
                    {"name": "data.freshness.after_etl", "status": "OK"},
                    {"name": "ranking", "status": "OK"},
                ],
                "metadata": {
                    "data_freshness": {
                        "datasets": {
                            "features.parquet": {
                                "latest_date": "2026-09-01",
                                "latest_market_coverage": {
                                    "markets": [
                                        {"market_type": "TWSE", "status": "OK"},
                                        {"market_type": "TPEX", "status": "OK"},
                                    ]
                                },
                            },
                            "universe.parquet": {"latest_date": "2026-09-01"},
                        }
                    }
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    class FakeRanker:
        def __init__(self, *, artifact_dir, **_kwargs):
            self.artifact_dir = Path(artifact_dir)
            self.top_n = 10

        def load_model(self, _filename=None):
            return None

    monkeypatch.setattr(ranking_set, "StockRanker", FakeRanker)
    monkeypatch.setattr(ranking_set, "load_trade_dates", lambda **_kwargs: ["2026-09-01"])
    universe = ranking_set.pd.DataFrame({"stock_id": ["1101"]})
    monkeypatch.setattr(ranking_set, "load_universe", lambda *_args, **_kwargs: universe)
    monkeypatch.setattr(ranking_set, "prepare_batch_frames", lambda _ranker: (object(), universe))
    monkeypatch.setattr(
        ranking_set,
        "producer_source_lineage",
        lambda *_args: {"source_commit": "a" * 40, "dependencies": [{"path": "scripts/producer.py", "sha256": "sha256:" + "1" * 64}]},
    )
    ranking_csv = "rank,stock_id,risk_adjusted_score\n" + "".join(
        f"{index},{1000 + index},{11 - index}\n" for index in range(1, 11)
    )
    monkeypatch.setattr(
        ranking_set,
        "run_batch_ranking_for_date",
        lambda ranker, *_args: (ranker.artifact_dir.mkdir(parents=True, exist_ok=True), (ranker.artifact_dir / "ranking_2026-09-01.csv").write_text(ranking_csv, encoding="utf-8"), ranker.artifact_dir / "ranking_2026-09-01.csv")[-1],
    )

    payload = ranking_set.build_payload(
        Namespace(
            start_date="2026-09-01",
            end_date="2026-09-01",
            data_dir=str(data_dir),
            model_dir=str(model_dir),
            config=str(config_path),
            output_dir=str(output_dir),
            stride=1,
            max_dates=None,
            top_n=10,
            legacy_per_date_load=False,
            manifest=str(output_dir / "manifest.json"),
            scenario="baseline_research",
            forward_capture=True,
            capture_trade_date="2026-09-01",
            capture_authority_artifact="artifacts/automation_status_2026-09-01.json",
            run_identity="fixture-forward-run",
        )
    )

    provenance_manifest = tmp_path / payload["outputs"]["provenance_manifest"]
    manifest = json.loads(provenance_manifest.read_text(encoding="utf-8"))
    receipt_ref = manifest["entries"][0]["receipt"]["path"]
    receipt = json.loads((tmp_path / receipt_ref).read_text(encoding="utf-8"))
    assert receipt["capture_mode"] == "FORWARD_CAPTURE"
    assert receipt["admission_eligible"] == "pending_registration"
    assert receipt["strict_inputs"]["completed_trade_date_authority"]["path"] == "artifacts/automation_status_2026-09-01.json"


def test_forward_capture_rejects_authority_replaced_after_validation_before_initial_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(ranking_set, "PROJECT_ROOT", tmp_path)
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    artifacts = tmp_path / "artifacts"
    data_dir.mkdir()
    model_dir.mkdir()
    artifacts.mkdir()
    for path in (data_dir / "features.parquet", data_dir / "universe.parquet", model_dir / "latest_lgbm.pkl", tmp_path / "signals.yaml"):
        path.write_bytes(b"fixture")
    authority_path = artifacts / "automation_status.json"
    authority = {
        "status": "OK", "run_date": "2026-09-01",
        "steps": [{"name": "data.freshness.after_etl", "status": "OK"}, {"name": "ranking", "status": "OK"}],
        "metadata": {"data_freshness": {"datasets": {
            "features.parquet": {"latest_date": "2026-09-01", "latest_market_coverage": {"markets": [{"market_type": "TWSE", "status": "OK"}, {"market_type": "TPEX", "status": "OK"}]}},
            "universe.parquet": {"latest_date": "2026-09-01"},
        }}},
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    original_validate = ranking_set.validate_completed_trade_date_authority

    def validate_then_replace(**kwargs):
        result = original_validate(**kwargs)
        authority_path.write_text(json.dumps({**authority, "replacement": True}), encoding="utf-8")
        return result

    monkeypatch.setattr(ranking_set, "validate_completed_trade_date_authority", validate_then_replace)
    monkeypatch.setattr(ranking_set, "load_trade_dates", lambda **_kwargs: ["2026-09-01"])
    monkeypatch.setattr(ranking_set, "producer_source_lineage", lambda *_args: {"source_commit": "a" * 40, "dependencies": []})

    with pytest.raises(ranking_set.RankingProvenanceError, match="validation 與 initial snapshot 間漂移"):
        ranking_set.build_payload(Namespace(
            start_date="2026-09-01", end_date="2026-09-01", data_dir=str(data_dir), model_dir=str(model_dir),
            config=str(tmp_path / "signals.yaml"), output_dir=str(tmp_path / "output"), stride=1, max_dates=None,
            top_n=10, legacy_per_date_load=False, manifest=str(tmp_path / "output" / "manifest.json"),
            scenario="baseline_research", forward_capture=True, capture_trade_date="2026-09-01",
            capture_authority_artifact="artifacts/automation_status.json", run_identity="authority-replaced",
        ))
