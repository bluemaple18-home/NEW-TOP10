from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.research import ranking_provenance_receipt as receipts


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _metadata(project: Path) -> tuple[dict, dict, dict, dict, dict]:
    model = _write(project / "models/model-a.pkl", "model")
    config = _write(project / "config/signals.yaml", "scoring: {}\n")
    universe = _write(project / "data/clean/universe.parquet", "universe")
    features = _write(project / "data/clean/features.parquet", "features")
    source = _write(project / "scripts/producer.py", "print('producer')\n")
    return (
        {"path": model.relative_to(project).as_posix(), "version": model.name, "sha256": receipts.sha256_file(model)},
        {"path": config.relative_to(project).as_posix(), "sha256": receipts.sha256_file(config)},
        {"path": universe.relative_to(project).as_posix(), "sha256": receipts.sha256_file(universe)},
        {"path": features.relative_to(project).as_posix(), "sha256": receipts.sha256_file(features)},
        {"source_commit": "a" * 40, "dependencies": [{"path": source.relative_to(project).as_posix(), "sha256": receipts.sha256_file(source)}]},
    )


def test_stable_top_n_uses_score_desc_stock_id_asc_and_rejects_short_or_duplicate() -> None:
    frame = pd.DataFrame({"stock_id": ["2330", "1101", "0050"], "score": [1.0, 1.0, 0.5]})
    actual = receipts.stable_ranked_top_n(frame, score_column="score", top_n=2)
    assert actual["stock_id"].tolist() == ["1101", "2330"]
    assert actual["rank"].tolist() == [1, 2]
    with pytest.raises(receipts.RankingProvenanceError, match="row count"):
        receipts.stable_ranked_top_n(frame, score_column="score", top_n=4)
    with pytest.raises(receipts.RankingProvenanceError, match="唯一"):
        receipts.stable_ranked_top_n(pd.DataFrame({"stock_id": ["1", "1"], "score": [2, 1]}), score_column="score", top_n=2)


def test_forward_mode_requires_explicit_single_matching_capture_date() -> None:
    assert receipts.ensure_capture_mode(
        capture_mode=receipts.REPLAY_GENERATED, ranking_dates=["2026-08-16", "2026-08-17"], capture_trade_date=None
    ) == (False, False)
    assert receipts.ensure_capture_mode(
        capture_mode=receipts.FORWARD_CAPTURE, ranking_dates=["2026-08-16"], capture_trade_date="2026-08-16"
    ) == (True, "pending_registration")
    with pytest.raises(receipts.RankingProvenanceError, match="單一"):
        receipts.ensure_capture_mode(
            capture_mode=receipts.FORWARD_CAPTURE, ranking_dates=["2026-08-16", "2026-08-17"], capture_trade_date="2026-08-16"
        )


def test_complete_bundle_is_canonical_create_only_and_verifiable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = project / "artifacts/out"
    model, config, universe, features, lineage = _metadata(project)
    bundle = receipts.BundleRun(
        project_root=project, output_dir=output, scenario="baseline", producer_entrypoint="scripts/producer.py",
        planned_dates=["2026-08-16"], capture_mode=receipts.REPLAY_GENERATED, capture_trade_date=None,
        run_identity="run",
    )
    _write(bundle.staging_dir / "model_snapshots/model-a.pkl", "model")
    staged = _write(bundle.ranking_dir / "ranking_2026-08-16.csv", "rank,stock_id,score\n1,1101,1\n")
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="run",
        batch_plan=bundle.plan_id, ranking_path=staged, published_ranking_path=output / staged.name,
        producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model, config=config,
        universe=universe, feature_calendar=features, top_n=1, capture_mode=receipts.REPLAY_GENERATED,
        admission_eligible=False,
    )
    bundle.add_receipt("2026-08-16", receipt)
    before = {"features": features}
    manifest = bundle.complete(before_inputs=before, after_inputs=before)
    assert receipts.verify_complete_bundle(project, manifest) == []
    assert json.loads(manifest.read_text(encoding="utf-8"))["status"] == "COMPLETE"
    assert not bundle.staging_dir.exists()
    with pytest.raises(receipts.RankingProvenanceError, match="已存在"):
        receipts.BundleRun(
            project_root=project, output_dir=output, scenario="baseline", producer_entrypoint="scripts/producer.py",
            planned_dates=["2026-08-16"], capture_mode=receipts.REPLAY_GENERATED, capture_trade_date=None,
            run_identity="run",
        )


def test_receipt_rejects_false_admission_absolute_path_outcome_and_noncanonical_identity(tmp_path: Path) -> None:
    project = tmp_path / "project"
    model, config, universe, features, lineage = _metadata(project)
    ranking = _write(project / "artifacts/out/ranking_2026-08-16.csv", "rank,stock_id,score\n1,1101,1\n")
    with pytest.raises(receipts.RankingProvenanceError, match="REPLAY"):
        receipts.build_receipt(
            project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="run", batch_plan="sha256:" + "1" * 64,
            ranking_path=ranking, producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model,
            config=config, universe=universe, feature_calendar=features, top_n=1,
            capture_mode=receipts.REPLAY_GENERATED, admission_eligible="pending_registration",
        )
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="run", batch_plan="sha256:" + "1" * 64,
        ranking_path=ranking, producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model,
        config=config, universe=universe, feature_calendar=features, top_n=1,
        capture_mode=receipts.REPLAY_GENERATED, admission_eligible=False,
    )
    receipt["model"]["path"] = "/tmp/latest_lgbm.pkl"
    receipt["profit"] = 1
    assert "model" in receipts.validate_receipt(receipt)
    assert "outcome_key" in receipts.validate_receipt(receipt)
    assert "receipt_identity" in receipts.validate_receipt(receipt)
