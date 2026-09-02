from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from app.research import ranking_provenance_receipt as receipts


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _authority_payload(date_text: str = "2026-09-01") -> dict:
    return {
        "schema_version": "automation-status.v1",
        "run_date": date_text,
        "mode": "daily",
        "status": "OK",
        "steps": [
            {"name": "data.freshness.after_etl", "status": "OK"},
            {"name": "ranking", "status": "OK"},
        ],
        "metadata": {
            "data_freshness": {
                "datasets": {
                    "features.parquet": {
                        "latest_date": date_text,
                        "latest_market_coverage": {
                            "markets": [
                                {"market_type": "TWSE", "status": "OK"},
                                {"market_type": "TPEX", "status": "OK"},
                            ]
                        },
                    },
                    "universe.parquet": {"latest_date": date_text},
                }
            }
        },
    }


def _write_authority(project: Path, payload: dict, name: str = "automation_status_2026-09-01.json") -> Path:
    return _write(project / "artifacts" / name, json.dumps(payload, ensure_ascii=False, sort_keys=True))


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
        capture_mode=receipts.FORWARD_CAPTURE, ranking_dates=["2026-08-16"], capture_trade_date="2026-08-16",
        trusted_capture_trade_date="2026-08-16",
    ) == (True, "pending_registration")
    with pytest.raises(receipts.RankingProvenanceError, match="單一"):
        receipts.ensure_capture_mode(
            capture_mode=receipts.FORWARD_CAPTURE, ranking_dates=["2026-08-16", "2026-08-17"], capture_trade_date="2026-08-16",
            trusted_capture_trade_date="2026-08-16",
        )


def test_completed_trade_date_authority_accepts_local_completion_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    path = _write_authority(project, _authority_payload())
    trusted_date, meta = receipts.validate_completed_trade_date_authority(
        project_root=project,
        authority_artifact=path.relative_to(project).as_posix(),
        capture_trade_date="2026-09-01",
    )
    assert trusted_date == "2026-09-01"
    assert meta == {"path": "artifacts/automation_status_2026-09-01.json", "sha256": receipts.sha256_file(path)}


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda payload: payload.update({"status": "FAILED"}), "status"),
        (lambda payload: payload.update({"run_date": "2026-09-02"}), "run_date"),
        (lambda payload: payload.update({"steps": [step for step in payload["steps"] if step["name"] != "data.freshness.after_etl"]}), "after-ETL"),
        (lambda payload: payload["steps"][0].update({"status": "FAILED"}), "after-ETL"),
        (lambda payload: payload["metadata"]["data_freshness"]["datasets"]["features.parquet"].update({"latest_date": "2026-08-31"}), "features latest_date"),
        (lambda payload: payload["metadata"]["data_freshness"]["datasets"]["universe.parquet"].update({"latest_date": "2026-08-31"}), "universe latest_date"),
        (lambda payload: payload["metadata"]["data_freshness"]["datasets"]["features.parquet"]["latest_market_coverage"].update({"markets": [{"market_type": "TWSE", "status": "OK"}]}), "TWSE/TPEX"),
        (lambda payload: payload["metadata"]["data_freshness"]["datasets"]["features.parquet"]["latest_market_coverage"]["markets"][1].update({"status": "FAILED"}), "TWSE/TPEX"),
        (lambda payload: payload["steps"][1].update({"status": "FAILED"}), "ranking OK"),
    ],
)
def test_completed_trade_date_authority_rejects_incomplete_or_stale_evidence(tmp_path: Path, mutate, match: str) -> None:
    project = tmp_path / "project"
    payload = _authority_payload()
    mutate(payload)
    path = _write_authority(project, payload)
    with pytest.raises(receipts.RankingProvenanceError, match=match):
        receipts.validate_completed_trade_date_authority(
            project_root=project,
            authority_artifact=path.relative_to(project).as_posix(),
            capture_trade_date="2026-09-01",
        )


def test_completed_trade_date_authority_rejects_missing_or_non_repo_relative_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(receipts.RankingProvenanceError, match="不可讀"):
        receipts.validate_completed_trade_date_authority(
            project_root=project,
            authority_artifact="artifacts/missing.json",
            capture_trade_date="2026-09-01",
        )
    path = _write_authority(project, _authority_payload())
    with pytest.raises(receipts.RankingProvenanceError, match="絕對路徑"):
        receipts.validate_completed_trade_date_authority(
            project_root=project,
            authority_artifact=str(path),
            capture_trade_date="2026-09-01",
        )


def test_completed_trade_date_authority_bytes_drift_fails_input_snapshot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    path = _write_authority(project, _authority_payload())
    before = receipts.snapshot_inputs(project, {"completed_trade_date_authority": path})
    _write_authority(project, _authority_payload("2026-09-02"))
    after = receipts.snapshot_inputs(project, {"completed_trade_date_authority": path})
    with pytest.raises(receipts.RankingProvenanceError, match="strict input"):
        receipts.assert_same_inputs(before, after)
    with pytest.raises(receipts.RankingProvenanceError, match="trusted"):
        receipts.ensure_capture_mode(
            capture_mode=receipts.FORWARD_CAPTURE, ranking_dates=["2026-08-15"], capture_trade_date="2026-08-15",
            trusted_capture_trade_date="2026-08-16",
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
        admission_eligible=False, score_column="score",
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
            capture_mode=receipts.REPLAY_GENERATED, admission_eligible="pending_registration", score_column="score",
        )
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="run", batch_plan="sha256:" + "1" * 64,
        ranking_path=ranking, producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model,
        config=config, universe=universe, feature_calendar=features, top_n=1,
        capture_mode=receipts.REPLAY_GENERATED, admission_eligible=False, score_column="score",
    )
    receipt["model"]["path"] = "/tmp/latest_lgbm.pkl"
    receipt["profit"] = 1
    assert "model" in receipts.validate_receipt(receipt)
    assert "outcome_key" in receipts.validate_receipt(receipt)
    assert "receipt_identity" in receipts.validate_receipt(receipt)


def test_semantic_verifier_rejects_short_top_n_and_unstable_score_order(tmp_path: Path) -> None:
    short = _write(tmp_path / "short.csv", "rank,stock_id,score\n1,1101,1\n")
    policy = {"top_n": 10, "score_column": "score"}
    assert "ranking_row_count" in receipts.verify_ranking_semantics(short, policy)
    unordered = _write(tmp_path / "unordered.csv", "rank,stock_id,score\n1,2330,1\n2,1101,1\n")
    assert "ranking_sort_policy" in receipts.verify_ranking_semantics(
        unordered, {"top_n": 2, "score_column": "score"}
    )


def test_unknown_receipt_extra_is_rejected_even_when_rehashed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    model, config, universe, features, lineage = _metadata(project)
    ranking = _write(project / "artifacts/out/ranking_2026-08-16.csv", "rank,stock_id,score\n1,1101,1\n")
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="run", batch_plan="sha256:" + "1" * 64,
        ranking_path=ranking, producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model,
        config=config, universe=universe, feature_calendar=features, top_n=1,
        capture_mode=receipts.REPLAY_GENERATED, admission_eligible=False, score_column="score",
    )
    receipt["strict_inputs"] = {"future_price": {"path": "x.csv", "sha256": "sha256:" + "2" * 64}}
    receipt["receipt_identity"] = receipts.content_hash({key: value for key, value in receipt.items() if key != "receipt_identity"})
    errors = receipts.validate_receipt(receipt)
    assert "strict_inputs" in errors
    assert "outcome_key" in errors


def test_publish_failure_rolls_back_hardlinked_ranking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    output = project / "artifacts/out"
    model, config, universe, features, lineage = _metadata(project)
    bundle = receipts.BundleRun(
        project_root=project, output_dir=output, scenario="baseline", producer_entrypoint="scripts/producer.py",
        planned_dates=["2026-08-16"], capture_mode=receipts.REPLAY_GENERATED, capture_trade_date=None,
        run_identity="rollback",
    )
    _write(bundle.staging_dir / "model_snapshots/model-a.pkl", "model")
    staged = _write(bundle.ranking_dir / "ranking_2026-08-16.csv", "rank,stock_id,score\n1,1101,1\n")
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="rollback",
        batch_plan=bundle.plan_id, ranking_path=staged, published_ranking_path=output / staged.name,
        producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model, config=config,
        universe=universe, feature_calendar=features, top_n=1, capture_mode=receipts.REPLAY_GENERATED,
        admission_eligible=False, score_column="score",
    )
    bundle.add_receipt("2026-08-16", receipt)
    monkeypatch.setattr(receipts.shutil, "copytree", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(receipts.RankingProvenanceError, match="rolled back"):
        bundle.complete(before_inputs={"x": 1}, after_inputs={"x": 1})
    assert not (output / "ranking_2026-08-16.csv").exists()
    assert not bundle.final_dir.exists()
    assert (bundle.staging_dir / "FAILED.json").is_file()


def test_bundle_rejects_caller_date_and_artifact_filename_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = project / "artifacts/out"
    model, config, universe, features, lineage = _metadata(project)
    bundle = receipts.BundleRun(
        project_root=project, output_dir=output, scenario="baseline", producer_entrypoint="scripts/producer.py",
        planned_dates=["2026-08-16"], capture_mode=receipts.REPLAY_GENERATED, capture_trade_date=None,
        run_identity="binding",
    )
    staged = _write(bundle.ranking_dir / "ranking_2026-08-16.csv", "rank,stock_id,score\n1,1101,1\n")
    receipt = receipts.build_receipt(
        project_root=project, scenario="baseline", ranking_date="2026-08-16", run_identity="binding",
        batch_plan=bundle.plan_id, ranking_path=staged, published_ranking_path=output / staged.name,
        producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model, config=config,
        universe=universe, feature_calendar=features, top_n=1, capture_mode=receipts.REPLAY_GENERATED,
        admission_eligible=False, score_column="score",
    )
    receipt["ranking_date"] = "2026-08-17"
    receipt["receipt_identity"] = receipts.content_hash({key: value for key, value in receipt.items() if key != "receipt_identity"})
    with pytest.raises(receipts.RankingProvenanceError, match="planned ranking identity"):
        bundle.add_receipt("2026-08-16", receipt)
    receipt["ranking_date"] = "2026-08-16"
    receipt["ranking_artifact"]["path"] = "artifacts/out/ranking_2026-08-17.csv"
    receipt["receipt_identity"] = receipts.content_hash({key: value for key, value in receipt.items() if key != "receipt_identity"})
    with pytest.raises(receipts.RankingProvenanceError, match="planned ranking identity"):
        bundle.add_receipt("2026-08-16", receipt)


def test_verifier_rejects_swapped_receipt_even_if_manifest_rehashed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = project / "artifacts/out"
    model, config, universe, features, lineage = _metadata(project)
    bundle = receipts.BundleRun(
        project_root=project, output_dir=output, scenario="baseline", producer_entrypoint="scripts/producer.py",
        planned_dates=["2026-08-16", "2026-08-17"], capture_mode=receipts.REPLAY_GENERATED,
        capture_trade_date=None, run_identity="swap",
    )
    _write(bundle.staging_dir / "model_snapshots/model-a.pkl", "model")
    for date_text in bundle.planned_dates:
        staged = _write(bundle.ranking_dir / f"ranking_{date_text}.csv", "rank,stock_id,score\n1,1101,1\n")
        receipt = receipts.build_receipt(
            project_root=project, scenario="baseline", ranking_date=date_text, run_identity="swap",
            batch_plan=bundle.plan_id, ranking_path=staged, published_ranking_path=output / staged.name,
            producer_entrypoint="scripts/producer.py", producer_lineage=lineage, model=model, config=config,
            universe=universe, feature_calendar=features, top_n=1, capture_mode=receipts.REPLAY_GENERATED,
            admission_eligible=False, score_column="score",
        )
        bundle.add_receipt(date_text, receipt)
    manifest_path = bundle.complete(before_inputs={"x": 1}, after_inputs={"x": 1})
    first = manifest_path.parent / "receipts" / "ranking_2026-08-16.receipt.json"
    second = manifest_path.parent / "receipts" / "ranking_2026-08-17.receipt.json"
    first_raw, second_raw = first.read_bytes(), second.read_bytes()
    first.write_bytes(second_raw)
    second.write_bytes(first_raw)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        receipt_path = project / entry["receipt"]["path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        entry["receipt"]["sha256"] = receipts.sha256_file(receipt_path)
        entry["receipt"]["receipt_identity"] = receipt["receipt_identity"]
    manifest["manifest_identity"] = receipts.content_hash({key: value for key, value in manifest.items() if key != "manifest_identity"})
    manifest_path.write_bytes(receipts.canonical_encode(manifest))
    assert "receipt_manifest_identity_mismatch" in receipts.verify_complete_bundle(project, manifest_path)


def test_source_lineage_expands_tracked_trading_and_ignores_unrelated_dirty(tmp_path: Path) -> None:
    project = tmp_path / "project"
    producer = _write(project / "scripts/producer.py", "print('ok')\n")
    policy = _write(project / "app/trading/ranking_policy.py", "VALUE = 1\n")
    factor_registry = _write(project / "app/modeling/factor_registry.py", "VALUE = 1\n")
    _write(project / "README.md", "clean\n")
    for command in (("init",), ("config", "user.email", "test@example.com"), ("config", "user.name", "test"), ("add", "."), ("commit", "-m", "fixture")):
        subprocess.run(["git", "-C", str(project), *command], check=True, capture_output=True)
    lineage = receipts.producer_source_lineage(project, [producer, project / "app/trading", factor_registry])
    assert {row["path"] for row in lineage["dependencies"]} == {"app/modeling/factor_registry.py", "app/trading/ranking_policy.py", "scripts/producer.py"}
    policy.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(receipts.RankingProvenanceError, match="非 HEAD"):
        receipts.producer_source_lineage(project, [producer, project / "app/trading", factor_registry])
    policy.write_text("VALUE = 1\n", encoding="utf-8")
    factor_registry.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(receipts.RankingProvenanceError, match="非 HEAD"):
        receipts.producer_source_lineage(project, [producer, project / "app/trading", factor_registry])
    factor_registry.write_text("VALUE = 1\n", encoding="utf-8")
    (project / "README.md").write_text("unrelated dirty\n", encoding="utf-8")
    assert receipts.producer_source_lineage(project, [producer, project / "app/trading", factor_registry])["source_commit"] == lineage["source_commit"]
