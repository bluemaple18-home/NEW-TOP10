from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.research import map_contract as canonical
from scripts import research_map_contract as legacy


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ResearchMapContractBoundaryTests(unittest.TestCase):
    def test_legacy_module_reexports_the_canonical_public_api(self) -> None:
        self.assertEqual(legacy.__all__, canonical.__all__)
        for name in canonical.__all__:
            self.assertIs(getattr(legacy, name), getattr(canonical, name), name)

    def test_combo_ids_and_schema_payload_are_equivalent(self) -> None:
        topics = [
            {"topic_id": "research:alpha", "candidate_dir": "artifacts/research/alpha"},
            {"topic_id": "beta", "candidate_dir": "artifacts/research/beta"},
        ]
        canonical_registry = canonical.build_combo_registry(topics)
        legacy_registry = legacy.build_combo_registry(topics)

        self.assertEqual(legacy_registry, canonical_registry)
        self.assertEqual(
            [row["combo_id"] for row in legacy_registry],
            [row["combo_id"] for row in canonical_registry],
        )
        self.assertEqual(legacy.dimension_schema_payload(), canonical.dimension_schema_payload())

        dimensions = {
            **canonical_registry[0]["dimensions"],
            "regime_gate": "BIG_BULL_ONLY",
            "risk_guard": "RISK_OFF_CASH_RAISE",
            "entry_filter": "LOG_GATE",
        }
        self.assertEqual(
            legacy.v2_combo_id(topics[0], dimensions),
            canonical.v2_combo_id(topics[0], dimensions),
        )

    def test_jsonl_round_trip_is_cross_compatible(self) -> None:
        rows = [
            {
                "combo_id": "alpha|horizon_3",
                "status": "completed",
                "source": "fixture",
                "finished_at": "2099-01-01T00:00:00+00:00",
            },
            {
                "combo_id": "beta|horizon_5",
                "status": "pending",
                "source": "research_map_linkage_smoke",
                "finished_at": "2099-01-02T00:00:00+00:00",
            },
        ]
        replacement = [
            {
                "combo_id": "gamma|horizon_10",
                "status": "completed",
                "source": "research_map_linkage_smoke",
                "finished_at": "2099-01-03T00:00:00+00:00",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_history.jsonl"
            canonical.write_jsonl(path, rows)
            self.assertEqual(legacy.read_jsonl(path), rows)

            legacy.write_jsonl(path, replacement, replace_smoke=True)
            self.assertEqual(canonical.read_jsonl(path), [rows[0], replacement[0]])

    def test_development_lifecycle_is_folded_into_parent_topic_and_history(self) -> None:
        parent_id = "strategy-matrix:artifacts-backtest-shadow"
        lifecycle_id = f"{parent_id}:development_screen"
        topics = [
            {
                "topic_id": parent_id,
                "candidate_dir": "artifacts/backtest/shadow",
                "manager_status": "candidate",
            },
            {
                "topic_id": lifecycle_id,
                "candidate_dir": "artifacts/backtest/shadow",
                "manager_status": "development_screen_passed",
                "selection_rationale": {"parent_topic_id": parent_id},
            },
        ]
        dimensions = {
            "horizon": "3",
            "stop_loss": "none",
            "take_profit": "none",
            "group_exposure": "none",
        }
        history = [
            {
                "topic_id": lifecycle_id,
                "combo_id": canonical.combo_id(topics[1], dimensions),
                "dimensions": dimensions,
                "status": "OK",
            }
        ]

        canonical_topics = canonical.canonicalize_lifecycle_topics(topics)
        canonical_history = canonical.canonicalize_lifecycle_history(history)

        self.assertEqual(len(canonical_topics), 1)
        self.assertEqual(canonical_topics[0]["topic_id"], parent_id)
        self.assertEqual(canonical_topics[0]["lifecycle_topic_id"], lifecycle_id)
        self.assertEqual(canonical_topics[0]["manager_status"], "development_screen_passed")
        self.assertEqual(canonical_history[0]["topic_id"], parent_id)
        self.assertEqual(canonical_history[0]["lifecycle_topic_id"], lifecycle_id)
        self.assertEqual(
            canonical_history[0]["combo_id"],
            canonical.combo_id(canonical_topics[0], dimensions),
        )

    def test_top_level_legacy_import_works_in_subprocess(self) -> None:
        code = """
import json
from research_map_contract import dimension_schema_payload, expanded_universe_total
print(json.dumps({
    "schema": dimension_schema_payload()["version"],
    "total": expanded_universe_total(1),
}, sort_keys=True))
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT / "scripts",
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "schema": canonical.V2_DIMENSION_SCHEMA_VERSION,
                "total": canonical.expanded_universe_total(1),
            },
        )

    def test_app_and_modern_adapter_do_not_import_legacy_contract(self) -> None:
        forbidden = "scripts.research_map_contract"
        offenders = [
            str(path.relative_to(PROJECT_ROOT))
            for path in (PROJECT_ROOT / "app").rglob("*.py")
            if forbidden in path.read_text(encoding="utf-8")
        ]
        adapter_source = (PROJECT_ROOT / "scripts" / "build_research_fog_map.py").read_text(encoding="utf-8")

        self.assertEqual(offenders, [])
        self.assertIn("from app.research.map_contract import", adapter_source)
        self.assertNotIn(forbidden, adapter_source)


if __name__ == "__main__":
    unittest.main()
