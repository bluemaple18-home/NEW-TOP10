from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import audit_script_references as audit


def write_policy(path: Path, **overrides: object) -> Path:
    payload = {
        "schema_version": "script-lifecycle-policy.v1",
        "production_entrypoints": ["scripts/run_daily.py"],
        "reference_audit": {"approved_unreferenced": ["scripts/existing_baseline.py"]},
    }
    payload.update(overrides)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


class ScriptReferenceAuditTest(unittest.TestCase):
    def load_fixture_policy(self) -> audit.ReferencePolicy:
        with tempfile.TemporaryDirectory() as tmp:
            return audit.load_policy(write_policy(Path(tmp) / "policy.yaml"))

    def test_python_import_shell_plist_and_docs_references(self) -> None:
        scripts = [
            "scripts/run_daily.py",
            "scripts/worker.py",
            "scripts/shell_target.sh",
            "scripts/service.py",
            "scripts/doc_target.py",
        ]
        texts = {
            "app.py": "from scripts import worker\nimport scripts.service\n",
            "scripts/run_wrapper.sh": "uv run python scripts/shell_target.sh\n",
            "scripts/com.example.plist": "<string>scripts/service.py</string>\n",
            "README.md": "See `scripts/doc_target.py`.\n",
        }
        references, unknown = audit.collect_references(texts, scripts)
        inventory = audit.build_inventory(self.load_fixture_policy(), scripts, references, unknown)
        entries = {entry["path"]: entry for entry in inventory["entries"]}
        self.assertEqual(entries["scripts/worker.py"]["reference_count"], 1)
        self.assertEqual(entries["scripts/shell_target.sh"]["reference_count"], 1)
        self.assertEqual(entries["scripts/service.py"]["reference_count"], 2)
        self.assertEqual(entries["scripts/doc_target.py"]["reference_count"], 1)

    def test_dynamic_import_is_unknown_and_literal_target_is_resolved(self) -> None:
        scripts = ["scripts/loader.py", "scripts/worker.py"]
        references, unknown = audit.collect_references(
            {
                "scripts/loader.py": (
                    "import importlib\n"
                    "importlib.import_module('scripts.worker')\n"
                    "importlib.import_module(module_name)\n"
                )
            },
            scripts,
        )
        inventory = audit.build_inventory(self.load_fixture_policy(), scripts, references, unknown)
        worker = next(entry for entry in inventory["entries"] if entry["path"] == "scripts/worker.py")
        self.assertEqual(worker["reference_count"], 1)
        self.assertEqual(inventory["summary"]["unknown_reference_count"], 1)
        self.assertEqual(inventory["unknown_references"][0]["source"], "scripts/loader.py")

    def test_protected_scripts_and_allowlisted_baseline(self) -> None:
        scripts = ["scripts/run_daily.py", "scripts/existing_baseline.py", "scripts/new_script.py"]
        inventory = audit.build_inventory(self.load_fixture_policy(), scripts, [], [])
        entries = {entry["path"]: entry for entry in inventory["entries"]}
        self.assertEqual(entries["scripts/run_daily.py"]["status"], "protected")
        self.assertEqual(entries["scripts/existing_baseline.py"]["status"], "suspected_orphan")
        self.assertTrue(entries["scripts/existing_baseline.py"]["baseline_approved"])
        self.assertEqual(entries["scripts/new_script.py"]["status"], "suspected_orphan")
        self.assertEqual(inventory["strict_new"]["new_suspected_orphans"], ["scripts/new_script.py"])

    def test_allowlist_text_does_not_count_as_reference_evidence(self) -> None:
        scripts = ["scripts/existing_baseline.py"]
        references, unknown = audit.collect_references(
            {"config/script_lifecycle.yaml": "  - scripts/existing_baseline.py\n"},
            scripts,
            {"config/script_lifecycle.yaml": frozenset(scripts)},
        )
        inventory = audit.build_inventory(self.load_fixture_policy(), scripts, references, unknown)
        entry = inventory["entries"][0]
        self.assertEqual(entry["reference_count"], 0)
        self.assertEqual(entry["status"], "suspected_orphan")

    def test_inventory_is_deterministic_and_self_reference_is_excluded(self) -> None:
        scripts = ["scripts/alpha.py", "scripts/beta.py"]
        texts = {"scripts/alpha.py": "# scripts/alpha.py\n", "README.md": "scripts/beta.py\n"}
        references, unknown = audit.collect_references(texts, scripts)
        policy = self.load_fixture_policy()
        self.assertEqual(
            audit.build_inventory(policy, scripts, references, unknown),
            audit.build_inventory(policy, reversed(scripts), reversed(references), reversed(unknown)),
        )
        alpha = next(entry for entry in audit.build_inventory(policy, scripts, references, unknown)["entries"] if entry["path"] == "scripts/alpha.py")
        self.assertEqual(alpha["reference_count"], 0)

    def test_generated_audit_evidence_is_not_scanned_as_reference_source(self) -> None:
        scripts = ["scripts/existing_baseline.py"]
        evidence_payloads = {
            ".work/CLEANUP-15/evidence/script-reference-audit.json": {
                "schema_version": "script-reference-audit.v1",
                "entries": [{"path": scripts[0]}],
            },
            ".work/CLEANUP-15/evidence/script-lifecycle.json": {
                "schema_version": "script-lifecycle.v1",
                "entries": [{"path": scripts[0]}],
            },
        }

        for path, payload in evidence_payloads.items():
            with self.subTest(path=path):
                self.assertTrue(
                    audit.is_generated_audit_evidence(
                        path,
                        json.dumps(payload, ensure_ascii=False),
                    )
                )

        self.assertFalse(
            audit.is_generated_audit_evidence(
                ".work/OTHER/evidence/result.json",
                json.dumps({"schema_version": "other.v1", "path": scripts[0]}),
            )
        )


if __name__ == "__main__":
    unittest.main()
