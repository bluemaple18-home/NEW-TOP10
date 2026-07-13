from __future__ import annotations

import copy
import hashlib
import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app.modeling.model_runtime_promotion as promotion_module
from app.modeling.model_runtime_migration import SCHEMA_VERSION as MIGRATION_SCHEMA_VERSION
from app.modeling.model_runtime_promotion import (
    EQUIVALENCE_FLAGS,
    PromotionError,
    promote_model_runtime_candidate,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ModelRuntimePromotionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="top10-model-promotion-")
        self.root = Path(self.tempdir.name)
        self.production = self.root / "models" / "latest_lgbm.pkl"
        self.candidate = (
            self.root
            / "artifacts"
            / "shadow"
            / "model_runtime_migration"
            / "latest_lgbm.pkl"
        )
        self.verdict = self.candidate.parent / "verdict.json"
        self.backup = (
            self.root
            / "models"
            / "backup"
            / "latest_lgbm.pre-runtime-migration.pkl"
        )
        self.report = (
            self.root / "artifacts" / "model_runtime_promotion" / "promotion.json"
        )
        self.production.parent.mkdir(parents=True)
        self.candidate.parent.mkdir(parents=True)
        self.production.write_bytes(
            pickle.dumps({"runtime": "source", "features": ["factor_a"]})
        )
        self.candidate.write_bytes(
            pickle.dumps({"runtime": "candidate", "features": ["factor_a"]})
        )
        self.source_bytes = self.production.read_bytes()
        self.candidate_bytes = self.candidate.read_bytes()
        self.valid_verdict = {
            "schema_version": MIGRATION_SCHEMA_VERSION,
            "source": {
                "sha256": sha256(self.production),
                "unchanged": True,
            },
            "candidate": {
                "sha256": sha256(self.candidate),
                "created": True,
                "shadow_only": True,
            },
            "warnings": {
                "candidate_reload": [],
                "candidate_inconsistent_version_count": 0,
            },
            "equivalence": {
                **{name: True for name in EQUIVALENCE_FLAGS},
                "calibrator_grid_points": 1001,
                "calibrator_max_abs_difference": 0.0,
                "calibrator_tolerance": 1e-12,
            },
            "verdict": {"status": "GO", "failures": []},
        }
        self._write_verdict(self.valid_verdict)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_verdict(self, payload: dict[str, object]) -> None:
        self.verdict.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _promote(self, **overrides: Path) -> dict[str, object]:
        return promote_model_runtime_candidate(
            self.root,
            overrides.get("candidate", self.candidate),
            overrides.get("verdict", self.verdict),
            overrides.get("backup", self.backup),
            overrides.get("report", self.report),
        )

    def _assert_production_unchanged(self) -> None:
        self.assertEqual(self.production.read_bytes(), self.source_bytes)

    def test_normal_promotion_creates_backup_and_go_report(self) -> None:
        result = self._promote()

        self.assertEqual(result["status"], "GO")
        self.assertTrue(result["executed"])
        self.assertEqual(self.production.read_bytes(), self.candidate_bytes)
        self.assertEqual(self.backup.read_bytes(), self.source_bytes)
        self.assertEqual(result["before"]["sha256"], sha256(self.backup))
        self.assertEqual(result["after"]["sha256"], sha256(self.candidate))
        self.assertTrue(result["after"]["loadable"])
        self.assertEqual(result["after"]["inconsistent_version_warning_count"], 0)
        self.assertIsNone(result["rollback"])
        self.assertEqual(
            json.loads(self.report.read_text(encoding="utf-8")),
            result,
        )

    def test_stale_source_fails_loud_without_changing_production(self) -> None:
        payload = copy.deepcopy(self.valid_verdict)
        payload["source"]["sha256"] = "0" * 64
        self._write_verdict(payload)

        with self.assertRaises(PromotionError) as caught:
            self._promote()

        self.assertEqual(caught.exception.status, "NO-GO")
        self._assert_production_unchanged()
        self.assertFalse(self.backup.exists())
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertFalse(report["executed"])
        self.assertIn("source_sha256_stale", report["errors"])

    def test_source_changed_after_backup_is_not_overwritten_by_candidate(self) -> None:
        concurrent_bytes = pickle.dumps(
            {"runtime": "concurrent-update", "features": ["factor_a"]}
        )
        copy_exclusive = promotion_module._copy_exclusive

        def copy_then_change_production(source: Path, destination: Path) -> None:
            copy_exclusive(source, destination)
            self.production.write_bytes(concurrent_bytes)

        with mock.patch.object(
            promotion_module,
            "_copy_exclusive",
            side_effect=copy_then_change_production,
        ):
            with self.assertRaises(PromotionError) as caught:
                self._promote()

        self.assertEqual(caught.exception.status, "NO-GO")
        self.assertEqual(self.production.read_bytes(), concurrent_bytes)
        self.assertNotEqual(self.production.read_bytes(), self.candidate_bytes)
        self.assertEqual(self.backup.read_bytes(), self.source_bytes)
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "NO-GO")
        self.assertFalse(report["executed"])
        self.assertEqual(
            report["errors"],
            ["source_sha256_changed_before_replace"],
        )

    def test_bad_candidate_hash_fails_without_changing_production(self) -> None:
        payload = copy.deepcopy(self.valid_verdict)
        payload["candidate"]["sha256"] = "f" * 64
        self._write_verdict(payload)

        with self.assertRaises(PromotionError):
            self._promote()

        self._assert_production_unchanged()
        self.assertFalse(self.backup.exists())
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertIn("candidate_sha256_mismatch", report["errors"])

    def test_non_go_verdict_fails_without_changing_production(self) -> None:
        payload = copy.deepcopy(self.valid_verdict)
        payload["verdict"] = {"status": "NO-GO", "failures": ["synthetic"]}
        self._write_verdict(payload)

        with self.assertRaises(PromotionError):
            self._promote()

        self._assert_production_unchanged()
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertIn("verdict_not_go", report["errors"])
        self.assertIn("verdict_failures_not_empty", report["errors"])

    def test_warning_gate_fails_without_changing_production(self) -> None:
        payload = copy.deepcopy(self.valid_verdict)
        payload["warnings"] = {
            "candidate_reload": [{"category": "InconsistentVersionWarning"}],
            "candidate_inconsistent_version_count": 1,
        }
        self._write_verdict(payload)

        with self.assertRaises(PromotionError):
            self._promote()

        self._assert_production_unchanged()
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertIn(
            "candidate_inconsistent_version_warning_present",
            report["errors"],
        )
        self.assertIn("candidate_reload_warning_present", report["errors"])

    def test_equivalence_and_tolerance_gates_fail_before_backup(self) -> None:
        cases = {
            "equivalence": ("metadata_equal", False),
            "tolerance": ("calibrator_tolerance", 1e-6),
        }
        for name, (key, value) in cases.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(self.valid_verdict)
                payload["equivalence"][key] = value
                self._write_verdict(payload)

                with self.assertRaises(PromotionError):
                    self._promote()

                self._assert_production_unchanged()
                self.assertFalse(self.backup.exists())
                report = json.loads(self.report.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "NO-GO")
                self.report.unlink()

    def test_post_replace_validation_failure_rolls_back_source_sha(self) -> None:
        with mock.patch(
            "app.modeling.model_runtime_promotion._verify_promoted_model",
            side_effect=ValueError("synthetic post-replace failure"),
        ):
            with self.assertRaises(PromotionError) as caught:
                self._promote()

        self.assertEqual(caught.exception.status, "ROLLED_BACK")
        self._assert_production_unchanged()
        self.assertEqual(self.backup.read_bytes(), self.source_bytes)
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "ROLLED_BACK")
        self.assertTrue(report["executed"])
        self.assertEqual(report["after"]["sha256"], sha256(self.candidate))
        self.assertEqual(report["rollback"]["sha256"], sha256(self.production))

    def test_output_path_escape_is_rejected(self) -> None:
        escaped_backup = self.root.parent / f"{self.root.name}-backup.pkl"
        escaped_report = self.root.parent / f"{self.root.name}-report.json"
        for name, overrides in (
            ("backup", {"backup": escaped_backup}),
            ("report", {"report": escaped_report}),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "路徑逃逸"):
                    self._promote(**overrides)
                self._assert_production_unchanged()

    def test_existing_backup_or_report_is_never_overwritten(self) -> None:
        self.backup.parent.mkdir(parents=True)
        self.backup.write_bytes(b"existing backup")
        with self.assertRaises(FileExistsError):
            self._promote()
        self.assertEqual(self.backup.read_bytes(), b"existing backup")
        self._assert_production_unchanged()

        self.backup.unlink()
        self.report.parent.mkdir(parents=True)
        self.report.write_bytes(b"existing report")
        with self.assertRaises(FileExistsError):
            self._promote()
        self.assertEqual(self.report.read_bytes(), b"existing report")
        self._assert_production_unchanged()


if __name__ == "__main__":
    unittest.main()
