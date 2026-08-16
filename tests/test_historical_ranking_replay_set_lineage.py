from argparse import Namespace
from pathlib import Path

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
