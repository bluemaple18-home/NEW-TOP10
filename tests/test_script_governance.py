from __future__ import annotations

import unittest
from copy import deepcopy

from app.architecture.script_governance import (
    ScriptGovernanceError,
    build_script_governance,
    verify_script_governance,
)


def lifecycle() -> dict:
    return {
        "schema_version": "script-lifecycle.v1",
        "entries": [
            {"path": "scripts/run_daily.sh", "category": "production_entrypoint", "candidate_action": "retain"},
            {"path": "scripts/build_helper.py", "category": "builder", "candidate_action": "review"},
            {"path": "scripts/research_probe.py", "category": "research", "candidate_action": "review"},
        ],
    }


def references() -> dict:
    return {
        "schema_version": "script-reference-audit.v1",
        "entries": [
            {"path": "scripts/run_daily.sh", "status": "protected", "references": []},
            {
                "path": "scripts/build_helper.py",
                "status": "referenced",
                "references": [
                    {"source": "scripts/run_daily.sh", "target": "scripts/build_helper.py", "kind": "path", "line": 2}
                ],
            },
            {"path": "scripts/research_probe.py", "status": "referenced", "references": []},
        ],
        "unknown_references": [],
    }


def architecture() -> dict:
    return {
        "schema_version": "top10.architecture-manifest.v1",
        "control_plane": {
            "entrypoints": {
                "scripts/run_daily.sh": {
                    "domain": "automation",
                    "workflows": ["daily"],
                    "required_verification": ["daily_contract"],
                }
            },
            "domains": {"automation": {"owner": "app.automation"}},
            "workflows": {"daily": {"required_verification": ["daily_contract"]}},
            "artifacts": {
                "ranking": {"producers": ["daily.rank"], "consumers": ["daily"]}
            },
            "verification": {
                "daily_contract": {"paths": ["tests/test_daily.py"]}
            },
        },
    }


class ScriptGovernanceTest(unittest.TestCase):
    def test_transitive_production_helper_inherits_owner_and_contracts(self) -> None:
        report = build_script_governance(lifecycle(), references(), architecture())
        entries = {item["path"]: item for item in report["entries"]}
        helper = entries["scripts/build_helper.py"]

        self.assertTrue(report["strict"]["passed"])
        self.assertTrue(helper["production_reachability"]["reachable"])
        self.assertEqual(helper["owner_contract"]["owners"], ["app.automation"])
        self.assertEqual(helper["artifact_contract"]["artifacts"], ["ranking"])
        self.assertEqual(helper["verification_contract"]["ids"], ["daily_contract"])
        self.assertEqual(helper["candidate_action"], "retain")

    def test_nonproduction_script_has_explicit_lifecycle_contract(self) -> None:
        report = build_script_governance(lifecycle(), references(), architecture())
        entry = next(item for item in report["entries"] if item["path"] == "scripts/research_probe.py")

        self.assertFalse(entry["production_reachability"]["reachable"])
        self.assertEqual(entry["owner_contract"]["owners"], ["research"])
        self.assertEqual(entry["artifact_contract"]["status"], "not_applicable_until_production_promotion")

    def test_production_missing_artifact_contract_fails_closed(self) -> None:
        manifest = architecture()
        manifest["control_plane"]["artifacts"] = {}
        report = build_script_governance(lifecycle(), references(), manifest)
        self.assertFalse(report["strict"]["passed"])
        self.assertTrue(report["summary"]["production_contract_gaps"])

    def test_tampered_report_is_rejected(self) -> None:
        report = build_script_governance(lifecycle(), references(), architecture())
        tampered = deepcopy(report)
        tampered["strict"]["passed"] = False
        with self.assertRaisesRegex(ScriptGovernanceError, "重算結果不一致"):
            verify_script_governance(tampered, lifecycle(), references(), architecture())


if __name__ == "__main__":
    unittest.main()
