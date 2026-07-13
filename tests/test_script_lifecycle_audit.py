from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import audit_script_lifecycle as audit


def write_policy(path: Path, **overrides: object) -> Path:
    payload = {
        "schema_version": "script-lifecycle-policy.v1",
        "production_entrypoints": ["scripts/run_daily.py"],
        "prefix_categories": [
            {"category": "research", "prefixes": ["research_"]},
            {"category": "builder", "prefixes": ["build_"]},
            {"category": "verifier", "prefixes": ["verify_"]},
            {"category": "maintenance", "prefixes": ["run_"]},
        ],
        "overrides": {
            "scripts/run_daily_v2.py": {
                "category": "research",
                "reason": "shadow-only fixture lane",
            },
            "scripts/legacy_probe.py": {
                "category": "legacy_candidate",
                "reason": "fixture legacy script",
            }
        },
        "approved_unclassified": ["scripts/existing_unknown.py"],
    }
    payload.update(overrides)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


class ScriptLifecycleAuditTest(unittest.TestCase):
    def test_exact_production_prefixes_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = audit.load_policy(write_policy(Path(tmp) / "policy.yaml"))
        entries = {
            item["path"]: item
            for item in audit.build_inventory(
                policy,
                [
                    "scripts/run_daily.py",
                    "scripts/run_daily_v2.py",
                    "scripts/research_signal.py",
                    "scripts/build_report.py",
                    "scripts/verify_report.py",
                    "scripts/legacy_probe.py",
                ],
            )["entries"]
        }
        self.assertEqual(entries["scripts/run_daily.py"]["category"], "production_entrypoint")
        self.assertTrue(entries["scripts/run_daily.py"]["entrypoint"])
        self.assertEqual(entries["scripts/run_daily_v2.py"]["category"], "research")
        self.assertFalse(entries["scripts/run_daily_v2.py"]["entrypoint"])
        self.assertEqual(entries["scripts/research_signal.py"]["category"], "research")
        self.assertEqual(entries["scripts/build_report.py"]["category"], "builder")
        self.assertEqual(entries["scripts/verify_report.py"]["category"], "verifier")
        self.assertEqual(entries["scripts/legacy_probe.py"]["category"], "legacy_candidate")
        self.assertEqual(entries["scripts/legacy_probe.py"]["candidate_action"], "review")

    def test_strict_new_only_blocks_unknowns_not_approved_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = audit.load_policy(write_policy(Path(tmp) / "policy.yaml"))
        inventory = audit.build_inventory(
            policy,
            ["scripts/existing_unknown.py", "scripts/new_unknown.py"],
        )
        self.assertEqual(inventory["strict_new"]["new_unclassified"], ["scripts/new_unknown.py"])
        self.assertFalse(inventory["strict_new"]["passed"])
        unknown = next(item for item in inventory["entries"] if item["path"] == "scripts/new_unknown.py")
        self.assertEqual(unknown["candidate_action"], "review")

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = audit.load_policy(write_policy(Path(tmp) / "policy.yaml"))
        with self.assertRaisesRegex(ValueError, "escapes scripts"):
            audit.build_inventory(policy, ["scripts/../outside.py"])

    def test_inventory_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = audit.load_policy(write_policy(Path(tmp) / "policy.yaml"))
        paths = ["scripts/verify_report.py", "scripts/run_daily.py", "scripts/existing_unknown.py"]
        self.assertEqual(audit.build_inventory(policy, paths), audit.build_inventory(policy, reversed(paths)))


if __name__ == "__main__":
    unittest.main()
