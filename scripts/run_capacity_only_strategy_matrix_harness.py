#!/usr/bin/env python3
"""Capacity-only strategy-matrix harness.

這個 harness 只建立量測 seam：
- 從 canonical formal family 讀取 expected IDs。
- 在 synthetic capacity fixture 上呼叫既有 strategy-matrix build path。
- 驗證 requested/executed canonical ID parity、資源欄位、I/O parity 與 cleanup。

它不產生 production/configured rankings，不修改正式 artifacts，不宣告研究有效性。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import resource
import shutil
import sys
import time
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research.parameter_catalog import (  # noqa: E402
    CANONICAL_EXECUTABLE_PARAMETER_ORDER,
    executable_parameter_dimensions,
)
from scripts import run_autonomous_research as research  # noqa: E402
from scripts import run_backtest_strategy_matrix as strategy_matrix  # noqa: E402


SCHEMA_VERSION = "capacity-only-strategy-matrix-harness.v1"
BOUNDARY_NOTE = (
    "capacity-only fixture validates harness mechanics; not research-valid workload or full-720 benchmark"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def relpath(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def manifest(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": relpath(path, root),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def manifest_hash(rows: list[dict[str, Any]]) -> str:
    return research.canonical_json_hash(rows)


def safe_path(path: Path) -> Path:
    return path.expanduser().resolve()


def ensure_safe_work_root(work_root: Path) -> Path:
    resolved = safe_path(work_root)
    project_root = PROJECT_ROOT.resolve()
    home = Path.home().resolve()
    broad_roots = {
        Path(resolved.anchor).resolve(),
        Path("/tmp").resolve(),
        Path("/private").resolve(),
        Path("/private/tmp").resolve(),
        Path("/Users").resolve(),
        home,
    }
    if resolved in broad_roots:
        raise ValueError(f"UNSAFE_BROAD_WORK_ROOT: {resolved}")
    if resolved == project_root or resolved.is_relative_to(project_root):
        raise ValueError(f"UNSAFE_REPO_WRITE_ROOT: {resolved}")
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError(f"WORK_ROOT_MUST_BE_EMPTY: {resolved}")
    return resolved


def ensure_output_inside_work_root(output: Path, work_root: Path) -> Path:
    resolved = safe_path(output)
    root = safe_path(work_root)
    if resolved == root:
        raise ValueError(f"OUTPUT_MUST_BE_FILE_INSIDE_WORK_ROOT: {resolved}")
    if not resolved.is_relative_to(root):
        raise ValueError(f"OUTPUT_OUTSIDE_WORK_ROOT: {resolved}")
    return resolved


def formal_family() -> dict[str, Any]:
    contract = research.load_json(PROJECT_ROOT / "config" / "regime_research_contract.json")
    combinations = research.parameter_combinations(contract)
    ids = [str(row["combination_id"]) for row in combinations]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    if duplicate_ids:
        raise ValueError(f"DUPLICATE_FORMAL_COMBINATION_IDS: {duplicate_ids[:3]}")
    authority = research.statistical_family_contract(contract)
    return {
        "expected_count": len(combinations),
        "combination_id_hash": research.canonical_json_hash(ids),
        "global_family_size": authority["global_family_size"],
        "global_combination_ids_hash": authority["global_combination_ids_hash"],
        "parameter_catalog_hash": authority["parameter_catalog_hash"],
        "contract_hash": authority["contract_hash"],
        "combinations": combinations,
        "by_id": {str(row["combination_id"]): row for row in combinations},
    }


def select_requested_scenarios(
    family: dict[str, Any],
    *,
    requested_ids: list[str] | None = None,
    max_scenarios: int | None = None,
    full_family: bool = False,
) -> list[dict[str, Any]]:
    selectors = sum(
        [
            bool(requested_ids),
            max_scenarios is not None,
            bool(full_family),
        ]
    )
    if selectors != 1:
        raise ValueError("EXACTLY_ONE_REQUEST_SELECTOR_REQUIRED")
    combinations = list(family["combinations"])
    by_id = dict(family["by_id"])
    if full_family:
        return combinations
    if max_scenarios is not None:
        if max_scenarios <= 0:
            raise ValueError("MAX_SCENARIOS_MUST_BE_POSITIVE")
        return combinations[:max_scenarios]
    assert requested_ids is not None
    duplicates = sorted({item for item in requested_ids if requested_ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"DUPLICATE_REQUESTED_COMBINATION_IDS: {duplicates[:3]}")
    unknown = sorted(set(requested_ids) - set(by_id))
    if unknown:
        raise ValueError(f"UNKNOWN_REQUESTED_COMBINATION_IDS: {unknown[:3]}")
    canonical_ids = [str(row["combination_id"]) for row in combinations]
    if len(requested_ids) != len(canonical_ids) or set(requested_ids) != set(canonical_ids):
        raise ValueError(
            "REQUESTED_IDS_NOT_FULL_CANONICAL_FAMILY: "
            f"expected={len(canonical_ids)} observed={len(requested_ids)}"
        )
    if requested_ids != canonical_ids:
        raise ValueError("REQUESTED_IDS_ORDER_MISMATCH")
    return [by_id[item] for item in requested_ids]


def scenario_values(selected: list[dict[str, Any]]) -> dict[str, list[Any]]:
    selected_values = {
        key: {row["parameters"][key] for row in selected}
        for key in CANONICAL_EXECUTABLE_PARAMETER_ORDER
    }
    ordered_values = {
        row["id"]: [value for value in row["allowed_values"] if value in selected_values[row["id"]]]
        for row in executable_parameter_dimensions()
    }
    expected_count = 1
    for values in ordered_values.values():
        expected_count *= len(values)
    if expected_count != len(selected):
        raise ValueError(
            "REQUESTED_SCENARIOS_NOT_RECTANGULAR_FOR_EXISTING_RUNNER: "
            f"requested={len(selected)} product={expected_count}"
        )
    return ordered_values


def csv_token(value: Any) -> str:
    return "none" if value is None else str(value)


def csv_values(values: list[Any]) -> str:
    return ",".join(csv_token(value) for value in values)


def scenario_id(parameters: dict[str, Any]) -> str:
    return research.canonical_json_hash(
        {
            key: parameters.get(key)
            for key in CANONICAL_EXECUTABLE_PARAMETER_ORDER
        }
    )


def validate_requested_executed_parity(
    *,
    family: dict[str, Any],
    requested_ids: list[str],
    executed_scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    requested_duplicates = sorted({item for item in requested_ids if requested_ids.count(item) > 1})
    if requested_duplicates:
        raise ValueError(f"DUPLICATE_REQUESTED_COMBINATION_IDS: {requested_duplicates[:3]}")
    known_ids = set(family["by_id"])
    unknown_requested = sorted(set(requested_ids) - known_ids)
    if unknown_requested:
        raise ValueError(f"UNKNOWN_REQUESTED_COMBINATION_IDS: {unknown_requested[:3]}")

    executed_ids = [scenario_id(row) for row in executed_scenarios]
    executed_duplicates = sorted({item for item in executed_ids if executed_ids.count(item) > 1})
    if executed_duplicates:
        raise ValueError(f"DUPLICATE_EXECUTED_COMBINATION_IDS: {executed_duplicates[:3]}")
    unknown_executed = sorted(set(executed_ids) - known_ids)
    if unknown_executed:
        raise ValueError(f"UNKNOWN_EXECUTED_COMBINATION_IDS: {unknown_executed[:3]}")

    missing = sorted(set(requested_ids) - set(executed_ids))
    extra = sorted(set(executed_ids) - set(requested_ids))
    if missing or extra or len(requested_ids) != len(executed_ids):
        raise ValueError(
            "REQUESTED_EXECUTED_MISMATCH: "
            f"missing={missing[:3]} extra={extra[:3]} requested={len(requested_ids)} executed={len(executed_ids)}"
        )
    return {
        "status": "PASS",
        "requested_executed_match": True,
        "requested_ids_hash": research.canonical_json_hash(sorted(requested_ids)),
        "executed_ids_hash": research.canonical_json_hash(sorted(executed_ids)),
        "id_count": len(executed_ids),
    }


def write_capacity_fixture(root: Path, *, top_n: int = 10, max_horizon: int = 20) -> dict[str, Any]:
    rankings_dir = root / "rankings"
    data_dir = root / "data"
    reference_dir = root / "reference"
    rankings_dir.mkdir(parents=True, exist_ok=False)
    data_dir.mkdir(parents=True, exist_ok=False)
    reference_dir.mkdir(parents=True, exist_ok=False)

    stock_ids = [f"9{index:03d}" for index in range(1, top_n + 1)]
    ranking_path = rankings_dir / "ranking_2026-01-02.csv"
    with ranking_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_id",
                "stock_name",
                "model_prob",
                "risk_adjusted_score",
                "suggested_weight",
                "max_position_weight",
                "gross_exposure",
            ],
        )
        writer.writeheader()
        for rank, stock_id in enumerate(stock_ids, start=1):
            writer.writerow(
                {
                    "stock_id": stock_id,
                    "stock_name": f"容量測試{rank}",
                    "model_prob": f"{0.8 - rank * 0.01:.4f}",
                    "risk_adjusted_score": f"{1.0 - rank * 0.01:.4f}",
                    "suggested_weight": "0.10",
                    "max_position_weight": "0.20",
                    "gross_exposure": "0.65",
                }
            )

    group_map_path = reference_dir / "stock_industry_map.csv"
    with group_map_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_id", "industry_name"])
        writer.writeheader()
        for rank, stock_id in enumerate(stock_ids, start=1):
            writer.writerow(
                {
                    "stock_id": stock_id,
                    "industry_name": "CAPACITY_A" if rank <= top_n // 2 else "CAPACITY_B",
                }
            )

    trade_days = pd.bdate_range("2026-01-02", periods=max_horizon + 3)
    rows = []
    for stock_index, stock_id in enumerate(stock_ids, start=1):
        base = 100.0 + stock_index
        for day_index, trade_date in enumerate(trade_days):
            open_price = base + day_index * 0.2
            rows.append(
                {
                    "stock_id": stock_id,
                    "trade_date": trade_date.date().isoformat(),
                    "open": round(open_price, 4),
                    "high": round(open_price * 1.02, 4),
                    "low": round(open_price * 0.98, 4),
                    "close": round(open_price * 1.005, 4),
                }
            )
    features_path = data_dir / "features.parquet"
    frame = pd.DataFrame(rows)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame.to_parquet(features_path, index=False)

    return {
        "purpose": "CAPACITY_ONLY",
        "research_evidence_status": "NOT_RESEARCH_EVIDENCE",
        "rankings_dir": str(rankings_dir),
        "ranking_file_count": 1,
        "features": str(features_path),
        "group_map": str(group_map_path),
        "top_n": top_n,
        "max_horizon": max_horizon,
        "stock_count": len(stock_ids),
        "trade_day_count": len(trade_days),
    }


def cleanup_fixture(fixture_root: Path, work_root: Path) -> bool:
    resolved_fixture = fixture_root.resolve()
    resolved_work_root = work_root.resolve()
    if resolved_fixture.name != "fixture" or resolved_fixture.parent != resolved_work_root:
        raise ValueError(f"UNSAFE_FIXTURE_CLEANUP_TARGET: {resolved_fixture}")
    if not resolved_fixture.exists():
        return True
    if not resolved_fixture.is_dir():
        raise ValueError(f"FIXTURE_CLEANUP_TARGET_NOT_DIRECTORY: {resolved_fixture}")
    shutil.rmtree(resolved_fixture)
    return not resolved_fixture.exists()


@contextmanager
def fixture_group_map_scope(group_map_path: Path):
    original = strategy_matrix.replay_args

    def replay_args_with_fixture_group_map(base: argparse.Namespace, scenario: dict[str, Any]) -> argparse.Namespace:
        args = original(base, scenario)
        args.group_map = str(group_map_path)
        return args

    strategy_matrix.replay_args = replay_args_with_fixture_group_map
    try:
        yield
    finally:
        strategy_matrix.replay_args = original


def build_strategy_matrix_args(
    *,
    fixture: dict[str, Any],
    values: dict[str, list[Any]],
    requested_ids: list[str],
) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=fixture["rankings_dir"],
        features=fixture["features"],
        max_ranking_files=None,
        top_n=fixture["top_n"],
        horizons=csv_values(values["horizon"]),
        stop_loss_pcts=csv_values(values["stop_loss_pct"]),
        take_profit_pcts=csv_values(values["take_profit_pct"]),
        max_group_exposures=csv_values(values["max_group_exposure"]),
        max_gross_exposure=0.65,
        max_position_weight=0.2,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        same_day_hit_priority="stop_loss",
        require_exact_regime=False,
        market_regime_history=None,
        base_regime=None,
        family_tags="",
        allowed_episode_ids=None,
        development_only=False,
        pre_registration=None,
        experiment_registry=None,
        output=None,
        research_run_id="capacity-only-harness",
        research_intent_id="BC-CP2-R3-CAPACITY-ADAPTER-01",
        research_variant_role=None,
        requested_trial_spec_ids=json.dumps(sorted(requested_ids)),
    )


def run_capacity_probe(
    *,
    work_root: Path,
    output: Path,
    requested_ids: list[str] | None = None,
    max_scenarios: int | None = None,
    full_family: bool = False,
) -> dict[str, Any]:
    root = ensure_safe_work_root(work_root)
    output_path = ensure_output_inside_work_root(output, root)
    if output_path.exists():
        raise ValueError(f"OUTPUT_ALREADY_EXISTS: {output_path}")
    family = formal_family()
    selected = select_requested_scenarios(
        family,
        requested_ids=requested_ids,
        max_scenarios=max_scenarios,
        full_family=full_family,
    )
    requested = [str(row["combination_id"]) for row in selected]
    values = scenario_values(selected)
    root.mkdir(parents=True, exist_ok=True)
    fixture_root = root / "fixture"
    if fixture_root.exists():
        raise ValueError(f"FIXTURE_ROOT_ALREADY_EXISTS: {fixture_root}")
    matrix_dir = root / "matrix"
    matrix_dir.mkdir(parents=True, exist_ok=True)
    matrix_json = matrix_dir / "strategy_matrix.json"
    matrix_md = matrix_json.with_suffix(".md")

    fixture: dict[str, Any] = {}
    pre_manifest: list[dict[str, Any]] = []
    post_manifest: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    cleanup_status = "PASS"
    fixture_removed = True
    started = time.monotonic()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    try:
        fixture = write_capacity_fixture(fixture_root)
        pre_manifest = manifest(fixture_root)
        args = build_strategy_matrix_args(
            fixture=fixture,
            values=values,
            requested_ids=requested,
        )
        with fixture_group_map_scope(Path(fixture["group_map"])):
            payload = strategy_matrix.build_payload(args)
        matrix_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        matrix_md.write_text(strategy_matrix.render_markdown(payload), encoding="utf-8")
        post_manifest = manifest(fixture_root)
    finally:
        usage_after = resource.getrusage(resource.RUSAGE_SELF)
        if fixture_root.exists():
            fixture_removed = cleanup_fixture(fixture_root, root)
        cleanup_status = "PASS" if fixture_removed else "FAILED"
    wall = time.monotonic() - started
    parity = validate_requested_executed_parity(
        family=family,
        requested_ids=requested,
        executed_scenarios=payload.get("scenarios", []),
    )

    output_sizes = {
        "matrix_json_bytes": matrix_json.stat().st_size if matrix_json.exists() else 0,
        "matrix_md_bytes": matrix_md.stat().st_size if matrix_md.exists() else 0,
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": pd.Timestamp.now(tz=timezone.utc).isoformat(),
        "boundary": {
            "purpose": "CAPACITY_ONLY",
            "research_evidence_status": "NOT_RESEARCH_EVIDENCE",
            "full_720_benchmark_status": "NOT_EXECUTED_BY_R3",
            "ranking_generation": False,
            "production_invocation": False,
            "repo_artifacts_write_allowed": False,
        },
        "formal_family": {
            key: value
            for key, value in family.items()
            if key not in {"combinations", "by_id"}
        },
        "requested": {
            "scenario_count": len(requested),
            "combination_ids_hash": research.canonical_json_hash(sorted(requested)),
            "manifest_order_policy": (
                "FULL_CANONICAL_FAMILY_ORDER_REQUIRED"
                if requested_ids is not None
                else "INTERNAL_BOUNDED_PREFIX_ONLY"
            ),
            "selector": (
                "full_family"
                if full_family
                else "max_scenarios"
                if max_scenarios is not None
                else "requested_ids"
            ),
        },
        "executed": {
            "scenario_count": int((payload.get("summary") or {}).get("scenario_count") or 0),
            "combination_ids_hash": parity["executed_ids_hash"],
            "matrix_schema_version": payload.get("schema_version"),
        },
        "parity": parity,
        "execution_order_boundary": (
            "strategy-matrix output is score-sorted; harness asserts requested/executed canonical set/hash parity, "
            "not execution order parity"
        ),
        "fixture": {
            key: value
            for key, value in fixture.items()
            if key
            in {
                "purpose",
                "research_evidence_status",
                "ranking_file_count",
                "top_n",
                "max_horizon",
                "stock_count",
                "trade_day_count",
            }
        },
        "metrics": {
            "wall_time_seconds": wall,
            "candidate_per_second": len(requested) / wall if wall > 0 else 0,
            "cpu_user_seconds": usage_after.ru_utime - usage_before.ru_utime,
            "cpu_system_seconds": usage_after.ru_stime - usage_before.ru_stime,
            "peak_rss": max(usage_before.ru_maxrss, usage_after.ru_maxrss),
            "inblock_delta": usage_after.ru_inblock - usage_before.ru_inblock,
            "oublock_delta": usage_after.ru_oublock - usage_before.ru_oublock,
        },
        "io": {
            "pre_manifest_hash": manifest_hash(pre_manifest),
            "post_manifest_hash": manifest_hash(post_manifest),
            "manifest_parity": "PASS" if pre_manifest == post_manifest else "FAIL",
            "fixture_file_count": len(pre_manifest),
            "output_sizes": output_sizes,
        },
        "cleanup": {
            "status": cleanup_status,
            "temp_fixture_removed": fixture_removed,
        },
        "outputs": {
            "receipt": str(output_path),
            "matrix_json": str(matrix_json),
            "matrix_md": str(matrix_md),
        },
        "non_extrapolation_boundary": BOUNDARY_NOTE,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return receipt


def parse_ids_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [line.strip() for line in text.splitlines() if line.strip()]
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("REQUESTED_IDS_FILE_MUST_BE_JSON_STRING_LIST_OR_LINE_LIST")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run capacity-only strategy matrix harness")
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--requested-ids-file", default=None)
    parser.add_argument("--max-scenarios", type=int, default=None)
    parser.add_argument("--full-family", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_ids = (
        parse_ids_file(Path(args.requested_ids_file).expanduser())
        if args.requested_ids_file
        else None
    )
    receipt = run_capacity_probe(
        work_root=Path(args.work_root),
        output=Path(args.output),
        requested_ids=requested_ids,
        max_scenarios=args.max_scenarios,
        full_family=bool(args.full_family),
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "output": receipt["outputs"]["receipt"],
                "scenario_count": receipt["executed"]["scenario_count"],
                "parity": receipt["parity"]["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
