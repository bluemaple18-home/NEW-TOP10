from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import verify_closed_regime_runtime as runtime_verifier
import verify_daily_research_quota as daily_verifier
import verify_fog_closed_regime_recovery as recovery_verifier
import verify_processed_id_authority as processed_verifier


RUN_DATE = "2099-01-05"
VERIFICATION_TIME = datetime(2099, 1, 5, 1, tzinfo=timezone.utc)


def write_history(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "market-regime-history.v2",
                "contract": {"research_only": True},
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def write_contract(path: Path) -> None:
    path.write_text('{"contract":"fixture"}\n', encoding="utf-8")


def regime_row(
    trade_date: str,
    *,
    base_regime: str = "RISK_OFF",
    is_transition: bool = False,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "as_of_date": trade_date,
        "base_regime": base_regime,
        "family_tags": [],
        "is_transition": is_transition,
    }


def test_daily_public_path_enables_closed_regime_with_verified_history() -> None:
    script = (PROJECT_ROOT / "scripts" / "run_daily_research_quota.sh").read_text(
        encoding="utf-8"
    )

    assert "--closed-regime-research" in script
    assert "--market-regime-history" in script
    assert "closed_regime_research=true" in script


def test_daily_public_command_emits_closed_regime_receipt(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copy(
        PROJECT_ROOT / "scripts" / "run_daily_research_quota.sh",
        scripts_dir / "run_daily_research_quota.sh",
    )
    history = tmp_path / "history.json"
    contract = tmp_path / "contract.json"
    fake_python = tmp_path / "fake_python.py"
    command_capture = tmp_path / "command.json"
    write_history(history, [regime_row(RUN_DATE)])
    write_contract(contract)
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import hashlib
import os
import sys
from pathlib import Path

script = sys.argv[1]
args = sys.argv[2:]
root = Path.cwd()
def value(flag):
    return args[args.index(flag) + 1]

if script.endswith("verify_closed_regime_runtime.py"):
    output = root / value("--output")
    output.parent.mkdir(parents=True, exist_ok=True)
    complete = "--daily-research-artifact" in args
    daily_path = root / value("--daily-research-artifact") if complete else None
    daily = json.loads(daily_path.read_text()) if daily_path else {}
    topic_runs = [{
        "topic_id": str((row.get("topic") or {}).get("topic_id") or ""),
        "status": str(row.get("status") or ""),
        "decision": (row.get("outcome") or {}).get("decision"),
    } for row in daily.get("topic_runs", [])]
    topic_hash = hashlib.sha256(json.dumps(
        topic_runs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    output.write_text(json.dumps({
        "schema_version": "closed-regime-runtime-receipt.v2",
        "status": "OK" if complete else "READY",
        "generated_at": "2099-01-05T00:00:00+00:00",
        "run_date": value("--run-date"),
        "closed_regime_research": True,
        "queue_owner": "fog_worker",
        "runner_identity": "scripts/run_daily_research_quota.sh",
        "exact_regime": {"base_regime": "RISK_OFF", "family_tags": [], "identity_id": "RISK_OFF|"},
        "market_regime_history": {
            "path": value("--market-regime-history"),
            "schema_version": "market-regime-history.v2",
            "sha256": "fixture",
            "source_trade_date": value("--run-date"),
        },
        "research_contract": {"path": value("--research-contract"), "sha256": "fixture"},
        "state_transition": {
            "from": "VERIFIED_HISTORY",
            "to": "CLOSED_RESEARCH_COMPLETED" if complete else "READY_FOR_CLOSED_RESEARCH",
        },
        "daily_research_artifact": ({
            "path": value("--daily-research-artifact"),
            "schema_version": "autonomous-research-run.v1",
            "sha256": hashlib.sha256(daily_path.read_bytes()).hexdigest(),
            "run_date": value("--run-date"),
        } if complete else None),
        "topic_runs": topic_runs,
        "topic_runs_sha256": topic_hash,
        "production_impact": "NO_PRODUCTION_CHANGE",
    }))
elif script.endswith("run_autonomous_research.py"):
    assert "--closed-regime-research" in args
    assert "--market-regime-history" in args
    Path(os.environ["COMMAND_CAPTURE"]).write_text(json.dumps(args))
    output = root / value("--output")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": "autonomous-research-run.v1",
        "status": "OK",
        "contract": {"closed_regime_research": True},
        "inputs": {
            "closed_regime_research": True,
            "market_regime_history": value("--market-regime-history"),
            "research_contract": value("--research-contract"),
            "from_queue": True,
        },
        "selected_topics": [],
        "topic_runs": [],
        "outcome": {"decision": "NO_EXECUTABLE_TOPIC"},
    }))
elif script.endswith("verify_daily_research_quota.py"):
    output = root / "artifacts/autonomous_research/daily_research_quota_verification_latest.json"
    output.write_text('{"status":"PARTIAL_NO_MORE_WORK"}')
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = {
        **os.environ,
        "TOP10_RESEARCH_PYTHON": str(fake_python),
        "TOP10_RESEARCH_DATE": RUN_DATE,
        "TOP10_MARKET_REGIME_HISTORY": str(history),
        "TOP10_REGIME_RESEARCH_CONTRACT": str(contract),
        "TOP10_REFRESH_RESEARCH_MAP": "0",
        "COMMAND_CAPTURE": str(command_capture),
    }

    completed = subprocess.run(
        ["bash", str(scripts_dir / "run_daily_research_quota.sh")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    command = json.loads(command_capture.read_text(encoding="utf-8"))
    assert command[command.index("--market-regime-history") + 1] == str(history)
    receipt = json.loads(
        (
            tmp_path
            / f"artifacts/autonomous_research/closed_regime_runtime_{RUN_DATE}.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["closed_regime_research"] is True
    assert receipt["schema_version"] == "closed-regime-runtime-receipt.v2"
    assert receipt["queue_owner"] == "fog_worker"
    assert receipt["runner_identity"] == "scripts/run_daily_research_quota.sh"
    assert receipt["state_transition"]["to"] == "CLOSED_RESEARCH_COMPLETED"
    assert receipt["daily_research_artifact"]["run_date"] == RUN_DATE
    assert receipt["exact_regime"]["identity_id"] == "RISK_OFF|"


def test_missing_regime_history_fails_closed(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    write_contract(contract)

    with pytest.raises(FileNotFoundError):
        runtime_verifier.verify_runtime(
            RUN_DATE,
            tmp_path / "missing.json",
            contract,
        )


def test_future_only_regime_history_fails_closed(tmp_path: Path) -> None:
    history = tmp_path / "future.json"
    contract = tmp_path / "contract.json"
    write_history(history, [regime_row("2099-01-06")])
    write_contract(contract)

    with pytest.raises(ValueError, match="找不到具有 as_of_date"):
        runtime_verifier.verify_runtime(RUN_DATE, history, contract)


@pytest.mark.parametrize(
    ("base_regime", "is_transition"),
    [("UNKNOWN", False), ("RISK_OFF", True)],
)
def test_unknown_or_transition_current_regime_fails_closed(
    tmp_path: Path,
    base_regime: str,
    is_transition: bool,
) -> None:
    history = tmp_path / "blocked.json"
    contract = tmp_path / "contract.json"
    write_history(
        history,
        [
            regime_row(
                RUN_DATE,
                base_regime=base_regime,
                is_transition=is_transition,
            )
        ],
    )
    write_contract(contract)

    with pytest.raises(ValueError, match="UNKNOWN/transition"):
        runtime_verifier.verify_runtime(RUN_DATE, history, contract)


def test_processed_id_verifier_rejects_forged_inventory_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def completed(combo_id: str) -> dict[str, object]:
        return {
            "schema_version": "research-map-run-history.v2",
            "map_version": "v2",
            "combo_id": combo_id,
            "status": "completed",
            "artifact_path": f"artifacts/research/{combo_id}.json",
            "dimensions": {
                "regime_gate": "RISK_OFF",
                "risk_guard": "NONE",
                "entry_filter": "LOG_GATE",
            },
        }

    good_ids = ["processed-a", "processed-b"]
    history = [completed(combo_id) for combo_id in good_ids]
    map_payload = {
        "schema_version": "research-fog-map.v2",
        "date": RUN_DATE,
        "contract": {"progress_from_run_history_jsonl": True},
        "source_hashes": {"fixtures/map-source.jsonl": "a" * 64},
        "summary": {"expanded_processed": 2},
        "processed_records": history,
    }
    inventory_payload = {
        "schema_version": "weekend-universe-inventory.v1",
        "date": RUN_DATE,
        "contract": {"manual_progress_fill_allowed": False},
        "source_hashes": {"fixtures/inventory-source.jsonl": "b" * 64},
        "summary": {"current_processed_count": 2},
        "records": [
            {
                "combo_id": "processed-a",
                "current_status": "EXECUTED_REPLAY",
                "source_artifact": "artifacts/research/processed-a.json",
            },
            {
                "combo_id": "forged-id",
                "current_status": "EXECUTED_REPLAY",
                "source_artifact": "artifacts/research/forged-id.json",
            },
        ],
    }
    lineage_map, lineage_inventory, _ = _processed_lineage_fixture(tmp_path)
    map_payload["source_lineage"] = lineage_map["source_lineage"]
    inventory_payload["source_lineage"] = lineage_inventory["source_lineage"]
    monkeypatch.setattr(processed_verifier, "PROJECT_ROOT", tmp_path)

    payload = processed_verifier.build_payload(
        [],
        history,
        map_payload,
        inventory_payload,
    )

    assert payload["status"] == "FAILED"
    difference = next(
        check["value"]
        for check in payload["checks"]
        if check["name"] == "processed_id_symmetric_difference_empty"
    )
    assert difference == {
        "map_only": ["processed-b"],
        "inventory_only": ["forged-id"],
    }

    inventory_payload["records"][1]["combo_id"] = "processed-b"
    inventory_payload["records"][1][
        "source_artifact"
    ] = "artifacts/research/processed-b.json"
    repaired = processed_verifier.build_payload(
        [],
        history,
        map_payload,
        inventory_payload,
    )
    assert repaired["status"] == "OK"


def test_daily_verifier_rejects_stale_forged_incomplete_runtime_receipt(
    tmp_path: Path,
) -> None:
    artifact, receipt = _write_daily_verifier_attack_fixture(tmp_path)

    payload = daily_verifier.build_payload(artifact, min_quota=5, runtime_receipt_path=receipt)

    assert payload["status"] == "BLOCKED"
    failed = {check["name"] for check in payload["checks"] if not check["ok"]}
    assert {
        "runtime_receipt_schema",
        "runtime_receipt_run_date",
        "runtime_receipt_identity",
        "runtime_receipt_state_transition",
        "runtime_receipt_topic_run_lineage",
    } <= failed


def _write_daily_verifier_attack_fixture(tmp_path: Path) -> tuple[Path, Path]:
    history = tmp_path / "history.json"
    contract = tmp_path / "contract.json"
    artifact = tmp_path / "daily.json"
    receipt = tmp_path / "runtime.json"
    write_history(history, [regime_row(RUN_DATE)])
    write_contract(contract)
    topic_runs = [
        {
            "topic": {"topic_id": f"topic-{index}"},
            "status": "OK",
            "outcome": {
                "decision": "REJECTED_BY_STRATEGY_MATRIX",
                "promotion_allowed": False,
            },
            "steps": [],
        }
        for index in range(5)
    ]
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "autonomous-research-run.v1",
                "date": RUN_DATE,
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
                    "execute_topic_count": 5,
                    "closed_regime_research": True,
                    "market_regime_history": str(history),
                    "research_contract": str(contract),
                },
                "selected_topics": [run["topic"] for run in topic_runs],
                "topic_runs": topic_runs,
                "outcome": {"decision": "REJECTED_BY_STRATEGY_MATRIX"},
            }
        ),
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps(
            {
                "status": "OK",
                "run_date": "1999-01-01",
                "closed_regime_research": True,
                "queue_owner": "forged-owner",
                "runner_identity": "forged-runner",
                "market_regime_history": {
                    "path": str(history),
                    "sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
                },
                "research_contract": {
                    "path": str(contract),
                    "sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
                },
                "exact_regime": {"identity_id": "FORGED|"},
                "production_impact": "NO_PRODUCTION_CHANGE",
            }
        ),
        encoding="utf-8",
    )
    return artifact, receipt


def test_daily_verifier_accepts_fully_bound_runtime_receipt(tmp_path: Path) -> None:
    artifact, receipt = _write_daily_verifier_attack_fixture(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    history = Path(payload["inputs"]["market_regime_history"])
    contract = Path(payload["inputs"]["research_contract"])
    bound_receipt = runtime_verifier.verify_runtime(
        RUN_DATE,
        history,
        contract,
        artifact,
    )
    bound_receipt["generated_at"] = "2099-01-05T00:00:00+00:00"
    receipt.write_text(json.dumps(bound_receipt), encoding="utf-8")

    verification = daily_verifier.build_payload(
        artifact,
        min_quota=5,
        runtime_receipt_path=receipt,
        verification_time=VERIFICATION_TIME,
    )

    assert verification["status"] == "COMPLETED"
    assert not [check for check in verification["checks"] if not check["ok"]]


def test_daily_verifier_rejects_unknown_runtime_receipt_field(tmp_path: Path) -> None:
    artifact, receipt = _write_daily_verifier_attack_fixture(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    bound_receipt = runtime_verifier.verify_runtime(
        RUN_DATE,
        Path(payload["inputs"]["market_regime_history"]),
        Path(payload["inputs"]["research_contract"]),
        artifact,
    )
    bound_receipt["forged_extension"] = True
    receipt.write_text(json.dumps(bound_receipt), encoding="utf-8")

    verification = daily_verifier.build_payload(
        artifact,
        min_quota=5,
        runtime_receipt_path=receipt,
    )

    assert verification["status"] == "BLOCKED"
    assert next(
        check
        for check in verification["checks"]
        if check["name"] == "runtime_receipt_schema"
    )["ok"] is False


def test_production_hash_gate_rejects_drift_against_trusted_baseline(
    tmp_path: Path,
) -> None:
    protected = recovery_verifier.canonical_protected_paths(tmp_path, RUN_DATE)
    for role, path in protected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}-v1\n", encoding="utf-8")
    baseline = recovery_verifier.build_production_hash_baseline(
        run_date=RUN_DATE,
        root=tmp_path,
        source_identity="candidate-fixture",
        created_at="2099-01-05T00:00:00+00:00",
    )
    assert recovery_verifier.verify_production_hash_baseline(
        baseline,
        run_date=RUN_DATE,
        root=tmp_path,
        expected_source_identity="candidate-fixture",
    )["ok"] is True
    assert recovery_verifier.verify_production_hash_baseline(
        baseline,
        run_date=RUN_DATE,
        root=tmp_path,
        expected_source_identity="forged-source",
    )["ok"] is False
    protected["model"].write_text("model-forged\n", encoding="utf-8")

    check = recovery_verifier.verify_production_hash_baseline(
        baseline,
        run_date=RUN_DATE,
        root=tmp_path,
        expected_source_identity="candidate-fixture",
    )

    assert check["ok"] is False
    assert check["hash_drift"] == ["model"]


def test_production_baseline_uses_canonical_contract_and_is_create_once(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        recovery_verifier.canonical_baseline_path(tmp_path, "../../escape")
    protected = recovery_verifier.canonical_protected_paths(tmp_path, RUN_DATE)
    for role, path in protected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}-v1\n", encoding="utf-8")
    baseline_path = recovery_verifier.canonical_baseline_path(tmp_path, RUN_DATE)
    baseline = recovery_verifier.write_production_hash_baseline_once(
        baseline_path,
        run_date=RUN_DATE,
        root=tmp_path,
        source_identity="candidate-fixture",
        created_at="2099-01-05T00:00:00+00:00",
    )

    protected["model"].write_text("model-forged\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        recovery_verifier.write_production_hash_baseline_once(
            baseline_path,
            run_date=RUN_DATE,
            root=tmp_path,
            source_identity="candidate-fixture",
            created_at="2099-01-05T00:01:00+00:00",
        )

    persisted = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert persisted == baseline
    check = recovery_verifier.verify_production_hash_baseline(
        persisted,
        run_date=RUN_DATE,
        root=tmp_path,
        expected_source_identity="candidate-fixture",
    )
    assert check["ok"] is False
    assert check["hash_drift"] == ["model"]

    arbitrary = {
        **persisted,
        "artifacts": {
            role: {
                "path": f"attacker/{role}.artifact",
                "sha256": "a" * 64,
            }
            for role in ("model", "baseline", "ranking", "weights", "promotion")
        },
    }
    arbitrary_check = recovery_verifier.verify_production_hash_baseline(
        arbitrary,
        run_date=RUN_DATE,
        root=tmp_path,
        expected_source_identity="candidate-fixture",
    )
    assert arbitrary_check["ok"] is False
    assert sorted(arbitrary_check["path_drift"]) == [
        "baseline",
        "model",
        "promotion",
        "ranking",
        "weights",
    ]

    with pytest.raises(ValueError, match="canonical baseline path"):
        recovery_verifier.write_production_hash_baseline_once(
            tmp_path / "attacker-baseline.json",
            run_date=RUN_DATE,
            root=tmp_path,
            source_identity="candidate-fixture",
            created_at="2099-01-05T00:02:00+00:00",
        )


@pytest.mark.parametrize(
    ("attack", "value"),
    [
        ("generated_at", "1999-01-01T00:00:00+00:00"),
        ("generated_at", "2199-01-01T00:00:00+00:00"),
        ("generated_at", "2099-01-05T00:00:00"),
        (
            "exact_regime",
            {
                "base_regime": "BROAD_RISK_ON",
                "family_tags": ["BIG_BULL"],
                "identity_id": "BROAD_RISK_ON|BIG_BULL",
            },
        ),
    ],
)
def test_daily_verifier_rejects_unfresh_or_forged_exact_regime(
    tmp_path: Path,
    attack: str,
    value: object,
) -> None:
    artifact, receipt = _write_daily_verifier_attack_fixture(tmp_path)
    artifact_payload = json.loads(artifact.read_text(encoding="utf-8"))
    bound_receipt = runtime_verifier.verify_runtime(
        RUN_DATE,
        Path(artifact_payload["inputs"]["market_regime_history"]),
        Path(artifact_payload["inputs"]["research_contract"]),
        artifact,
    )
    bound_receipt["generated_at"] = "2099-01-05T00:00:00+00:00"
    bound_receipt[attack] = value
    receipt.write_text(json.dumps(bound_receipt), encoding="utf-8")

    verification = daily_verifier.build_payload(
        artifact,
        min_quota=5,
        runtime_receipt_path=receipt,
        verification_time=VERIFICATION_TIME,
    )

    assert verification["status"] == "BLOCKED"
    failed = {check["name"] for check in verification["checks"] if not check["ok"]}
    expected = (
        "runtime_receipt_freshness"
        if attack == "generated_at"
        else "runtime_receipt_exact_regime"
    )
    assert expected in failed


def _source_contract_hash(
    artifact_kind: str,
    roles: dict[str, str],
) -> str:
    contract = {
        "schema_version": "fog-source-role-path-contract.v1",
        "artifact_kind": artifact_kind,
        "roles": roles,
    }
    return hashlib.sha256(
        json.dumps(
            contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _processed_lineage_fixture(
    root: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, Path]]:
    paths = {
        "topic_registry": root
        / "artifacts"
        / "autonomous_research"
        / "topic_registry.json",
        "run_history": root
        / "artifacts"
        / "autonomous_research"
        / "run_history.jsonl",
        "research_map": root
        / "artifacts"
        / "research_map"
        / "research_fog_map_latest.json",
    }
    for role, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}-source\n", encoding="utf-8")

    map_roles = {
        "topic_registry": "artifacts/autonomous_research/topic_registry.json",
        "run_history": "artifacts/autonomous_research/run_history.jsonl",
    }
    inventory_roles = {
        "research_map": "artifacts/research_map/research_fog_map_latest.json",
        **map_roles,
    }

    def lineage(artifact_kind: str, roles: dict[str, str]) -> dict[str, object]:
        return {
            "schema_version": "fog-source-lineage.v1",
            "contract_sha256": _source_contract_hash(artifact_kind, roles),
            "sources": {
                role: {
                    "path": path,
                    "sha256": hashlib.sha256(
                        (root / path).read_bytes()
                    ).hexdigest(),
                }
                for role, path in roles.items()
            },
        }

    completed = {
        "schema_version": "research-map-run-history.v2",
        "map_version": "v2",
        "combo_id": "processed-a",
        "status": "completed",
        "artifact_path": "artifacts/research/processed-a.json",
        "dimensions": {
            "regime_gate": "RISK_OFF",
            "risk_guard": "NONE",
            "entry_filter": "LOG_GATE",
        },
    }
    map_payload: dict[str, object] = {
        "schema_version": "research-fog-map.v2",
        "date": RUN_DATE,
        "contract": {"progress_from_run_history_jsonl": True},
        "source_hashes": {"missing/map-source.jsonl": "a" * 64},
        "source_lineage": lineage("research_map", map_roles),
        "summary": {"expanded_processed": 1},
        "processed_records": [completed],
    }
    inventory_payload: dict[str, object] = {
        "schema_version": "weekend-universe-inventory.v1",
        "date": RUN_DATE,
        "contract": {"manual_progress_fill_allowed": False},
        "source_hashes": {"missing/inventory-source.jsonl": "b" * 64},
        "source_lineage": lineage("weekend_inventory", inventory_roles),
        "summary": {"current_processed_count": 1},
        "processed_records": [
            {
                "combo_id": "processed-a",
                "completion_status": "completed",
                "artifact_path": "artifacts/research/processed-a.json",
            }
        ],
    }
    return map_payload, inventory_payload, paths


@pytest.mark.parametrize(
    "attack",
    [
        "missing_source",
        "source_set_addition",
        "source_set_removal",
        "path_escape",
        "symlink_escape",
    ],
)
def test_processed_source_lineage_rejects_hostile_paths_and_sets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    map_payload, inventory_payload, paths = _processed_lineage_fixture(tmp_path)
    monkeypatch.setattr(processed_verifier, "PROJECT_ROOT", tmp_path)
    map_sources = map_payload["source_lineage"]["sources"]
    inventory_sources = inventory_payload["source_lineage"]["sources"]

    if attack == "missing_source":
        paths["run_history"].unlink()
    elif attack == "source_set_addition":
        map_sources["attacker"] = {
            "path": "attacker/source.json",
            "sha256": "a" * 64,
        }
    elif attack == "source_set_removal":
        inventory_sources.pop("topic_registry")
    elif attack == "path_escape":
        map_sources["run_history"] = {
            "path": "../escape.jsonl",
            "sha256": "a" * 64,
        }
    else:
        outside = tmp_path.parent / f"{tmp_path.name}-outside.jsonl"
        outside.write_text("outside\n", encoding="utf-8")
        paths["run_history"].unlink()
        paths["run_history"].symlink_to(outside)
        map_sources["run_history"]["sha256"] = hashlib.sha256(
            outside.read_bytes()
        ).hexdigest()
        inventory_sources["run_history"]["sha256"] = hashlib.sha256(
            outside.read_bytes()
        ).hexdigest()

    payload = processed_verifier.build_payload(
        [],
        [],
        map_payload,
        inventory_payload,
    )

    assert payload["status"] == "FAILED"
    source_check = next(
        check for check in payload["checks"] if check["name"] == "source_hash_lineage"
    )
    assert source_check["ok"] is False
