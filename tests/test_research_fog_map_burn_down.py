from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.research import fog_map_domain, fog_map_render, map_contract


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts import build_research_fog_map as adapter
from scripts import verify_research_fog_map as verifier


CURRENT_UNIVERSE_TOTAL = 2_921_184
CLASSIFIED_SUBSET_TOTAL = 2_866_752
CLASSIFIED_PENDING = 54_432


def burn_down_counts(total: int) -> dict[str, int]:
    return {
        "executed_replay_count": total,
        "equivalence_inherited_count": 0,
        "rule_pruned_count": 0,
        "unsupported_count": 0,
        "low_information_count": 0,
        "next_stage_count": 0,
        "rejected_count": 0,
        "representative_replay_pending_count": 0,
    }


def weekend_rollup(total: int) -> dict[str, object]:
    return {
        "schema_version": "weekend-training-rollup.v1",
        "date": "2026-07-31",
        "summary": {
            "full_universe_total": total,
            "rollup_classified_total": total,
            **burn_down_counts(total),
        },
    }


class ResearchFogMapBurnDownTests(unittest.TestCase):
    def verifier_check(self, burn_down: dict[str, object]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "weekend_training_rollup_2026-07-31.json"
            source_path.write_text("{}\n", encoding="utf-8")
            payload_path = tmp_path / "research_fog_map_2026-08-01.json"
            html_path = tmp_path / "index.html"
            payload = {
                "summary": {
                    "expanded_universe_total": CURRENT_UNIVERSE_TOTAL,
                    "expanded_processed": 0,
                    "base_processed": 0,
                },
                "burn_down_progress": {**burn_down, "source": str(source_path)},
            }
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            html_path.write_text("", encoding="utf-8")
            with (
                patch.object(verifier, "SOURCE_DIR", tmp_path / "autonomous_research"),
                patch.object(verifier, "OUTPUT_DIR", tmp_path),
            ):
                report = verifier.build_payload("2026-08-01", payload_path, html_path)
        return next(check for check in report["checks"] if check["name"] == "burn_down_counts_classify_full_universe")

    def test_producer_keeps_current_universe_and_exposes_stale_rollup_delta(self) -> None:
        progress = fog_map_domain.build_burn_down_progress(
            weekend_rollup(CLASSIFIED_SUBSET_TOTAL),
            source="artifacts/weekend_training/weekend_training_rollup_2026-07-31.json",
            expanded_total=CURRENT_UNIVERSE_TOTAL,
            executed_processed=1,
        )

        self.assertEqual(progress["full_universe_total"], CURRENT_UNIVERSE_TOTAL)
        self.assertEqual(progress["source_full_universe_total"], CLASSIFIED_SUBSET_TOTAL)
        self.assertEqual(progress["classified_total"], CLASSIFIED_SUBSET_TOTAL)
        self.assertEqual(progress["classified_pending"], CLASSIFIED_PENDING)
        self.assertEqual(sum(progress["counts"].values()), progress["classified_total"])

    def test_adapter_uses_latest_historical_rollup_as_classified_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            weekend_dir = Path(tmp)
            rollup_path = weekend_dir / "weekend_training_rollup_2026-07-31.json"
            rollup_path.write_text(json.dumps(weekend_rollup(CLASSIFIED_SUBSET_TOTAL)), encoding="utf-8")
            with patch.object(adapter, "WEEKEND_DIR", weekend_dir):
                progress = adapter.build_burn_down_progress(
                    "2026-08-01",
                    CURRENT_UNIVERSE_TOTAL,
                    executed_processed=1,
                )

        self.assertIsNotNone(progress)
        self.assertEqual(progress["source_full_universe_total"], CLASSIFIED_SUBSET_TOTAL)
        self.assertEqual(progress["full_universe_total"], CURRENT_UNIVERSE_TOTAL)
        self.assertEqual(progress["classified_pending"], CLASSIFIED_PENDING)

    def test_producer_reports_full_classification_as_one_hundred_percent(self) -> None:
        progress = fog_map_domain.build_burn_down_progress(
            weekend_rollup(CURRENT_UNIVERSE_TOTAL),
            source="artifacts/weekend_training/weekend_training_rollup_2026-08-01.json",
            expanded_total=CURRENT_UNIVERSE_TOTAL,
            executed_processed=1,
        )

        self.assertEqual(progress["classified_pending"], 0)
        self.assertEqual(progress["classified_progress_pct"], 1.0)

    def test_verifier_accepts_explicit_partial_classification(self) -> None:
        check = self.verifier_check(
            {
                "schema_version": "research-map-burn-down-progress.v1",
                "source_full_universe_total": CLASSIFIED_SUBSET_TOTAL,
                "full_universe_total": CURRENT_UNIVERSE_TOTAL,
                "classified_total": CLASSIFIED_SUBSET_TOTAL,
                "classified_pending": CLASSIFIED_PENDING,
                "counts": burn_down_counts(CLASSIFIED_SUBSET_TOTAL),
            }
        )

        self.assertTrue(check["ok"], check["value"])

    def test_verifier_accepts_same_scope_full_classification(self) -> None:
        check = self.verifier_check(
            {
                "schema_version": "research-map-burn-down-progress.v1",
                "source_full_universe_total": CURRENT_UNIVERSE_TOTAL,
                "full_universe_total": CURRENT_UNIVERSE_TOTAL,
                "classified_total": CURRENT_UNIVERSE_TOTAL,
                "classified_pending": 0,
                "counts": burn_down_counts(CURRENT_UNIVERSE_TOTAL),
            }
        )

        self.assertTrue(check["ok"], check["value"])

    def test_full_verifier_accepts_generated_stale_rollup_map(self) -> None:
        topics = [
            {
                "topic_id": f"topic-{index:03d}",
                "candidate_dir": f"artifacts/backtest/topic-{index:03d}",
                "manager_status": "candidate",
                "score": 1,
            }
            for index in range(322)
        ]
        dimensions = {
            "horizon": "3",
            "stop_loss": "none",
            "take_profit": "none",
            "group_exposure": "none",
        }
        history_records = [
            {
                "topic_id": topic["topic_id"],
                "combo_id": map_contract.combo_id(topic, dimensions),
                "dimensions": dimensions,
                "status": "OK",
                "decision": "DEVELOPMENT_CANDIDATE",
                "artifact_path": f"{topic['candidate_dir']}/result.json",
                "finished_at": "2026-08-01T00:00:00+00:00",
            }
            for topic in topics[:3]
        ]
        rollup = weekend_rollup(CLASSIFIED_SUBSET_TOTAL)
        rollup["summary"].update(
            {
                "artifact_blocker_count": 0,
                "baseline_blocker_cleared": True,
            }
        )
        rollup["controlled_grid_drain"] = {
            "baseline_blocker_cleared": True,
            "target_production_path_created": False,
            "production_impact": "NO_PRODUCTION_CHANGE",
            "status": "OK",
            "controlled_grid_drain_ready": True,
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_dir = tmp_path / "autonomous_research"
            output_dir = tmp_path / "research_map"
            source_dir.mkdir()
            output_dir.mkdir()
            source_path = tmp_path / "weekend_training_rollup_2026-07-31.json"
            source_path.write_text(json.dumps(rollup), encoding="utf-8")
            payload = fog_map_domain.build_payload(
                "2026-08-01",
                progress={},
                registry={"topics": topics},
                queue={"actions": [{"topic_id": topics[0]["topic_id"]}]},
                history={},
                history_records=history_records,
                weekend_rollup=rollup,
                weekend_rollup_source=str(source_path),
                active_expansion_parent={},
                active_expansion_parent_evidence=None,
                source_paths={},
            )
            payload_path = output_dir / "research_fog_map_2026-08-01.json"
            latest_path = output_dir / "research_fog_map_latest.json"
            html_path = output_dir / "index.html"
            payload_json = json.dumps(payload, ensure_ascii=False)
            payload_path.write_text(payload_json, encoding="utf-8")
            latest_path.write_text(payload_json, encoding="utf-8")
            html_path.write_text(fog_map_render.render_html(payload), encoding="utf-8")
            (source_dir / "research_campaign_progress_2026-08-01.json").write_text(
                json.dumps({"summary": {}}),
                encoding="utf-8",
            )
            with (
                patch.object(verifier, "SOURCE_DIR", source_dir),
                patch.object(verifier, "OUTPUT_DIR", output_dir),
            ):
                report = verifier.build_payload("2026-08-01", payload_path, html_path)

        failed = [check for check in report["checks"] if not check["ok"]]
        self.assertEqual(report["status"], "OK", failed)

    def test_verifier_rejects_invalid_classification_contracts(self) -> None:
        valid = {
            "schema_version": "research-map-burn-down-progress.v1",
            "source_full_universe_total": CLASSIFIED_SUBSET_TOTAL,
            "full_universe_total": CURRENT_UNIVERSE_TOTAL,
            "classified_total": CLASSIFIED_SUBSET_TOTAL,
            "classified_pending": CLASSIFIED_PENDING,
            "counts": burn_down_counts(CLASSIFIED_SUBSET_TOTAL),
        }
        invalid_cases = {
            "over_classified": {
                **valid,
                "source_full_universe_total": CURRENT_UNIVERSE_TOTAL + 1,
                "classified_total": CURRENT_UNIVERSE_TOTAL + 1,
                "classified_pending": -1,
                "counts": burn_down_counts(CURRENT_UNIVERSE_TOTAL + 1),
            },
            "negative_pending": {**valid, "classified_pending": -1},
            "count_sum_mismatch": {**valid, "counts": burn_down_counts(CLASSIFIED_SUBSET_TOTAL - 1)},
            "pending_missing": {key: value for key, value in valid.items() if key != "classified_pending"},
            "source_scope_missing": {key: value for key, value in valid.items() if key != "source_full_universe_total"},
            "source_scope_mismatch": {**valid, "source_full_universe_total": CLASSIFIED_SUBSET_TOTAL + 1},
        }

        for name, burn_down in invalid_cases.items():
            with self.subTest(name=name):
                check = self.verifier_check(copy.deepcopy(burn_down))
                self.assertFalse(check["ok"], check["value"])


if __name__ == "__main__":
    unittest.main()
