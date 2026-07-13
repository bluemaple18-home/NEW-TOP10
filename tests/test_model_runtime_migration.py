from __future__ import annotations

import hashlib
import json
import pickle
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import numpy as np
import sklearn
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.isotonic import IsotonicRegression

from app.modeling.model_runtime_migration import build_migration_candidate


class FixtureBooster:
    def __init__(self, feature_names: list[str]) -> None:
        self._feature_names = feature_names

    def model_to_string(self) -> str:
        return "tree\nfeature=factor_a factor_b\nend of trees"

    def feature_name(self) -> list[str]:
        return list(self._feature_names)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_old_runtime_fixture(path: Path) -> dict[str, object]:
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        np.array([0.0, 0.2, 0.5, 0.8, 1.0]),
        np.array([0.0, 0.0, 0.4, 1.0, 1.0]),
    )
    payload: dict[str, object] = {
        "model": FixtureBooster(["factor_a", "factor_b"]),
        "calibrator": calibrator,
        "feature_names": ["factor_a", "factor_b"],
        "metadata": {
            "feature_count": 2,
            "feature_names": ["factor_a", "factor_b"],
            "horizon": 5,
            "notes": "synthetic fixture",
        },
    }
    serialized = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    current_version = sklearn.__version__.encode("ascii")
    if current_version != b"1.9.0" or serialized.count(current_version) != 1:
        raise RuntimeError("fixture 需要 sklearn 1.9.0 runtime")
    path.write_bytes(serialized.replace(current_version, b"1.8.0"))
    return payload


class ModelRuntimeMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="top10-model-runtime-")
        self.root = Path(self.tempdir.name)
        self.source = self.root / "models" / "latest_lgbm.pkl"
        self.candidate = self.root / "artifacts" / "shadow" / "candidate.pkl"
        self.report = self.root / "artifacts" / "shadow" / "verdict.json"
        self.source.parent.mkdir(parents=True)
        self.original_payload = write_old_runtime_fixture(self.source)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_captures_source_warning_and_candidate_reloads_without_warning(self) -> None:
        result = build_migration_candidate(self.source, self.candidate, self.report)

        self.assertEqual(result["verdict"]["status"], "GO")
        self.assertEqual(result["warnings"]["source_inconsistent_version_count"], 1)
        self.assertEqual(result["warnings"]["candidate_inconsistent_version_count"], 0)
        self.assertTrue(self.candidate.is_file())
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with self.candidate.open("rb") as handle:
                candidate_payload = pickle.load(handle)
        self.assertFalse(
            any(issubclass(item.category, InconsistentVersionWarning) for item in caught)
        )
        self.assertEqual(
            candidate_payload["model"].model_to_string(),
            self.original_payload["model"].model_to_string(),
        )
        self.assertEqual(
            candidate_payload["feature_names"], self.original_payload["feature_names"]
        )
        self.assertEqual(candidate_payload["metadata"], self.original_payload["metadata"])

    def test_calibrator_grid_is_exact_and_report_contains_hashes(self) -> None:
        result = build_migration_candidate(self.source, self.candidate, self.report)

        metrics = result["equivalence"]
        self.assertEqual(metrics["calibrator_grid_points"], 1001)
        self.assertEqual(metrics["calibrator_max_abs_difference"], 0.0)
        self.assertTrue(metrics["calibrator_within_tolerance"])
        saved_report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(saved_report, result)
        self.assertEqual(saved_report["source"]["sha256"], sha256(self.source))
        self.assertEqual(saved_report["candidate"]["sha256"], sha256(self.candidate))
        self.assertEqual(saved_report["runtime_versions"]["scikit-learn"], "1.9.0")

    def test_output_is_isolated_and_source_hash_and_mtime_are_unchanged(self) -> None:
        source_before = (sha256(self.source), self.source.stat().st_mtime_ns)

        result = build_migration_candidate(self.source, self.candidate, self.report)

        self.assertNotEqual(self.source.resolve(), self.candidate.resolve())
        self.assertNotEqual(self.source.resolve(), self.report.resolve())
        self.assertEqual(source_before, (sha256(self.source), self.source.stat().st_mtime_ns))
        self.assertTrue(result["source"]["unchanged"])
        self.assertTrue(result["candidate"]["shadow_only"])
        self.assertFalse(result["verdict"]["production_model"])

    def test_rejects_overwriting_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "完全隔離"):
            build_migration_candidate(self.source, self.source, self.report)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InconsistentVersionWarning)
            with self.source.open("rb") as handle:
                payload = pickle.load(handle)
        self.assertEqual(payload["metadata"], self.original_payload["metadata"])

    def test_report_write_failure_removes_candidate_and_preserves_source(self) -> None:
        source_before = (sha256(self.source), self.source.stat().st_mtime_ns)

        with mock.patch(
            "app.modeling.model_runtime_migration._write_json_atomic",
            side_effect=OSError("synthetic report write failure"),
        ):
            with self.assertRaisesRegex(OSError, "synthetic report write failure"):
                build_migration_candidate(self.source, self.candidate, self.report)

        self.assertFalse(self.candidate.exists())
        self.assertFalse(self.report.exists())
        self.assertEqual(source_before, (sha256(self.source), self.source.stat().st_mtime_ns))


if __name__ == "__main__":
    unittest.main()
