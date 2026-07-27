#!/usr/bin/env python3
"""執行 statistical-family trust boundary 的四個 bounded canary。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.sealed_oos import build_regime_episode_split  # noqa: E402
from scripts import run_autonomous_research as research  # noqa: E402


CONTRACT_PATH = PROJECT_ROOT / "config" / "regime_research_contract.json"
MATRIX_RUNNER = PROJECT_ROOT / "scripts" / "run_backtest_strategy_matrix.py"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "docs"
    / "evidence"
    / "REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01"
    / "canary-receipts.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run regime statistical family canaries")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--real-data-root", default=str(PROJECT_ROOT))
    parser.add_argument("--max-real-ranking-files", type=int, default=3)
    return parser.parse_args()


def canonical_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def run_command(command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    monotonic_started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    return {
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": round(time.monotonic() - monotonic_started, 6),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def synthetic_fixture(root: Path) -> dict[str, Any]:
    rankings_dir = root / "rankings"
    rankings_dir.mkdir(parents=True, exist_ok=True)
    history_rows: list[dict[str, Any]] = []
    price_rows: list[dict[str, Any]] = []
    cursor = date(2025, 1, 2)
    price = 100.0
    for episode_index in range(10):
        for day_index in range(15):
            trade_date = cursor.isoformat()
            history_rows.append(
                {
                    "trade_date": trade_date,
                    "as_of_date": trade_date,
                    "base_regime": "BROAD_RISK_ON",
                    "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
                    "is_transition": False,
                }
            )
            price_rows.append(
                {
                    "stock_id": "2330",
                    "trade_date": trade_date,
                    "open": price,
                    "high": price * 1.02,
                    "low": price * 0.995,
                    "close": price * 1.01,
                }
            )
            if day_index == 0:
                (rankings_dir / f"ranking_{trade_date}.csv").write_text(
                    "stock_id,stock_name,suggested_weight\n2330,synthetic,0.2\n",
                    encoding="utf-8",
                )
            price *= 1.01
            cursor += timedelta(days=1)
        transition_date = cursor.isoformat()
        history_rows.append(
            {
                "trade_date": transition_date,
                "as_of_date": transition_date,
                "base_regime": "BROAD_RISK_ON",
                "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
                "is_transition": True,
            }
        )
        price_rows.append(
            {
                "stock_id": "2330",
                "trade_date": transition_date,
                "open": price,
                "high": price * 1.01,
                "low": price * 0.995,
                "close": price,
            }
        )
        cursor += timedelta(days=1)
    history_path = root / "history.json"
    features_path = root / "features.parquet"
    write_json(history_path, {"rows": history_rows})
    pd.DataFrame(price_rows).to_parquet(features_path, index=False)
    episodes = research.build_regime_episodes(history_rows)
    split = build_regime_episode_split(
        episodes,
        horizon=10,
        min_development_episodes=2,
        validation_episodes=1,
        sealed_episodes=1,
        min_embargo_trade_days=10,
    )
    return {
        "rankings_dir": rankings_dir,
        "history_path": history_path,
        "features_path": features_path,
        "history_rows": history_rows,
        "split": split,
        "base_regime": "BROAD_RISK_ON",
        "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
    }


def issue_registration(
    *,
    root: Path,
    name: str,
    contract: dict[str, Any],
    history_rows: list[dict[str, Any]],
    split: Any,
    tested_combinations: list[dict[str, Any]],
    partition_id: str,
    correction_family_ids: list[str],
    correction_scope: str,
) -> tuple[Path, Path, dict[str, Any]]:
    authority = research.statistical_family_contract(contract)
    tested_ids = sorted(research.canonical_json_hash(row) for row in tested_combinations)
    correction_ids = sorted(str(item) for item in correction_family_ids)
    correction_family_id = research.canonical_json_hash(correction_ids)
    split_payload = {
        "metadata": split.metadata,
        "development": split.development,
        "validation": split.validation,
        "embargo": split.embargo,
        "sealed": split.sealed,
    }
    split_ids = {
        role: list(split.metadata[f"{role}_episode_ids"])
        for role in ("development", "validation", "embargo", "sealed")
    }
    sealed_trade_dates = [
        str(trade_date)
        for episode in split.sealed
        for trade_date in episode["trade_dates"]
    ]
    registration = research.build_experiment_pre_registration(
        {
            "experiment_label": name,
            "research_question": f"{name} statistical-family canary",
            "baseline_id": "canary-baseline",
            "regime_id": split.metadata["regime_id"],
            "dataset_hash": research.canonical_json_hash(history_rows),
            "split_id": split.metadata["split_id"],
            "split_artifact_hash": research.canonical_json_hash(split_payload),
            "episode_split_ids_hash": research.canonical_json_hash(split_ids),
            "parameter_space_hash": authority["parameter_space_hash"],
            "contract_hash": authority["contract_hash"],
            "global_combination_ids": authority["global_combination_ids"],
            "global_combination_ids_hash": authority["global_combination_ids_hash"],
            "global_family_id": authority["global_family_id"],
            "global_family_size": authority["global_family_size"],
            "tested_combination_ids": tested_ids,
            "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
            "correction_family_combination_ids": correction_ids,
            "correction_family_id": correction_family_id,
            "correction_family_size": len(correction_ids),
            "partition_policy": {
                "policy_id": authority["partition_policy_id"],
                "partition_id": partition_id,
                "correction_scope": correction_scope,
                "parameter_space_hash": authority["parameter_space_hash"],
                "tested_combination_count": len(tested_ids),
                "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
                "correction_family_id": correction_family_id,
                "correction_family_size": len(correction_ids),
            },
            "metric_policy_hash": research.canonical_json_hash(
                contract["multiple_testing_policy"]
            ),
            "development_episode_ids": split_ids["development"],
            "validation_episode_ids": split_ids["validation"],
            "embargo_episode_ids": split_ids["embargo"],
            "sealed_episode_ids": split_ids["sealed"],
            "sealed_trade_dates": sealed_trade_dates,
        }
    )
    registry_path = root / f"{name}-registry.jsonl"
    registered = research.append_experiment_registry(registry_path, registration)
    if not registered["ok"]:
        raise RuntimeError(f"canary registration failed: {registered}")
    registration = {
        **registration,
        "registry_record_hash": registered["registry_record_hash"],
    }
    registration_path = root / f"{name}-registration.json"
    write_json(registration_path, registration)
    return registration_path, registry_path, registration


def matrix_command(
    *,
    fixture: dict[str, Any],
    registration_path: Path,
    registry_path: Path,
    output_path: Path,
    horizons: str,
    stop_loss_pcts: str,
    take_profit_pcts: str,
    max_group_exposures: str,
    max_ranking_files: int,
) -> list[str]:
    return [
        sys.executable,
        str(MATRIX_RUNNER),
        "--rankings-dir",
        str(fixture["rankings_dir"]),
        "--features",
        str(fixture["features_path"]),
        "--max-ranking-files",
        str(max_ranking_files),
        "--horizons",
        horizons,
        "--stop-loss-pcts",
        stop_loss_pcts,
        "--take-profit-pcts",
        take_profit_pcts,
        "--max-group-exposures",
        max_group_exposures,
        "--require-exact-regime",
        "--market-regime-history",
        str(fixture["history_path"]),
        "--base-regime",
        str(fixture["base_regime"]),
        "--family-tags",
        ",".join(fixture["family_tags"]),
        "--allowed-episode-ids",
        ",".join(fixture["split"].metadata["development_episode_ids"]),
        "--pre-registration",
        str(registration_path),
        "--experiment-registry",
        str(registry_path),
        "--output",
        str(output_path),
    ]


def matrix_receipt(output_path: Path, execution: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
    raw_gate = (payload.get("summary") or {}).get("statistical_gate") or {}
    insufficient = raw_gate.get("insufficient_units_by_combination") or {}
    gate = {
        key: value
        for key, value in raw_gate.items()
        if key != "insufficient_units_by_combination"
    }
    if insufficient:
        actual_counts = [int(row.get("actual") or 0) for row in insufficient.values()]
        gate["insufficient_unit_combination_count"] = len(insufficient)
        gate["actual_statistical_unit_count_min"] = min(actual_counts)
        gate["actual_statistical_unit_count_max"] = max(actual_counts)
    return {
        "execution": execution,
        "output_sha256": canonical_hash(output_path) if output_path.exists() else None,
        "scenario_count": (payload.get("summary") or {}).get("scenario_count"),
        "round_decision": (payload.get("summary") or {}).get("round_decision"),
        "statistical_gate": gate,
        "input_contract_hash": (payload.get("inputs") or {}).get("contract_hash"),
        "input_registry_record_hash": (payload.get("inputs") or {}).get(
            "registry_record_hash"
        ),
    }


def run_synthetic_canaries(
    root: Path,
    artifact_dir: Path,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = synthetic_fixture(root)
    authority = research.statistical_family_contract(contract)
    local_combinations = research.validation_profile_combinations(
        "3,5,10", "none", "none", "none"
    )
    local_ids = sorted(research.canonical_json_hash(row) for row in local_combinations)
    local_registration, local_registry, local_payload = issue_registration(
        root=root,
        name="canary-a-local-three",
        contract=contract,
        history_rows=fixture["history_rows"],
        split=fixture["split"],
        tested_combinations=local_combinations,
        partition_id="forged-local-three",
        correction_family_ids=local_ids,
        correction_scope="local_profile",
    )
    local_output = artifact_dir / "canary-a-local-three-matrix.json"
    local_execution = run_command(
        matrix_command(
            fixture=fixture,
            registration_path=local_registration,
            registry_path=local_registry,
            output_path=local_output,
            horizons="3,5,10",
            stop_loss_pcts="none",
            take_profit_pcts="none",
            max_group_exposures="none",
            max_ranking_files=6,
        )
    )
    local_receipt = matrix_receipt(local_output, local_execution)
    local_gate = local_receipt["statistical_gate"]
    local_receipt.update(
        {
            "status": (
                "PASS"
                if local_execution["returncode"] == 0
                and not local_gate.get("ok")
                and not local_gate.get("evidence_complete")
                and local_gate.get("family_validation_reason") == "INVALID_CORRECTION_FAMILY"
                else "FAIL"
            ),
            "claimed_family_size": local_payload["correction_family_size"],
            "claimed_corrected_alpha": 0.05 / local_payload["correction_family_size"],
        }
    )

    standard_profile = next(
        row for row in research.VALIDATION_PROFILES if row["name"] == "standard"
    )
    standard_combinations = research.validation_profile_combinations(
        standard_profile["horizons"],
        standard_profile["stop_loss_pcts"],
        standard_profile["take_profit_pcts"],
        standard_profile["max_group_exposures"],
    )
    standard_registration, standard_registry, standard_payload = issue_registration(
        root=root,
        name="canary-b-standard",
        contract=contract,
        history_rows=fixture["history_rows"],
        split=fixture["split"],
        tested_combinations=standard_combinations,
        partition_id="standard",
        correction_family_ids=authority["global_combination_ids"],
        correction_scope="global_parameter_universe",
    )
    run_receipts = {}
    for variant in ("baseline", "candidate"):
        output_path = artifact_dir / f"canary-b-{variant}-matrix.json"
        execution = run_command(
            matrix_command(
                fixture=fixture,
                registration_path=standard_registration,
                registry_path=standard_registry,
                output_path=output_path,
                horizons=standard_profile["horizons"],
                stop_loss_pcts=standard_profile["stop_loss_pcts"],
                take_profit_pcts=standard_profile["take_profit_pcts"],
                max_group_exposures=standard_profile["max_group_exposures"],
                max_ranking_files=6,
            )
        )
        run_receipts[variant] = matrix_receipt(output_path, execution)
    baseline_gate = run_receipts["baseline"]["statistical_gate"]
    candidate_gate = run_receipts["candidate"]["statistical_gate"]
    standard_receipt = {
        "status": (
            "PASS"
            if all(row["execution"]["returncode"] == 0 for row in run_receipts.values())
            and all(row["scenario_count"] == 81 for row in run_receipts.values())
            and baseline_gate.get("family_validation_reason") == "EXPECTED_FAMILY_VALID"
            and candidate_gate.get("family_validation_reason") == "EXPECTED_FAMILY_VALID"
            and baseline_gate.get("correction_family_size") == 720
            and candidate_gate.get("correction_family_size") == 720
            and baseline_gate.get("corrected_alpha") == authority["corrected_alpha"]
            and candidate_gate.get("corrected_alpha") == authority["corrected_alpha"]
            else "FAIL"
        ),
        "tested_combination_count": len(standard_payload["tested_combination_ids"]),
        "global_family_size": standard_payload["global_family_size"],
        "corrected_alpha": authority["corrected_alpha"],
        "shared_experiment_id": standard_payload["experiment_id"],
        "shared_registry_record_hash": standard_payload["registry_record_hash"],
        "runs": run_receipts,
    }

    forged_split_ids = {
        "development": list(fixture["split"].metadata["development_episode_ids"]),
        "validation": ["sha256:forged-validation"],
        "embargo": ["sha256:forged-embargo"],
        "sealed": ["sha256:forged-sealed"],
    }
    forged_values = {
        key: value
        for key, value in standard_payload.items()
        if key not in {"experiment_id", "registry_record_hash"}
    }
    forged_values.update(
        {
            "dataset_hash": "sha256:forged-runtime-lineage",
            "split_id": "sha256:forged-split",
            "split_artifact_hash": "sha256:forged-split-artifact",
            "development_episode_ids": forged_split_ids["development"],
            "validation_episode_ids": forged_split_ids["validation"],
            "embargo_episode_ids": forged_split_ids["embargo"],
            "sealed_episode_ids": forged_split_ids["sealed"],
            "episode_split_ids_hash": research.canonical_json_hash(forged_split_ids),
        }
    )
    forged_registration = research.build_experiment_pre_registration(forged_values)
    forged_registry_path = root / "forged-lineage-registry.jsonl"
    forged_registered = research.append_experiment_registry(
        forged_registry_path,
        forged_registration,
    )
    if not forged_registered["ok"]:
        raise RuntimeError(f"forged-lineage registration failed: {forged_registered}")
    forged_registration = {
        **forged_registration,
        "registry_record_hash": forged_registered["registry_record_hash"],
    }
    forged_registration_path = root / "forged-lineage-registration.json"
    write_json(forged_registration_path, forged_registration)
    forged_output_path = artifact_dir / "forged-lineage-public-matrix.json"
    forged_execution = run_command(
        matrix_command(
            fixture=fixture,
            registration_path=forged_registration_path,
            registry_path=forged_registry_path,
            output_path=forged_output_path,
            horizons=standard_profile["horizons"],
            stop_loss_pcts=standard_profile["stop_loss_pcts"],
            take_profit_pcts=standard_profile["take_profit_pcts"],
            max_group_exposures=standard_profile["max_group_exposures"],
            max_ranking_files=6,
        )
    )
    forged_receipt = matrix_receipt(forged_output_path, forged_execution)
    forged_gate = forged_receipt["statistical_gate"]
    forged_receipt.update(
        {
            "status": (
                "PASS"
                if forged_execution["returncode"] == 0
                and forged_receipt["scenario_count"] == 81
                and not forged_gate.get("ok")
                and not forged_gate.get("evidence_complete")
                and forged_gate.get("family_validation_reason")
                == "DATASET_HASH_MISMATCH"
                else "FAIL"
            ),
            "registration_dataset_hash": forged_registration["dataset_hash"],
            "runtime_dataset_hash": research.canonical_json_hash(
                fixture["history_rows"]
            ),
            "registration_split_id": forged_registration["split_id"],
            "runtime_split_id": fixture["split"].metadata["split_id"],
            "registration_episode_split_ids_hash": forged_registration[
                "episode_split_ids_hash"
            ],
        }
    )
    return local_receipt, standard_receipt, forged_receipt


def safe_real_rankings(
    *,
    rankings_dir: Path,
    development: list[dict[str, Any]],
    horizon: int,
    limit: int,
) -> list[Path]:
    available = {path.name: path for path in rankings_dir.glob("ranking_*.csv")}
    selected: list[Path] = []
    for episode in development:
        dates = [str(item) for item in episode["trade_dates"]]
        safe_dates = dates[: max(0, len(dates) - horizon)]
        candidates = [
            available[f"ranking_{trade_date}.csv"]
            for trade_date in safe_dates
            if f"ranking_{trade_date}.csv" in available
        ]
        if candidates:
            selected.append(candidates[-1])
        if len(selected) >= limit:
            break
    return selected


def real_feature_subset(
    *,
    source: Path,
    ranking_paths: list[Path],
    development: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    stock_ids: set[str] = set()
    for path in ranking_paths:
        frame = pd.read_csv(path, dtype={"stock_id": str}, nrows=10)
        stock_ids.update(frame["stock_id"].astype(str).str.zfill(4))
    allowed_dates = {
        str(trade_date)
        for episode in development
        for trade_date in episode["trade_dates"]
    }
    try:
        frame = pd.read_parquet(
            source,
            columns=["stock_id", "trade_date", "open", "high", "low", "close"],
            filters=[("stock_id", "in", sorted(stock_ids))],
        )
    except Exception as exc:
        if "trade_date" not in str(exc):
            raise
        frame = pd.read_parquet(
            source,
            columns=["stock_id", "date", "open", "high", "low", "close"],
            filters=[("stock_id", "in", sorted(stock_ids))],
        ).rename(columns={"date": "trade_date"})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    date_text = pd.to_datetime(frame["trade_date"]).dt.date.astype(str)
    frame = frame[
        frame["stock_id"].isin(stock_ids) & date_text.isin(allowed_dates)
    ].copy()
    frame.to_parquet(output, index=False)
    return {
        "stock_count": len(stock_ids),
        "row_count": len(frame),
        "subset_sha256": canonical_hash(output),
    }


def run_available_data_canary(
    *,
    root: Path,
    artifact_dir: Path,
    data_root: Path,
    contract: dict[str, Any],
    max_ranking_files: int,
) -> dict[str, Any]:
    rankings_source = (
        data_root
        / "artifacts"
        / "backtest"
        / "historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15"
    )
    features_source = data_root / "data" / "clean" / "features.parquet"
    industry_map = data_root / "data" / "reference" / "stock_industry_map.csv"
    required_paths = [rankings_source, features_source]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return {
            "status": "BLOCKED",
            "reason_code": "REAL_DATA_INPUT_MISSING",
            "missing_count": len(missing),
        }
    real_root = root / "real-data"
    real_root.mkdir(parents=True, exist_ok=True)
    history_path = real_root / "market-regime-history.json"
    builder_command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "build_market_regime_history.py"),
        "--features",
        str(features_source),
        "--start-date",
        "2023-11-21",
        "--end-date",
        "2026-05-15",
        "--output",
        str(history_path),
    ]
    if industry_map.exists():
        builder_command.extend(["--industry-map", str(industry_map)])
    builder_execution = run_command(builder_command)
    if builder_execution["returncode"] != 0 or not history_path.exists():
        return {
            "status": "BLOCKED",
            "reason_code": "AS_OF_HISTORY_REBUILD_FAILED",
            "history_builder": builder_execution,
        }
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history_rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    episodes = research.build_regime_episodes(history_rows)
    by_regime: dict[str, list[dict[str, Any]]] = {}
    for episode in episodes:
        by_regime.setdefault(str(episode["regime_id"]), []).append(episode)
    split = None
    exact_regime = ""
    for regime_id, regime_episodes in sorted(
        by_regime.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        try:
            candidate_split = build_regime_episode_split(
                regime_episodes,
                horizon=10,
                min_development_episodes=2,
                validation_episodes=1,
                sealed_episodes=1,
                min_embargo_trade_days=10,
            )
        except ValueError:
            continue
        candidates = safe_real_rankings(
            rankings_dir=rankings_source,
            development=candidate_split.development,
            horizon=10,
            limit=max_ranking_files,
        )
        if candidates:
            split = candidate_split
            exact_regime = regime_id
            ranking_paths = candidates
            break
    if split is None:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason_code": "NO_REGIME_WITH_SPLIT_AND_SAFE_RANKING",
            "episode_counts": dict(Counter(episode["regime_id"] for episode in episodes)),
        }

    rankings_dir = real_root / "rankings"
    rankings_dir.mkdir(parents=True, exist_ok=True)
    copied_rankings = []
    for path in ranking_paths:
        target = rankings_dir / path.name
        shutil.copy2(path, target)
        copied_rankings.append(target)
    features_path = real_root / "features-subset.parquet"
    subset = real_feature_subset(
        source=features_source,
        ranking_paths=ranking_paths,
        development=split.development,
        output=features_path,
    )
    fixture = {
        "rankings_dir": rankings_dir,
        "features_path": features_path,
        "history_path": history_path,
        "history_rows": history_rows,
        "split": split,
        "base_regime": exact_regime.split("|", 1)[0],
        "family_tags": [
            item for item in exact_regime.split("|", 1)[1].split("+") if item
        ],
    }
    profile = next(row for row in research.VALIDATION_PROFILES if row["name"] == "standard")
    combinations = research.validation_profile_combinations(
        profile["horizons"],
        profile["stop_loss_pcts"],
        profile["take_profit_pcts"],
        profile["max_group_exposures"],
    )
    authority = research.statistical_family_contract(contract)
    registration_path, registry_path, registration = issue_registration(
        root=real_root,
        name="canary-d-available-data",
        contract=contract,
        history_rows=history_rows,
        split=split,
        tested_combinations=combinations,
        partition_id="standard",
        correction_family_ids=authority["global_combination_ids"],
        correction_scope="global_parameter_universe",
    )
    coarse = research.transition_experiment_registry(
        registry_path,
        experiment_id=registration["experiment_id"],
        target_state="COARSE_SCREEN",
        evidence_path="canary-d-episode-split",
    )
    output_path = artifact_dir / "canary-d-available-data-matrix.json"
    execution = run_command(
        matrix_command(
            fixture=fixture,
            registration_path=registration_path,
            registry_path=registry_path,
            output_path=output_path,
            horizons=profile["horizons"],
            stop_loss_pcts=profile["stop_loss_pcts"],
            take_profit_pcts=profile["take_profit_pcts"],
            max_group_exposures=profile["max_group_exposures"],
            max_ranking_files=max_ranking_files,
        )
    )
    matrix = matrix_receipt(output_path, execution)
    gate = matrix["statistical_gate"]
    if execution["returncode"] != 0:
        terminal = "BLOCKED"
    elif not gate.get("evidence_complete"):
        terminal = "INSUFFICIENT_EVIDENCE"
    elif gate.get("eligible_ids"):
        terminal = "SAME_REGIME_VALIDATION"
    else:
        terminal = "NO_STRATEGY"
    terminal_transition = research.transition_experiment_registry(
        registry_path,
        experiment_id=registration["experiment_id"],
        target_state=terminal,
        evidence_path="canary-d-available-data-matrix",
    )
    trace = [
        json.loads(line)
        for line in registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actual_units = max(
        [int(row.get("statistical_unit_count") or 0) for row in json.loads(output_path.read_text(encoding="utf-8")).get("scenarios", [])]
        or [0]
    ) if output_path.exists() else 0
    bonferroni_min_units = math.ceil(
        math.log2(authority["global_family_size"] / authority["familywise_alpha"])
    )
    episode_status = research.closed_mode_episode_evidence_status(
        exact_regime=exact_regime,
        available_episode_count=len(by_regime[exact_regime]),
        contract=contract,
    )
    return {
        "status": (
            "PASS"
            if coarse["ok"]
            and terminal_transition["ok"]
            and execution["returncode"] == 0
            and terminal in {"INSUFFICIENT_EVIDENCE", "NO_STRATEGY", "SAME_REGIME_VALIDATION"}
            else "FAIL"
        ),
        "decision": terminal,
        "exact_regime": exact_regime,
        "available_episode_count": len(by_regime[exact_regime]),
        "episode_role_counts": {
            role: len(getattr(split, role))
            for role in ("development", "validation", "embargo", "sealed")
        },
        "episode_gaps": episode_status["episode_gaps"],
        "theoretical_minimum_split_episode_count": episode_status[
            "theoretical_minimum_episode_count"
        ],
        "bonferroni_min_all_positive_statistical_units": bonferroni_min_units,
        "actual_max_statistical_units": actual_units,
        "statistical_unit_gap": max(0, bonferroni_min_units - actual_units),
        "next_replay_condition": (
            None
            if actual_units >= bonferroni_min_units
            else f"至少累積 {bonferroni_min_units} 個獨立 exact-regime episode trades"
        ),
        "input_hashes": {
            "generated_as_of_history": canonical_hash(history_path),
            "features": canonical_hash(features_source),
            "industry_map": canonical_hash(industry_map) if industry_map.exists() else None,
            "rankings": {
                path.name: canonical_hash(path)
                for path in ranking_paths
            },
            "contract": authority["contract_hash"],
        },
        "bounded_input_counts": {
            "ranking_files": len(copied_rankings),
            **subset,
        },
        "history_builder": builder_execution,
        "matrix": matrix,
        "state_trace": [
            {
                "event_type": row.get("event_type"),
                "target_state": row.get("target_state"),
                "experiment_id": row.get("experiment_id"),
                "registry_record_hash": row.get("registry_record_hash"),
                "event_hash": row.get("event_hash"),
            }
            for row in trace
        ],
    }


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).expanduser().resolve()
    artifact_dir = output_path.parent / "canary-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    started = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="regime-family-canary-") as temp_dir:
        root = Path(temp_dir)
        canary_a, canary_b, forged_lineage = run_synthetic_canaries(
            root,
            artifact_dir,
            contract,
        )
        canary_d = run_available_data_canary(
            root=root,
            artifact_dir=artifact_dir,
            data_root=Path(args.real_data_root).expanduser().resolve(),
            contract=contract,
            max_ranking_files=max(1, args.max_real_ranking_files),
        )
    coverage = research.validation_profile_partition_coverage(contract)
    canary_c = {
        **coverage,
        "status": (
            "PASS"
            if coverage["status"] == "PARTITION_COVERAGE_INCOMPLETE"
            and coverage["global_family_size"] == 720
            and coverage["missing_count"] > 0
            else "FAIL"
        ),
        "coverage_status": coverage["status"],
    }
    receipts = {
        "schema_version": "regime-statistical-family-canary.v1",
        "started_at": started.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "contract_hash": research.canonical_json_hash(contract),
        "canary_a_trust_boundary": canary_a,
        "canary_b_public_cli_81_of_720": canary_b,
        "canary_c_partition_coverage": canary_c,
        "canary_d_available_data_closed_run": canary_d,
        "forged_lineage_public_attack": forged_lineage,
        "new_problems": [
            {
                "reason_code": "PARTITION_COVERAGE_INCOMPLETE",
                "missing_count": coverage["missing_count"],
                "detail": "現有 validation profiles 的 union 未覆蓋 720；不得宣稱完整搜尋。",
            },
            *(
                [
                    {
                        "reason_code": "AVAILABLE_DATA_STATISTICAL_UNIT_GAP",
                        "gap": canary_d.get("statistical_unit_gap"),
                        "detail": "bounded repo-data run 未達 0.05/720 的理論最少獨立單位。",
                    }
                ]
                if int(canary_d.get("statistical_unit_gap") or 0) > 0
                else []
            ),
        ],
    }
    write_json(output_path, receipts)
    passed = all(
        row.get("status") == "PASS"
        for row in (canary_a, canary_b, canary_c, canary_d, forged_lineage)
    )
    print(json.dumps({"status": "PASS" if passed else "FAIL", "output": str(output_path)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
