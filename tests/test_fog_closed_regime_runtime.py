from __future__ import annotations

import copy
import hashlib
import importlib
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = PROJECT_ROOT / "docs/architecture/fog_runtime_receipt_v3.schema.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@contextmanager
def _runtime_fixture() -> Iterator[tuple[Path, dict[str, object]]]:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        schema_path = root / "docs/architecture/fog_runtime_receipt_v3.schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_bytes(SCHEMA_SOURCE.read_bytes())
        policy = {
            "schema_version": "fog-runtime-time-authority.v1",
            "market_id": "TWSE",
            "market_timezone": "Asia/Taipei",
            "market_day_semantics": "local-civil-date",
            "timestamp_format": "rfc3339-utc-z",
            "receipt_schema_version": "closed-regime-runtime-receipt.v3",
            "freshness": {"max_age_seconds": 900, "future_tolerance_seconds": 5},
            "lifecycle": {"market_midnight_boundary": "hard"},
        }
        _write_json(root / "config/fog_runtime_time_authority_v1.json", policy)
        paths = {
            "history": "artifacts/market_regime_history.json",
            "daily": (
                "artifacts/autonomous_research/"
                "autonomous_research_daily_quota_2026-08-08.json"
            ),
            "contract": "config/regime_research_contract.json",
        }
        _write_json(
            root / paths["history"],
            {
                "schema_version": "market-regime-history.v2",
                "rows": [
                    {
                        "trade_date": "2026-08-07",
                        "as_of_date": "2026-08-07",
                        "base_regime": "RISK_OFF",
                        "family_tags": ["HIGH_VOLATILITY"],
                    }
                ],
            },
        )
        features_path = root / "data/clean/features.parquet"
        features_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-08-07"]),
                "stock_id": ["0001"],
            }
        ).to_parquet(features_path)
        _write_json(
            root / paths["daily"],
            {
                "schema_version": "autonomous-research-run.v1",
                "status": "OK",
                "run_date": "2026-08-08",
                "source_date": "2026-08-07",
                "source_lineage": {
                    "schema_version": "fog-daily-source-lineage.v1",
                    "features_path": "data/clean/features.parquet",
                    "features_sha256": _sha256(features_path),
                    "daily_source_date": "2026-08-07",
                },
                "topic_runs": [
                    {
                        "topic": {"topic_id": "topic-001"},
                        "status": "OK",
                        "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX"},
                    }
                ],
            },
        )
        _write_json(
            root / paths["contract"],
            {"schema_version": "regime-research-contract.v1"},
        )
        yield root, paths


class FogRuntimeAuthorityRegressionTest(unittest.TestCase):
    def test_processed_authority_rejects_caller_selected_distinct_sources(
        self,
    ) -> None:
        """Caller 自選兩份互異 source 仍不得取得 processed authority。"""
        authority = importlib.import_module("scripts.verify_processed_id_authority")
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            _write_json(root / "attacker/map-source.json", {"source": "map"})
            _write_json(
                root / "attacker/inventory-source.json",
                {"source": "inventory"},
            )
            rows = [{"topic_id": "processed-a", "status": "COMPLETED"}]
            _write_json(
                root / "map.json",
                {
                    "processed": rows,
                    "source_hashes": {
                        "map": {
                            "path": "attacker/map-source.json",
                            "sha256": _sha256(root / "attacker/map-source.json"),
                        }
                    },
                },
            )
            _write_json(
                root / "inventory.json",
                {
                    "processed": rows,
                    "source_hashes": {
                        "inventory": {
                            "path": "attacker/inventory-source.json",
                            "sha256": _sha256(
                                root / "attacker/inventory-source.json"
                            ),
                        }
                    },
                },
            )

            result = authority.verify_processed_artifacts(
                root=root,
                research_map_path="map.json",
                inventory_path="inventory.json",
                research_map_source_roles={"map": "attacker/map-source.json"},
                inventory_source_roles={
                    "inventory": "attacker/inventory-source.json"
                },
            )

        self.assertFalse(result["ok"])
        self.assertIn("DATA_AUTHORITY_ARGUMENT_DRIFT", result["reason_codes"])

    def test_frta_reg_rrv_p1_01_processed_id(self) -> None:
        """FRTA-REG-RRV-P1-01-PROCESSED-ID：偽造與同源集合必須拒絕。"""
        authority = importlib.import_module("scripts.verify_processed_id_authority")
        contracts = importlib.import_module("scripts.fog_authority_contracts")
        configured = contracts.load_data_authority()["processed_id_authority"]
        map_authority = configured["research_map"]
        inventory_authority = configured["inventory"]
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            map_source = next(iter(map_authority["source_roles"].values()))
            inventory_source = next(iter(inventory_authority["source_roles"].values()))
            _write_json(root / map_source, {"ids": ["processed-a", "processed-b"]})
            _write_json(
                root / inventory_source,
                {"ids": ["processed-a", "processed-b"]},
            )
            map_role = next(iter(map_authority["source_roles"]))
            inventory_role = next(iter(inventory_authority["source_roles"]))
            map_payload = {
                "schema_version": "research-map-processed.v1",
                "processed": [
                    {"topic_id": "processed-a", "status": "COMPLETED"},
                    {"topic_id": "processed-b", "status": "COMPLETED"},
                ],
                "source_hashes": {
                    map_role: {
                        "path": map_source,
                        "sha256": _sha256(root / map_source),
                    }
                },
            }
            inventory_payload = {
                "schema_version": "weekend-inventory-processed.v1",
                "processed": [
                    {"topic_id": "processed-a", "status": "COMPLETED"},
                    {"topic_id": "forged-id", "status": "COMPLETED"},
                ],
                "source_hashes": {
                    inventory_role: {
                        "path": inventory_source,
                        "sha256": _sha256(root / inventory_source),
                    }
                },
            }
            _write_json(root / map_authority["artifact_path"], map_payload)
            _write_json(root / inventory_authority["artifact_path"], inventory_payload)

            result = authority.verify_processed_artifacts(
                root=root,
                research_map_path=map_authority["artifact_path"],
                inventory_path=inventory_authority["artifact_path"],
                research_map_source_roles=map_authority["source_roles"],
                inventory_source_roles=inventory_authority["source_roles"],
            )
            map_payload["source_hashes"][map_role]["sha256"] = "0" * 64
            _write_json(root / map_authority["artifact_path"], map_payload)
            hash_drift = authority.verify_processed_artifacts(
                root=root,
                research_map_path=map_authority["artifact_path"],
                inventory_path=inventory_authority["artifact_path"],
                research_map_source_roles=map_authority["source_roles"],
                inventory_source_roles=inventory_authority["source_roles"],
            )
            map_payload["source_hashes"][map_role]["sha256"] = _sha256(
                root / map_source
            )
            map_payload["processed"] = inventory_payload["processed"]
            inventory_payload["source_hashes"] = {
                inventory_role: {
                    "path": map_source,
                    "sha256": _sha256(root / map_source),
                }
            }
            _write_json(root / map_authority["artifact_path"], map_payload)
            _write_json(root / inventory_authority["artifact_path"], inventory_payload)
            same_source = authority.verify_processed_artifacts(
                root=root,
                research_map_path=map_authority["artifact_path"],
                inventory_path=inventory_authority["artifact_path"],
                research_map_source_roles=map_authority["source_roles"],
                inventory_source_roles=inventory_authority["source_roles"],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["difference"]["map_only"], ["processed-b"])
        self.assertEqual(result["difference"]["inventory_only"], ["forged-id"])
        self.assertFalse(result["artifacts_share_processed_source"])
        self.assertIn("SOURCE_HASH_DRIFT", hash_drift["reason_codes"])
        self.assertIn("SOURCE_PATH_DRIFT", same_source["reason_codes"])

    def test_frta_reg_rrv_p1_03_source_baseline(self) -> None:
        """FRTA-REG-RRV-P1-03-SOURCE-BASELINE：自報 baseline 不得成為 authority。"""
        contracts = importlib.import_module("scripts.fog_authority_contracts")
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            baseline_authority = contracts.load_data_authority()["trusted_baseline"]
            canonical_roles = baseline_authority["protected_roles"]
            canonical_path = baseline_authority["path"]
            canonical_identity = baseline_authority["source_identity"]
            for role, relative_path in canonical_roles.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"canonical-{role}\n", encoding="utf-8")
            for role in canonical_roles:
                path = root / f"attacker/{role}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"attacker-{role}\n", encoding="utf-8")
            forged_baseline = {
                "schema_version": "fog-protected-baseline.v1",
                "created_at_utc": "2026-07-28T01:00:00Z",
                "source_identity": "trusted-mainline",
                "artifacts": [
                    {
                        "role": role,
                        "path": f"attacker/{role}.txt",
                        "sha256": _sha256(root / f"attacker/{role}.txt"),
                    }
                    for role in canonical_roles
                ],
            }
            _write_json(root / canonical_path, forged_baseline)

            result = contracts.verify_trusted_baseline(
                root=root,
                baseline_path=canonical_path,
                protected_roles=canonical_roles,
                expected_source_identity=canonical_identity,
            )
            canonical_baseline = {
                "schema_version": "fog-protected-baseline.v1",
                "created_at_utc": "2026-07-28T01:00:00Z",
                "source_identity": canonical_identity,
                "artifacts": [
                    {
                        "role": role,
                        "path": relative_path,
                        "sha256": _sha256(root / relative_path),
                    }
                    for role, relative_path in canonical_roles.items()
                ],
            }
            _write_json(root / canonical_path, canonical_baseline)
            canonical_result = contracts.verify_trusted_baseline(
                root=root,
                baseline_path=canonical_path,
                protected_roles=canonical_roles,
                expected_source_identity=canonical_identity,
            )
            (root / canonical_roles["model"]).write_text(
                "drifted-model\n",
                encoding="utf-8",
            )
            hash_drift = contracts.verify_trusted_baseline(
                root=root,
                baseline_path=canonical_path,
                protected_roles=canonical_roles,
                expected_source_identity=canonical_identity,
            )
            attacker_baseline = copy.deepcopy(canonical_baseline)
            attacker_baseline["source_identity"] = "attacker-selected-identity"
            _write_json(root / "attacker/runtime-selected-baseline.json", attacker_baseline)
            self_reported = contracts.verify_trusted_baseline(
                root=root,
                baseline_path="attacker/runtime-selected-baseline.json",
                protected_roles=canonical_roles,
                expected_source_identity="attacker-selected-identity",
            )

        self.assertFalse(result["ok"])
        self.assertIn("PROTECTED_PATH_SET_DRIFT", result["reason_codes"])
        self.assertTrue(canonical_result["ok"])
        self.assertIn("PROTECTED_HASH_DRIFT", hash_drift["reason_codes"])
        self.assertFalse(self_reported["ok"])
        self.assertIn(
            "DATA_AUTHORITY_ARGUMENT_DRIFT",
            self_reported["reason_codes"],
        )

    def test_frta_reg_receipt_v3_exact(self) -> None:
        """FRTA-REG-RECEIPT-V3-EXACT：exact schema 與 forged lineage 必須拒絕。"""
        verifier = importlib.import_module("scripts.verify_closed_regime_runtime")
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            schema_path = root / "docs/architecture/fog_runtime_receipt_v3.schema.json"
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_bytes(SCHEMA_SOURCE.read_bytes())
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            receipt = copy.deepcopy(schema["examples"][0])
            receipt["daily_research_artifact"]["path"] = (
                "artifacts/autonomous_research/"
                "autonomous_research_daily_quota_2026-08-08.json"
            )

            policy = {
                "schema_version": "fog-runtime-time-authority.v1",
                "market_id": "TWSE",
                "market_timezone": "Asia/Taipei",
                "market_day_semantics": "local-civil-date",
                "timestamp_format": "rfc3339-utc-z",
                "receipt_schema_version": "closed-regime-runtime-receipt.v3",
                "freshness": {"max_age_seconds": 900, "future_tolerance_seconds": 5},
                "lifecycle": {"market_midnight_boundary": "hard"},
            }
            _write_json(root / "config/fog_runtime_time_authority_v1.json", policy)
            regime = {
                "schema_version": "market-regime-history.v2",
                "rows": [
                    {
                        "trade_date": "2026-08-07",
                        "as_of_date": "2026-08-07",
                        "base_regime": "RISK_OFF",
                        "family_tags": ["HIGH_VOLATILITY"],
                    }
                ],
            }
            daily = {
                "schema_version": "autonomous-research-run.v1",
                "run_date": "2026-08-08",
                "source_date": "2026-08-07",
                "topic_runs": [
                    {
                        "topic": {"topic_id": "topic-001"},
                        "status": "OK",
                        "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX"},
                    }
                ],
            }
            features_path = root / "data/clean/features.parquet"
            features_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-07"]),
                    "stock_id": ["0001"],
                }
            ).to_parquet(features_path)
            daily["source_lineage"] = {
                "schema_version": "fog-daily-source-lineage.v1",
                "features_path": "data/clean/features.parquet",
                "features_sha256": _sha256(features_path),
                "daily_source_date": "2026-08-07",
            }
            research_contract = {"schema_version": "regime-research-contract.v1"}
            _write_json(root / receipt["market_regime_history"]["path"], regime)
            _write_json(root / receipt["daily_research_artifact"]["path"], daily)
            _write_json(root / receipt["research_contract"]["path"], research_contract)
            receipt["time_authority"]["contract_hash"] = _canonical_hash(policy)
            receipt["market_regime_history"]["sha256"] = _sha256(
                root / receipt["market_regime_history"]["path"]
            )
            receipt["daily_research_artifact"]["sha256"] = _sha256(
                root / receipt["daily_research_artifact"]["path"]
            )
            receipt["research_contract"]["sha256"] = _sha256(
                root / receipt["research_contract"]["path"]
            )

            hostile_receipts = []
            missing = copy.deepcopy(receipt)
            missing.pop("state_transition")
            hostile_receipts.append(missing)
            unknown = copy.deepcopy(receipt)
            unknown["unexpected"] = True
            hostile_receipts.append(unknown)
            wrong_type = copy.deepcopy(receipt)
            wrong_type["closed_regime_research"] = "true"
            hostile_receipts.append(wrong_type)
            forged_lineage = copy.deepcopy(receipt)
            forged_lineage["daily_research_artifact"]["daily_source_date"] = "2026-08-06"
            hostile_receipts.append(forged_lineage)

            results = [
                verifier.verify_receipt(
                    item,
                    project_root=root,
                    verification_time_utc="2026-08-08T02:02:00Z",
                )
                for item in hostile_receipts
            ]

        self.assertTrue(all(not result["ok"] for result in results))
        self.assertIn("RECEIPT_SCHEMA_REJECT", results[0]["reason_codes"])
        self.assertIn("RECEIPT_SCHEMA_REJECT", results[1]["reason_codes"])
        self.assertIn("RECEIPT_SCHEMA_REJECT", results[2]["reason_codes"])
        self.assertIn("DAILY_SOURCE_DATE_MISMATCH", results[3]["reason_codes"])

    def test_frta_reg_time_date_lineage(self) -> None:
        """FRTA-REG-TIME-DATE-LINEAGE：UTC 日界與休市日 lineage 必須分離。"""
        time_authority = importlib.import_module("scripts.fog_runtime_time_authority")
        self.assertEqual(
            time_authority.derive_market_run_date("2026-07-27T16:30:00Z"),
            "2026-07-28",
        )
        valid = time_authority.verify_date_lineage(
            market_run_date="2026-08-08",
            artifact_run_date="2026-08-08",
            daily_source_date="2026-08-07",
            source_trade_date="2026-08-07",
            canonical_artifact_run_date="2026-08-08",
            canonical_daily_source_date="2026-08-07",
            canonical_source_trade_date="2026-08-07",
        )
        wrong = time_authority.verify_date_lineage(
            market_run_date="2026-08-08",
            artifact_run_date="2026-08-08",
            daily_source_date="2026-08-06",
            source_trade_date="2026-08-07",
            canonical_artifact_run_date="2026-08-08",
            canonical_daily_source_date="2026-08-07",
            canonical_source_trade_date="2026-08-07",
        )
        future = time_authority.verify_date_lineage(
            market_run_date="2026-08-08",
            artifact_run_date="2026-08-08",
            daily_source_date="2026-08-09",
            source_trade_date="2026-08-07",
            canonical_artifact_run_date="2026-08-08",
            canonical_daily_source_date="2026-08-07",
            canonical_source_trade_date="2026-08-07",
        )
        drift = time_authority.verify_date_lineage(
            market_run_date="2026-08-08",
            artifact_run_date="2026-08-07",
            daily_source_date="2026-08-07",
            source_trade_date="2026-08-07",
            canonical_artifact_run_date="2026-08-08",
            canonical_daily_source_date="2026-08-07",
            canonical_source_trade_date="2026-08-07",
        )

        self.assertTrue(valid["ok"])
        self.assertIn("DAILY_SOURCE_DATE_MISMATCH", wrong["reason_codes"])
        self.assertIn("FUTURE_DAILY_SOURCE_DATE", future["reason_codes"])
        self.assertIn("ARTIFACT_IDENTITY_DRIFT", drift["reason_codes"])

    def test_receipt_v3_producer_is_deterministic_and_verifiable(self) -> None:
        producer = importlib.import_module("scripts.verify_closed_regime_runtime")
        time_authority = importlib.import_module("scripts.fog_runtime_time_authority")
        with _runtime_fixture() as (root, _):
            context = time_authority.build_run_context(
                "2026-08-08T02:00:00Z",
                project_root=root,
            )
            first = producer.build_receipt(
                run_context=context,
                generated_at_utc="2026-08-08T02:01:00Z",
                project_root=root,
            )
            second = producer.build_receipt(
                run_context=context,
                generated_at_utc="2026-08-08T02:01:00Z",
                project_root=root,
            )
            verification = producer.verify_receipt(
                first,
                project_root=root,
                verification_time_utc="2026-08-08T02:02:00Z",
            )

        self.assertEqual(first, second)
        self.assertTrue(verification["ok"], verification)
        self.assertEqual(first["time_authority"]["market_run_date"], "2026-08-08")
        self.assertEqual(
            first["daily_research_artifact"]["daily_source_date"],
            "2026-08-07",
        )

    def test_receipt_producer_rejects_source_and_artifact_drift(self) -> None:
        producer = importlib.import_module("scripts.verify_closed_regime_runtime")
        time_authority = importlib.import_module("scripts.fog_runtime_time_authority")
        with _runtime_fixture() as (root, paths):
            context = time_authority.build_run_context(
                "2026-08-08T02:00:00Z",
                project_root=root,
            )
            daily_path = root / str(paths["daily"])
            daily = json.loads(daily_path.read_text(encoding="utf-8"))
            daily["run_date"] = "2026-08-07"
            _write_json(daily_path, daily)
            with self.assertRaisesRegex(
                producer.ClosedRegimeRuntimeError,
                "ARTIFACT_IDENTITY_DRIFT",
            ):
                producer.build_receipt(
                    run_context=context,
                    generated_at_utc="2026-08-08T02:01:00Z",
                    project_root=root,
                )
            daily["run_date"] = "2026-08-08"
            daily["source_date"] = "2026-08-09"
            daily["source_lineage"]["daily_source_date"] = "2026-08-09"
            _write_json(daily_path, daily)
            with self.assertRaisesRegex(
                producer.ClosedRegimeRuntimeError,
                "DAILY_ARTIFACT_SCHEMA_REJECT",
            ):
                producer.build_receipt(
                    run_context=context,
                    generated_at_utc="2026-08-08T02:01:00Z",
                    project_root=root,
                )

    def test_receipt_producer_rejects_missing_daily_source_lineage(self) -> None:
        """Producer 不得以 regime/run/host date補造 daily source lineage。"""
        producer = importlib.import_module("scripts.verify_closed_regime_runtime")
        time_authority = importlib.import_module(
            "scripts.fog_runtime_time_authority"
        )
        with _runtime_fixture() as (root, paths):
            context = time_authority.build_run_context(
                "2026-08-08T02:00:00Z",
                project_root=root,
            )
            daily_path = root / str(paths["daily"])
            daily = json.loads(daily_path.read_text(encoding="utf-8"))
            daily.pop("source_date")
            daily.pop("source_lineage")
            _write_json(daily_path, daily)

            with self.assertRaisesRegex(
                producer.ClosedRegimeRuntimeError,
                "DAILY_ARTIFACT_SCHEMA_REJECT",
            ):
                producer.build_receipt(
                    run_context=context,
                    generated_at_utc="2026-08-08T02:01:00Z",
                    project_root=root,
                )

    def test_receipt_verifier_rejects_missing_daily_source_lineage(self) -> None:
        """Independent verifier 必須從 canonical daily artifact重讀 lineage。"""
        runtime = importlib.import_module("scripts.verify_closed_regime_runtime")
        time_authority = importlib.import_module(
            "scripts.fog_runtime_time_authority"
        )
        with _runtime_fixture() as (root, paths):
            context = time_authority.build_run_context(
                "2026-08-08T02:00:00Z",
                project_root=root,
            )
            receipt = runtime.build_receipt(
                run_context=context,
                generated_at_utc="2026-08-08T02:01:00Z",
                project_root=root,
            )
            daily_path = root / str(paths["daily"])
            daily = json.loads(daily_path.read_text(encoding="utf-8"))
            daily.pop("source_date")
            daily.pop("source_lineage")
            _write_json(daily_path, daily)

            result = runtime.verify_receipt(
                receipt,
                project_root=root,
                verification_time_utc="2026-08-08T02:02:00Z",
            )

        self.assertFalse(result["ok"])
        self.assertIn("DAILY_ARTIFACT_SCHEMA_REJECT", result["reason_codes"])

    def test_v2_receipt_cannot_be_relabelled(self) -> None:
        verifier = importlib.import_module("scripts.verify_closed_regime_runtime")
        with _runtime_fixture() as (root, _):
            v2 = {
                "schema_version": "closed-regime-runtime-receipt.v2",
                "status": "OK",
            }
            result = verifier.verify_receipt(
                v2,
                project_root=root,
                verification_time_utc="2026-08-08T02:02:00Z",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_codes"], ["RECEIPT_SCHEMA_REJECT"])


if __name__ == "__main__":
    unittest.main()
