from __future__ import annotations

import hashlib
import json
import pickle
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import pandas as pd

from app.contracts.daily_v2_comparison import build_ranking_comparison
from app.workflows.daily_v2_real_shadow import RealShadowExecutionError, run_real_shadow
from scripts import run_daily_v2


RUN_DATE = "2026-07-09"
RUN_ID = "daily-v2-20260709-real-shadow"


def ranking_rows(stock_ids: list[str] | None = None) -> list[dict[str, object]]:
    ids = stock_ids or [str(2300 + index) for index in range(1, 11)]
    return [
        {
            "rank": rank,
            "stock_id": stock_id,
            "risk_adjusted_score": round(1 - rank / 100, 6),
            "model_prob": round(0.9 - rank / 100, 6),
        }
        for rank, stock_id in enumerate(ids, start=1)
    ]


def write_ranking(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_ranker_class(
    rows: list[dict[str, object]],
    *,
    returned_path: Path | None = None,
    model_warning: Warning | None = None,
) -> type:
    class FakeStockRanker:
        def __init__(self, *, artifact_dir: str, **_: object) -> None:
            self.artifact_dir = Path(artifact_dir)

        def load_model(self, filename: str = "latest_lgbm.pkl") -> None:
            self.model_filename = filename
            if model_warning is not None:
                warnings.warn(model_warning, stacklevel=2)

        def run_ranking(self, date: str | None = None) -> Path:
            output = returned_path or self.artifact_dir / f"ranking_{date}.csv"
            if returned_path is None:
                write_ranking(output, rows)
            return output

    return FakeStockRanker


class DailyV2RealShadowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="top10-daily-v2-real-")
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data" / "clean"
        self.model_dir = self.root / "models"
        self.workspace = self.root / "artifacts" / "shadow" / "daily_v2"
        self.baseline_path = self.root / "artifacts" / f"ranking_{RUN_DATE}.csv"
        self.data_dir.mkdir(parents=True)
        self.model_dir.mkdir(parents=True)
        (self.data_dir / "features.parquet").write_bytes(b"fixture-features")
        with (self.model_dir / "latest_lgbm.pkl").open("wb") as handle:
            pickle.dump({"model": object()}, handle)
        write_ranking(self.baseline_path, ranking_rows())

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_with_fake_ranker(self, rows: list[dict[str, object]]) -> dict[str, object]:
        with mock.patch(
            "app.workflows.daily_v2_real_shadow.StockRanker",
            fake_ranker_class(rows),
        ):
            return run_real_shadow(
                run_id=RUN_ID,
                run_date=RUN_DATE,
                workspace=self.workspace,
                data_dir=self.data_dir,
                model_dir=self.model_dir,
                baseline_ranking=self.baseline_path,
            )

    def test_identical_fixture_returns_go_and_preserves_sources(self) -> None:
        source_paths = [
            self.data_dir / "features.parquet",
            self.model_dir / "latest_lgbm.pkl",
            self.baseline_path,
        ]
        before = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}

        result = self.run_with_fake_ranker(ranking_rows())

        run_dir = self.workspace / RUN_ID
        self.assertEqual(result["status"], "GO")
        self.assertEqual(
            {path.name for path in run_dir.iterdir()},
            {f"ranking_{RUN_DATE}.csv", "comparison.json", "manifest.json"},
        )
        comparison = json.loads((run_dir / "comparison.json").read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(comparison["status"], "GO")
        self.assertEqual(comparison["top10"]["overlap_count"], 10)
        self.assertTrue(comparison["top10"]["same_order"])
        self.assertTrue(comparison["numeric_differences"]["core_within_tolerance"])
        self.assertTrue(manifest["inputs_unchanged"])
        self.assertTrue(manifest["shadow_only"])
        self.assertFalse(manifest["live_send_enabled"])
        self.assertTrue(
            all(
                item["sha256"]
                for item in manifest["inputs_before"].values()
                if item["required"]
            )
        )
        after = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}
        self.assertEqual(after, before)

    def test_corrupt_real_model_fails_loud_and_records_failure(self) -> None:
        (self.model_dir / "latest_lgbm.pkl").write_bytes(b"not-a-pickle")

        with self.assertRaisesRegex(RealShadowExecutionError, "model load failed"):
            run_real_shadow(
                run_id=RUN_ID,
                run_date=RUN_DATE,
                workspace=self.workspace,
                data_dir=self.data_dir,
                model_dir=self.model_dir,
                baseline_ranking=self.baseline_path,
            )

        manifest = json.loads(
            (self.workspace / RUN_ID / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("model load failed", manifest["error"]["message"])
        self.assertFalse((self.workspace / RUN_ID / f"ranking_{RUN_DATE}.csv").exists())

    def test_model_compatibility_warning_blocks_only_production_switch(self) -> None:
        class InconsistentVersionWarning(UserWarning):
            pass

        with mock.patch(
            "app.workflows.daily_v2_real_shadow.StockRanker",
            fake_ranker_class(
                ranking_rows(),
                model_warning=InconsistentVersionWarning(
                    "Trying to unpickle estimator from scikit-learn 1.8.0 under 1.9.0"
                ),
            ),
        ):
            result = run_real_shadow(
                run_id=RUN_ID,
                run_date=RUN_DATE,
                workspace=self.workspace,
                data_dir=self.data_dir,
                model_dir=self.model_dir,
                baseline_ranking=self.baseline_path,
            )

        run_dir = self.workspace / RUN_ID
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        comparison = json.loads((run_dir / "comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "GO")
        self.assertEqual(result["production_switch_status"], "NO-GO")
        self.assertTrue(manifest["model_compatibility"]["version_mismatch"])
        self.assertTrue(manifest["model_compatibility"]["warnings"])
        self.assertIn("python", manifest["runtime_versions"])
        self.assertIn("scikit-learn", manifest["runtime_versions"])
        self.assertEqual(comparison["status"], "GO")
        self.assertEqual(comparison["production_switch"]["status"], "NO-GO")
        self.assertEqual(
            comparison["model_compatibility"],
            manifest["model_compatibility"],
        )

    def test_missing_requested_trade_date_fails_loud(self) -> None:
        pd.DataFrame(
            [{"date": "2026-07-08", "stock_id": "2330", "close": 100.0}]
        ).to_parquet(self.data_dir / "features.parquet", index=False)

        with self.assertRaisesRegex(RealShadowExecutionError, "找不到指定交易日資料"):
            run_real_shadow(
                run_id=RUN_ID,
                run_date=RUN_DATE,
                workspace=self.workspace,
                data_dir=self.data_dir,
                model_dir=self.model_dir,
                baseline_ranking=self.baseline_path,
            )

        manifest = json.loads(
            (self.workspace / RUN_ID / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")

    def test_run_id_cannot_escape_workspace(self) -> None:
        with self.assertRaisesRegex(ValueError, "run_id"):
            run_real_shadow(
                run_id="../escape",
                run_date=RUN_DATE,
                workspace=self.workspace,
                data_dir=self.data_dir,
                model_dir=self.model_dir,
                baseline_ranking=self.baseline_path,
            )
        self.assertFalse((self.workspace.parent / "escape").exists())

    def test_wrong_date_baseline_fails_before_manifest_or_ranker(self) -> None:
        wrong_baseline = self.root / "artifacts" / "ranking_2026-07-08.csv"
        write_ranking(wrong_baseline, ranking_rows())
        source_paths = [
            self.data_dir / "features.parquet",
            self.model_dir / "latest_lgbm.pkl",
            wrong_baseline,
        ]
        before = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}

        with mock.patch("app.workflows.daily_v2_real_shadow.StockRanker") as ranker:
            with self.assertRaisesRegex(ValueError, "baseline ranking date mismatch"):
                run_real_shadow(
                    run_id=RUN_ID,
                    run_date=RUN_DATE,
                    workspace=self.workspace,
                    data_dir=self.data_dir,
                    model_dir=self.model_dir,
                    baseline_ranking=wrong_baseline,
                )

        self.assertFalse((self.workspace / RUN_ID).exists())
        ranker.assert_not_called()
        after = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}
        self.assertEqual(after, before)

        wrong_content_rows = ranking_rows()
        for row in wrong_content_rows:
            row["run_date"] = "2026-07-08"
        write_ranking(self.baseline_path, wrong_content_rows)
        content_sources = [
            self.data_dir / "features.parquet",
            self.model_dir / "latest_lgbm.pkl",
            self.baseline_path,
        ]
        content_before = {
            path: (sha256(path), path.stat().st_mtime_ns) for path in content_sources
        }
        with mock.patch("app.workflows.daily_v2_real_shadow.StockRanker") as ranker:
            with self.assertRaisesRegex(ValueError, "baseline ranking date mismatch"):
                run_real_shadow(
                    run_id=RUN_ID,
                    run_date=RUN_DATE,
                    workspace=self.workspace,
                    data_dir=self.data_dir,
                    model_dir=self.model_dir,
                    baseline_ranking=self.baseline_path,
                )
        self.assertFalse((self.workspace / RUN_ID).exists())
        ranker.assert_not_called()
        content_after = {
            path: (sha256(path), path.stat().st_mtime_ns) for path in content_sources
        }
        self.assertEqual(content_after, content_before)

    def test_model_filename_traversal_fails_before_manifest_or_ranker(self) -> None:
        escaped_model = self.root / "escaped_model.pkl"
        escaped_model.write_bytes(b"outside-model-dir")
        source_paths = [
            self.data_dir / "features.parquet",
            self.model_dir / "latest_lgbm.pkl",
            escaped_model,
            self.baseline_path,
        ]
        before = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}

        with mock.patch("app.workflows.daily_v2_real_shadow.StockRanker") as ranker:
            with self.assertRaisesRegex(ValueError, "model path must stay within model_dir"):
                run_real_shadow(
                    run_id=RUN_ID,
                    run_date=RUN_DATE,
                    workspace=self.workspace,
                    data_dir=self.data_dir,
                    model_dir=self.model_dir,
                    model_filename="../escaped_model.pkl",
                    baseline_ranking=self.baseline_path,
                )

        self.assertFalse((self.workspace / RUN_ID).exists())
        ranker.assert_not_called()
        after = {path: (sha256(path), path.stat().st_mtime_ns) for path in source_paths}
        self.assertEqual(after, before)

    def test_ranker_return_path_outside_run_dir_fails_loud(self) -> None:
        outside = self.root / "outside.csv"
        with mock.patch(
            "app.workflows.daily_v2_real_shadow.StockRanker",
            fake_ranker_class(ranking_rows(), returned_path=outside),
        ):
            with self.assertRaisesRegex(RealShadowExecutionError, "outside shadow run directory"):
                run_real_shadow(
                    run_id=RUN_ID,
                    run_date=RUN_DATE,
                    workspace=self.workspace,
                    data_dir=self.data_dir,
                    model_dir=self.model_dir,
                    baseline_ranking=self.baseline_path,
                )
        self.assertFalse(outside.exists())

    def test_schema_mismatch_is_explicit_no_go(self) -> None:
        shadow_path = self.root / "shadow_schema.csv"
        rows = ranking_rows()
        for row in rows:
            row["unexpected"] = 1
        write_ranking(shadow_path, rows)

        comparison = build_ranking_comparison(
            baseline_path=self.baseline_path,
            shadow_path=shadow_path,
            input_snapshots={"features": {"sha256": "abc"}},
        )

        self.assertEqual(comparison["status"], "NO-GO")
        self.assertTrue(comparison["schema"]["blocking"])
        self.assertEqual(comparison["schema"]["extra_in_shadow"], ["unexpected"])

    def test_top10_order_mismatch_is_explicit_no_go(self) -> None:
        shadow_path = self.root / "shadow_order.csv"
        reordered = ranking_rows()
        reordered[0]["stock_id"], reordered[1]["stock_id"] = (
            reordered[1]["stock_id"],
            reordered[0]["stock_id"],
        )
        write_ranking(shadow_path, reordered)

        comparison = build_ranking_comparison(
            baseline_path=self.baseline_path,
            shadow_path=shadow_path,
            input_snapshots={"features": {"sha256": "abc"}},
        )

        self.assertEqual(comparison["status"], "NO-GO")
        self.assertEqual(comparison["top10"]["overlap_count"], 10)
        self.assertFalse(comparison["top10"]["same_order"])
        self.assertTrue(any(row["status"] == "moved" for row in comparison["rank_changes"]))

    def test_core_score_outside_tolerance_is_explicit_no_go(self) -> None:
        shadow_path = self.root / "shadow_score.csv"
        rows = ranking_rows()
        rows[0]["risk_adjusted_score"] = 0.5
        write_ranking(shadow_path, rows)

        comparison = build_ranking_comparison(
            baseline_path=self.baseline_path,
            shadow_path=shadow_path,
            input_snapshots={"features": {"sha256": "abc"}},
            numeric_tolerance=1e-9,
        )

        self.assertEqual(comparison["status"], "NO-GO")
        self.assertFalse(comparison["numeric_differences"]["core_within_tolerance"])
        self.assertGreater(
            comparison["numeric_differences"]["columns"]["risk_adjusted_score"][
                "max_absolute_difference"
            ],
            1e-9,
        )

    def test_cli_real_source_uses_thin_adapter_entry(self) -> None:
        adapter_result = {
            "status": "GO",
            "production_switch_status": "NO-GO",
            "run_id": RUN_ID,
            "manifest": "manifest.json",
            "comparison": "comparison.json",
            "live_send_enabled": False,
        }
        argv = [
            "scripts/run_daily_v2.py",
            "--dry-run",
            "--source",
            "real",
            "--run-date",
            RUN_DATE,
            "--run-id",
            RUN_ID,
            "--data-dir",
            str(self.data_dir),
            "--model-dir",
            str(self.model_dir),
            "--baseline-ranking",
            str(self.baseline_path),
            "--workspace",
            str(self.workspace),
        ]
        with (
            mock.patch.object(run_daily_v2.sys, "argv", argv),
            mock.patch.object(
                run_daily_v2,
                "run_real_shadow",
                return_value=adapter_result,
                create=True,
            ) as adapter,
        ):
            exit_code = run_daily_v2.main()

        self.assertEqual(exit_code, 0)
        adapter.assert_called_once()
        called = adapter.call_args.kwargs
        self.assertEqual(called["run_date"], RUN_DATE)
        self.assertEqual(called["baseline_ranking"], self.baseline_path)


if __name__ == "__main__":
    unittest.main()
