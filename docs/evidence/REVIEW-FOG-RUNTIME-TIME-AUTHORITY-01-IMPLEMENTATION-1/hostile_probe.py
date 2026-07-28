#!/usr/bin/env python3
"""獨立 hostile probes；不重用 candidate tests 或 stored fixtures。"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.fog_authority_contracts import (
    resolve_repo_path,
    verify_trusted_baseline,
)
from scripts.fog_runtime_time_authority import (
    build_run_context,
    derive_market_run_date,
    verify_freshness,
)
from scripts.verify_closed_regime_runtime import build_receipt, verify_receipt
from scripts.verify_processed_id_authority import verify_processed_artifacts


SCHEMA_SOURCE = ROOT / "docs/architecture/fog_runtime_receipt_v3.schema.json"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def runtime_fixture(*, include_daily_source: bool = True) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        schema = root / "docs/architecture/fog_runtime_receipt_v3.schema.json"
        schema.parent.mkdir(parents=True)
        schema.write_bytes(SCHEMA_SOURCE.read_bytes())
        write_json(
            root / "config/fog_runtime_time_authority_v1.json",
            {
                "schema_version": "fog-runtime-time-authority.v1",
                "market_id": "TWSE",
                "market_timezone": "Asia/Taipei",
                "market_day_semantics": "local-civil-date",
                "timestamp_format": "rfc3339-utc-z",
                "receipt_schema_version": "closed-regime-runtime-receipt.v3",
                "freshness": {
                    "max_age_seconds": 900,
                    "future_tolerance_seconds": 5,
                },
                "lifecycle": {"market_midnight_boundary": "hard"},
            },
        )
        write_json(
            root / "artifacts/market_regime_history.json",
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
        daily = {
            "schema_version": "autonomous-research-run.v1",
            "status": "OK",
            "run_date": "2026-08-08",
            "topic_runs": [
                {
                    "topic": {"topic_id": "hostile-topic"},
                    "status": "OK",
                    "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX"},
                }
            ],
        }
        if include_daily_source:
            daily["source_date"] = "2026-08-07"
        write_json(
            root
            / "artifacts/autonomous_research/"
            "autonomous_research_daily_quota_2026-08-08.json",
            daily,
        )
        write_json(
            root / "config/regime_research_contract.json",
            {"schema_version": "regime-research-contract.v1"},
        )
        yield root


def processed_authority_probes() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        write_json(root / "attacker/map-source.json", {"source": "attacker-map"})
        write_json(
            root / "attacker/inventory-source.json",
            {"source": "attacker-inventory"},
        )
        common_rows = [{"topic_id": "topic-a", "status": "COMPLETED"}]
        write_json(
            root / "map.json",
            {
                "processed": common_rows,
                "source_hashes": {
                    "map": {
                        "path": "attacker/map-source.json",
                        "sha256": digest(root / "attacker/map-source.json"),
                    }
                },
            },
        )
        write_json(
            root / "inventory.json",
            {
                "processed": common_rows,
                "source_hashes": {
                    "inventory": {
                        "path": "attacker/inventory-source.json",
                        "sha256": digest(root / "attacker/inventory-source.json"),
                    }
                },
            },
        )
        self_reported = verify_processed_artifacts(
            root=root,
            research_map_path="map.json",
            inventory_path="inventory.json",
            research_map_source_roles={"map": "attacker/map-source.json"},
            inventory_source_roles={"inventory": "attacker/inventory-source.json"},
        )

        inventory = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
        inventory["processed"] = [{"topic_id": "forged", "status": "COMPLETED"}]
        write_json(root / "inventory.json", inventory)
        set_drift = verify_processed_artifacts(
            root=root,
            research_map_path="map.json",
            inventory_path="inventory.json",
            research_map_source_roles={"map": "attacker/map-source.json"},
            inventory_source_roles={"inventory": "attacker/inventory-source.json"},
        )

        inventory["processed"] = common_rows
        inventory["source_hashes"]["inventory"] = {
            "path": "attacker/map-source.json",
            "sha256": digest(root / "attacker/map-source.json"),
        }
        write_json(root / "inventory.json", inventory)
        shared = verify_processed_artifacts(
            root=root,
            research_map_path="map.json",
            inventory_path="inventory.json",
            research_map_source_roles={"map": "attacker/map-source.json"},
            inventory_source_roles={"inventory": "attacker/map-source.json"},
        )

        inventory["source_hashes"]["inventory"] = {
            "path": "attacker/inventory-source.json",
            "sha256": "0" * 64,
        }
        write_json(root / "inventory.json", inventory)
        hash_drift = verify_processed_artifacts(
            root=root,
            research_map_path="map.json",
            inventory_path="inventory.json",
            research_map_source_roles={"map": "attacker/map-source.json"},
            inventory_source_roles={"inventory": "attacker/inventory-source.json"},
        )

        inventory["source_hashes"]["inventory"] = {
            "path": "attacker/inventory-source.json",
            "sha256": digest(root / "attacker/inventory-source.json"),
        }
        write_json(root / "inventory.json", inventory)
        role_swap = verify_processed_artifacts(
            root=root,
            research_map_path="map.json",
            inventory_path="inventory.json",
            research_map_source_roles={"map": "attacker/inventory-source.json"},
            inventory_source_roles={"inventory": "attacker/map-source.json"},
        )

        return {
            "forged_set_rejected": not set_drift["ok"],
            "shared_source_rejected": not shared["ok"],
            "source_hash_drift_rejected": not hash_drift["ok"],
            "source_role_swap_rejected": not role_swap["ok"],
            "self_reported_distinct_sources_rejected": not self_reported["ok"],
        }


def path_probes() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        outside = root.parent / f"{root.name}-outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        link = root / "escape.json"
        link.symlink_to(outside)
        results = {}
        for name, value in {
            "parent_escape": "../outside.json",
            "symlink_escape": "escape.json",
        }.items():
            try:
                resolve_repo_path(root, value)
            except ValueError:
                results[name] = True
            else:
                results[name] = False
        outside.unlink()
        return results


def baseline_probes() -> dict[str, bool]:
    roles = {
        "model": "models/latest_lgbm.pkl",
        "baseline": "models/baseline_stats.json",
        "ranking": "app/agent_b_ranking.py",
        "weights": "config/signals.yaml",
        "promotion": "app/modeling/model_runtime_promotion.py",
    }

    def materialize_protected_files(root: Path, prefix: str) -> None:
        for role, relative in roles.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{prefix}-{role}\n", encoding="utf-8")

    def baseline_payload(
        root: Path,
        *,
        source_identity: str,
    ) -> dict[str, object]:
        return {
            "schema_version": "fog-protected-baseline.v1",
            "created_at_utc": "2026-07-28T01:00:00Z",
            "source_identity": source_identity,
            "artifacts": [
                {
                    "role": role,
                    "path": relative,
                    "sha256": digest(root / relative),
                }
                for role, relative in roles.items()
            ],
        }

    with tempfile.TemporaryDirectory() as legitimate_tmp:
        legitimate_root = Path(legitimate_tmp)
        materialize_protected_files(legitimate_root, "repo-owned")
        legitimate_path = "authority/trusted-protected-baseline.json"
        write_json(
            legitimate_root / legitimate_path,
            baseline_payload(
                legitimate_root,
                source_identity="trusted-mainline",
            ),
        )
        legitimate = verify_trusted_baseline(
            root=legitimate_root,
            baseline_path=legitimate_path,
            expected_source_identity="trusted-mainline",
        )
        (legitimate_root / roles["model"]).write_text(
            "drift\n",
            encoding="utf-8",
        )
        drift = verify_trusted_baseline(
            root=legitimate_root,
            baseline_path=legitimate_path,
            expected_source_identity="trusted-mainline",
        )

    with tempfile.TemporaryDirectory() as attacker_tmp:
        attacker_root = Path(attacker_tmp)
        materialize_protected_files(attacker_root, "runtime-current")
        attacker_path = "attacker/runtime-selected-baseline.json"
        write_json(
            attacker_root / attacker_path,
            baseline_payload(
                attacker_root,
                source_identity="attacker-selected-identity",
            ),
        )
        self_reported = verify_trusted_baseline(
            root=attacker_root,
            baseline_path=attacker_path,
            expected_source_identity="attacker-selected-identity",
        )

    return {
        "legitimate_shape_control_accepted": legitimate["ok"],
        "self_reported_baseline_rejected": not self_reported["ok"],
        "baseline_hash_drift_rejected": not drift["ok"],
    }


def receipt_and_time_probes() -> dict[str, bool]:
    with runtime_fixture() as root:
        context = build_run_context("2026-08-08T02:00:00Z", project_root=root)
        receipt = build_receipt(
            run_context=context,
            generated_at_utc="2026-08-08T02:01:00Z",
            project_root=root,
        )
        control = verify_receipt(
            receipt,
            project_root=root,
            verification_time_utc="2026-08-08T02:02:00Z",
        )
        mutations = {}
        for name, mutate in {
            "missing": lambda value: value.pop("queue_owner"),
            "unknown": lambda value: value.update({"unknown": True}),
            "wrong_type": lambda value: value.update({"runner_identity": 7}),
            "wrong_contract_hash": lambda value: value["time_authority"].update(
                {"contract_hash": "0" * 64}
            ),
            "naive_timestamp": lambda value: value["time_authority"].update(
                {"generated_at_utc": "2026-08-08T02:01:00"}
            ),
            "artifact_identity_drift": lambda value: value[
                "daily_research_artifact"
            ].update({"artifact_run_date": "2026-08-07"}),
        }.items():
            candidate = copy.deepcopy(receipt)
            mutate(candidate)
            mutations[name] = not verify_receipt(
                candidate,
                project_root=root,
                verification_time_utc="2026-08-08T02:02:00Z",
            )["ok"]

        original_tz = os.environ.get("TZ")
        try:
            host_results = []
            for host_tz in ("UTC", "Asia/Taipei", "America/Los_Angeles"):
                os.environ["TZ"] = host_tz
                time.tzset()
                host_results.append(
                    verify_receipt(
                        receipt,
                        project_root=root,
                        verification_time_utc="2026-08-08T02:02:00Z",
                    )["ok"]
                )
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

    with runtime_fixture(include_daily_source=False) as root:
        context = build_run_context("2026-08-08T02:00:00Z", project_root=root)
        try:
            build_receipt(
                run_context=context,
                generated_at_utc="2026-08-08T02:01:00Z",
                project_root=root,
            )
        except ValueError:
            missing_daily_source_rejected = True
        else:
            missing_daily_source_rejected = False

    freshness = {
        "future_boundary_accept": verify_freshness(
            "2026-08-08T02:00:05Z", "2026-08-08T02:00:00Z"
        )["ok"],
        "future_over_reject": not verify_freshness(
            "2026-08-08T02:00:05.001000Z", "2026-08-08T02:00:00Z"
        )["ok"],
        "stale_boundary_accept": verify_freshness(
            "2026-08-08T02:00:00Z", "2026-08-08T02:15:00Z"
        )["ok"],
        "stale_over_reject": not verify_freshness(
            "2026-08-08T02:00:00Z", "2026-08-08T02:15:00.001000Z"
        )["ok"],
    }
    return {
        "control_accepted": control["ok"],
        **{f"{name}_rejected": value for name, value in mutations.items()},
        "missing_daily_source_rejected": missing_daily_source_rejected,
        "host_timezone_invariant": all(host_results),
        "utc_date_lineage": (
            derive_market_run_date("2026-07-27T16:30:00Z") == "2026-07-28"
        ),
        **freshness,
    }


def static_probes() -> dict[str, bool]:
    worker = (ROOT / "scripts/run_fog_research_worker.sh").read_text(encoding="utf-8")
    daily = (ROOT / "scripts/run_daily_research_quota.sh").read_text(encoding="utf-8")
    plist = (
        ROOT / "scripts/com.new-top10.fog-research-worker.plist"
    ).read_text(encoding="utf-8")
    return {
        "shell_has_no_date_percent_f_identity": "date +%F" not in worker + daily,
        "worker_creates_context_once": worker.count(
            "scripts/fog_runtime_time_authority.py --output"
        )
        == 1,
        "daily_requires_context": "TOP10_FOG_RUN_CONTEXT is required" in daily,
        "queue_owner_fixed": 'QUEUE_OWNER_NAME_FILE="$QUEUE_OWNER_LOCK_DIR/owner"'
        in worker
        and 'echo "fog_worker" > "$QUEUE_OWNER_NAME_FILE"' in worker,
        "plist_does_not_inject_policy": all(
            marker not in plist
            for marker in (
                "<key>TZ</key>",
                "<key>TOP10_RUN_DATE</key>",
                "<key>TOP10_RESEARCH_DATE</key>",
                "FRESHNESS",
            )
        ),
    }


def main() -> int:
    results = {
        "processed_authority": processed_authority_probes(),
        "path_security": path_probes(),
        "baseline_authority": baseline_probes(),
        "receipt_and_time": receipt_and_time_probes(),
        "static_wiring": static_probes(),
    }
    failures = [
        f"{group}.{name}"
        for group, checks in results.items()
        for name, passed in checks.items()
        if not passed
    ]
    output = {"ok": not failures, "failures": failures, "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
