from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.verify_daily_research_quota import build_payload, canonical_json_hash


class DailyResearchQuotaVerifierTest(unittest.TestCase):
    def build_artifact(self, topic_count: int, quota: int = 5) -> tuple[Path, Path]:
        run_date = "2099-01-05"
        directory = Path(tempfile.mkdtemp())
        artifact = directory / "quota.json"
        history = directory / "history.json"
        contract_path = directory / "contract.json"
        runtime_receipt = directory / "runtime.json"
        history.write_text('{"schema_version":"market-regime-history.v2"}\n', encoding="utf-8")
        contract_path.write_text('{"contract":"fixture"}\n', encoding="utf-8")
        runtime_receipt.write_text(
            json.dumps(
                {
                    "schema_version": "closed-regime-runtime-receipt.v2",
                    "status": "READY",
                    "closed_regime_research": True,
                    "market_regime_history": {
                        "path": str(history),
                        "sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
                    },
                    "research_contract": {
                        "path": str(contract_path),
                        "sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                    },
                    "exact_regime": {"identity_id": "RISK_OFF|"},
                    "production_impact": "NO_PRODUCTION_CHANGE",
                }
            ),
            encoding="utf-8",
        )
        topic_runs = [
            {
                "topic": {"topic_id": f"topic-{index}"},
                "status": "OK",
                "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX", "promotion_allowed": False},
                "steps": [],
            }
            for index in range(topic_count)
        ]
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "autonomous-research-run.v1",
                    "date": run_date,
                    "status": "OK",
                    "contract": {
                        "research_only": True,
                        "does_not_train_model": True,
                        "does_not_write_models_latest_lgbm": True,
                        "does_not_change_risk_adjusted_score": True,
                        "does_not_change_production_ranking": True,
                        "production_promotion_allowed": False,
                        "closed_regime_research": True,
                    },
                    "inputs": {
                        "execute": True,
                        "from_queue": True,
                        "execute_topic_count": quota,
                        "closed_regime_research": True,
                        "market_regime_history": str(history),
                        "research_contract": str(contract_path),
                    },
                    "selected_topics": [run["topic"] for run in topic_runs],
                    "topic_runs": topic_runs,
                    "outcome": {"decision": "NO_EXECUTABLE_TOPIC" if not topic_runs else "REJECTED_BY_STRATEGY_MATRIX"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        topic_lineage = [
            {
                "topic_id": str(run["topic"]["topic_id"]),
                "status": str(run["status"]),
                "decision": run["outcome"]["decision"],
            }
            for run in topic_runs
        ]
        runtime_receipt.write_text(
            json.dumps(
                {
                    "schema_version": "closed-regime-runtime-receipt.v2",
                    "status": "OK",
                    "generated_at": "2099-01-05T00:00:00+00:00",
                    "run_date": run_date,
                    "closed_regime_research": True,
                    "queue_owner": "fog_worker",
                    "runner_identity": "scripts/run_daily_research_quota.sh",
                    "market_regime_history": {
                        "path": str(history),
                        "schema_version": "market-regime-history.v2",
                        "sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
                        "source_trade_date": run_date,
                    },
                    "research_contract": {
                        "path": str(contract_path),
                        "sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                    },
                    "exact_regime": {
                        "base_regime": "RISK_OFF",
                        "family_tags": [],
                        "identity_id": "RISK_OFF|",
                    },
                    "state_transition": {
                        "from": "VERIFIED_HISTORY",
                        "to": "CLOSED_RESEARCH_COMPLETED",
                    },
                    "daily_research_artifact": {
                        "path": str(artifact),
                        "schema_version": "autonomous-research-run.v1",
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        "run_date": run_date,
                    },
                    "topic_runs": topic_lineage,
                    "topic_runs_sha256": canonical_json_hash(topic_lineage),
                    "production_impact": "NO_PRODUCTION_CHANGE",
                }
            ),
            encoding="utf-8",
        )
        self.addCleanup(shutil.rmtree, directory)
        return artifact, runtime_receipt

    def test_zero_topics_is_partial_no_more_work(self) -> None:
        artifact, runtime = self.build_artifact(0)
        payload = build_payload(artifact, min_quota=5, runtime_receipt_path=runtime)

        self.assertEqual(payload["status"], "PARTIAL_NO_MORE_WORK")
        self.assertEqual(payload["summary"]["research_value_status"], "QUEUE_EMPTY")

    def test_one_topic_is_partial_no_more_work(self) -> None:
        artifact, runtime = self.build_artifact(1)
        self.assertEqual(build_payload(artifact, 5, runtime)["status"], "PARTIAL_NO_MORE_WORK")

    def test_three_topics_is_partial_no_more_work(self) -> None:
        artifact, runtime = self.build_artifact(3)
        self.assertEqual(build_payload(artifact, 5, runtime)["status"], "PARTIAL_NO_MORE_WORK")

    def test_five_topics_completes_batch(self) -> None:
        artifact, runtime = self.build_artifact(5)
        self.assertEqual(build_payload(artifact, 5, runtime)["status"], "COMPLETED")

    def test_topic_failure_is_failed(self) -> None:
        artifact, runtime = self.build_artifact(1)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload["status"] = "FAILED"
        payload["topic_runs"][0]["status"] = "FAILED"
        artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(build_payload(artifact, 5, runtime)["status"], "FAILED")

    def test_quota_above_cap_is_blocked(self) -> None:
        artifact, runtime = self.build_artifact(5, quota=6)
        self.assertEqual(build_payload(artifact, 5, runtime)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
