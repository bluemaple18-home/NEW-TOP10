from argparse import Namespace
from pathlib import Path

from scripts import build_historical_ranking_replay_set as ranking_set


def test_manifest_records_current_model_source_lineage(tmp_path, monkeypatch):
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

        def load_model(self):
            return None

    monkeypatch.setattr(ranking_set, "StockRanker", FakeRanker)
    monkeypatch.setattr(ranking_set, "load_trade_dates", lambda **_kwargs: ["2026-03-13"])
    monkeypatch.setattr(ranking_set, "prepare_batch_frames", lambda _ranker: (object(), object()))
    monkeypatch.setattr(
        ranking_set,
        "run_batch_ranking_for_date",
        lambda ranker, *_args: ranker.artifact_dir / "ranking_2026-03-13.csv",
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
        )
    )

    lineage = payload["source_lineage"]
    assert lineage["features_path"] == str(data_dir / "features.parquet")
    assert lineage["features_sha256"] == ranking_set.sha256_file(data_dir / "features.parquet")
    assert lineage["universe_path"] == str(data_dir / "universe.parquet")
    assert lineage["universe_sha256"] == ranking_set.sha256_file(data_dir / "universe.parquet")
    assert lineage["model_path"] == str(model_dir / "latest_lgbm.pkl")
    assert lineage["model_sha256"] == ranking_set.sha256_file(model_dir / "latest_lgbm.pkl")
    assert lineage["config_path"] == str(config_path)
    assert lineage["config_sha256"] == ranking_set.sha256_file(config_path)
