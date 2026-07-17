from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from app.architecture.control_plane import (
    ArchitectureControlPlaneError,
    build_architecture_manifest,
    validate_control_plane_config,
    verify_architecture_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config/architecture_control_plane.yaml"
LIFECYCLE_PATH = PROJECT_ROOT / "config/script_lifecycle.yaml"


class ArchitectureControlPlaneTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.lifecycle = yaml.safe_load(LIFECYCLE_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_deterministic_and_covers_all_production_entrypoints(self) -> None:
        first = build_architecture_manifest(PROJECT_ROOT)
        second = build_architecture_manifest(PROJECT_ROOT)

        self.assertEqual(first, second)
        self.assertEqual(
            set(first["control_plane"]["entrypoints"]),
            set(self.lifecycle["production_entrypoints"]),
        )
        self.assertFalse(first["lifecycle_contract"]["automatic_full_fallback_allowed"])

    def test_missing_entrypoint_metadata_fails_loud(self) -> None:
        config = deepcopy(self.config)
        config["entrypoints"].pop("scripts/run_daily.sh")

        with self.assertRaisesRegex(ArchitectureControlPlaneError, "production entrypoint"):
            validate_control_plane_config(config, self.lifecycle, PROJECT_ROOT)

    def test_unknown_artifact_reference_fails_loud(self) -> None:
        config = deepcopy(self.config)
        config["workflows"]["daily"]["steps"][0]["outputs"].append("unknown-artifact")

        with self.assertRaisesRegex(ArchitectureControlPlaneError, "未知項目"):
            validate_control_plane_config(config, self.lifecycle, PROJECT_ROOT)

    def test_tampered_manifest_is_rejected(self) -> None:
        manifest = build_architecture_manifest(PROJECT_ROOT)
        manifest["control_plane"]["workflows"]["daily"]["production"] = False

        with self.assertRaisesRegex(ArchitectureControlPlaneError, "repo source 不一致"):
            verify_architecture_manifest(manifest, PROJECT_ROOT)

    def test_serialized_manifest_can_be_verified(self) -> None:
        manifest = build_architecture_manifest(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            verify_architecture_manifest(json.loads(path.read_text(encoding="utf-8")), PROJECT_ROOT)

    def test_unknown_source_commit_is_rejected(self) -> None:
        manifest = build_architecture_manifest(PROJECT_ROOT)
        manifest["source"]["git_sha"] = "0" * 40

        with self.assertRaisesRegex(ArchitectureControlPlaneError, "不是目前 HEAD ancestor"):
            verify_architecture_manifest(manifest, PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()
