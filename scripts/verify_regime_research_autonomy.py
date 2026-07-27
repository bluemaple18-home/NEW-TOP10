#!/usr/bin/env python3
"""驗證 REGIME-RESEARCH-AUTONOMY-01 的封閉研究契約。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.sealed_oos import build_regime_episode_split  # noqa: E402
from scripts import run_autonomous_research as research  # noqa: E402


DEFAULT_CONTRACT = PROJECT_ROOT / "config" / "regime_research_contract.json"
EXPECTED_PRODUCTION_HASHES = {
    "models/latest_lgbm.pkl": "ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d",
    "models/baseline_stats.json": "c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7",
}
ALLOWED_EXACT_FILES = {
    "app/modeling/sealed_oos.py",
    "config/regime_research_contract.json",
    "docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md",
    "docs/architecture/MODEL_IMPROVEMENT_LOOP.md",
    "docs/tasks/2026-07-27_REGIME-RESEARCH-AUTONOMY-01_closed_regime_parameter_research.md",
    "scripts/build_market_regime_history.py",
    "scripts/compare_strategy_matrices.py",
    "scripts/run_autonomous_research.py",
    "scripts/run_backtest_strategy_matrix.py",
    "scripts/run_portfolio_replay.py",
    "scripts/verify_regime_research_autonomy.py",
    "tests/test_regime_research_autonomy.py",
    "docs/tasks/2026-07-27_REVIEW-REGIME-RESEARCH-AUTONOMY-01.md",
    "docs/tasks/2026-07-27_REPAIR-REGIME-RESEARCH-AUTONOMY-01-01.md",
    "docs/tasks/2026-07-27_REPAIR-REGIME-RESEARCH-AUTONOMY-01-02.md",
}
ALLOWED_PREFIXES = (
    "artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/",
    "docs/evidence/REGIME-RESEARCH-AUTONOMY-01/",
    "docs/evidence/REVIEW-REGIME-RESEARCH-AUTONOMY-01/",
    "docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-01/",
    "docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-02/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify closed regime research autonomy contract")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--base", default="7efda43641118f36b10261b4a04e0278bba941a2")
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument(
        "--output",
        default="artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/verifier_report.json",
    )
    return parser.parse_args()


def check(name: str, ok: bool, value: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "value": value}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_at_ref(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def experiment(experiment_id: str, sealed: list[str]) -> dict[str, Any]:
    trade_dates = [
        f"2026-02-{index + 1 + int(hashlib.sha256(item.encode('utf-8')).hexdigest()[:2], 16) % 20:02d}"
        for index, item in enumerate(sealed)
    ]
    trade_dates = sorted(set(trade_dates))
    return research.build_experiment_pre_registration(
        {
            "experiment_label": experiment_id,
            "research_question": "exact-match regime candidate 是否優於同盤勢 baseline？",
            "baseline_id": "baseline-v1",
            "regime_id": "BROAD_RISK_ON|BIG_BULL",
            "dataset_hash": "sha256:dataset",
            "split_id": "sha256:split",
            "parameter_space_hash": "sha256:space",
            "metric_policy_hash": "sha256:metrics",
            "sealed_episode_ids": sealed,
            "sealed_trade_dates": trade_dates,
        }
    )


def episode(index: int, regime_id: str = "BROAD_RISK_ON|BIG_BULL") -> dict[str, Any]:
    start = f"2026-01-{index * 3 + 1:02d}"
    dates = [f"2026-01-{index * 3 + offset:02d}" for offset in (1, 2, 3)]
    return {
        "episode_id": f"episode-{index}",
        "regime_id": regime_id,
        "start_date": start,
        "end_date": dates[-1],
        "trade_dates": dates,
    }


def allowed_change_paths(paths: list[str]) -> bool:
    return all(path in ALLOWED_EXACT_FILES or path.startswith(ALLOWED_PREFIXES) for path in paths)


def changed_paths(base: str, candidate: str) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{candidate}"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return sorted({line.strip() for line in diff.stdout.splitlines() if line.strip()})


def build_report(contract: dict[str, Any], *, base: str, candidate: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    universe = research.parameter_universe_summary(contract)
    universe_evidence = {key: value for key, value in universe.items() if key != "legal_combination_ids"}
    expected_count = int(contract["parameter_universe"]["expected_executable_legal_combination_count"])
    checks.append(
        check(
            "parameter_universe.positive",
            universe["legal_combination_count"] == expected_count,
            universe_evidence,
        )
    )
    drifted = json.loads(json.dumps(contract))
    drifted["parameter_universe"]["dimensions"][0]["allowed_values"].append(99)
    checks.append(
        check(
            "parameter_universe.synthetic_negative",
            research.parameter_universe_summary(drifted)["legal_combination_count"] != expected_count,
            "count drift rejected",
        )
    )

    exact = {"base_regime": "BROAD_RISK_ON", "family_tags": ["BIG_BULL"]}
    rows = [
        {"trade_date": "2026-01-01", "as_of_date": "2026-01-01", **exact},
        {
            "trade_date": "2026-01-02",
            "as_of_date": "2026-01-02",
            "base_regime": "BROAD_RISK_ON",
            "family_tags": [],
        },
        {"trade_date": "2026-01-03", "as_of_date": "2026-01-03", **exact, "is_transition": True},
        {"trade_date": "2026-01-04", "as_of_date": "2026-01-04", "base_regime": "UNKNOWN", "family_tags": []},
    ]
    prefix_identity = research.regime_identity_id(rows[0])
    future_extended_identity = research.regime_identity_id([*rows, {"trade_date": "2099-01-01", **exact}][0])
    as_of_positive = research.validate_as_of_regime_rows(rows)
    as_of_negative = research.validate_as_of_regime_rows([{**rows[0], "as_of_date": "2026-01-02"}])
    checks.append(
        check(
            "as_of_regime.positive",
            as_of_positive["ok"] and prefix_identity == future_extended_identity,
            {"validation": as_of_positive, "identity": prefix_identity},
        )
    )
    checks.append(
        check(
            "as_of_regime.synthetic_negative",
            not as_of_negative["ok"] and as_of_negative["violations"][0]["reason_code"] == "AS_OF_DATE_NOT_TRADE_DATE",
            as_of_negative,
        )
    )
    selected = research.select_exact_regime_rows(rows, exact)
    checks.append(check("exact_match.positive", [row["trade_date"] for row in selected] == ["2026-01-01"], selected))
    checks.append(
        check(
            "exact_match.synthetic_negative",
            all(row["family_tags"] == ["BIG_BULL"] and not row.get("is_transition") for row in selected),
            "family mismatch/transition/UNKNOWN excluded",
        )
    )

    episodes = [episode(index) for index in range(1, 8)]
    split = build_regime_episode_split(
        episodes,
        horizon=3,
        min_development_episodes=2,
        validation_episodes=1,
        sealed_episodes=1,
        min_embargo_trade_days=3,
    )
    split_ids = [
        *(row["episode_id"] for row in split.development),
        *(row["episode_id"] for row in split.validation),
        *(row["episode_id"] for row in split.embargo),
        *(row["episode_id"] for row in split.sealed),
    ]
    checks.append(
        check(
            "episode_split.positive",
            len(split_ids) == len(set(split_ids)) and split.metadata["embargo_covers_horizon"],
            split.metadata,
        )
    )
    try:
        build_regime_episode_split([*episodes[:-1], episode(8, "RISK_OFF|")], horizon=3)
        mixed_rejected = False
    except ValueError:
        mixed_rejected = True
    checks.append(check("episode_split.synthetic_negative", mixed_rejected, "mixed identity rejected"))

    first = experiment("exp-a", ["episode-7"])
    registration = research.validate_experiment_registration(first, [])
    checks.append(check("pre_registration.positive", registration["ok"], registration))
    tampered = research.validate_experiment_registration({**first, "research_question": "post-hoc changed"}, [])
    checks.append(
        check(
            "pre_registration.synthetic_negative",
            tampered["reason_code"] == "EXPERIMENT_ID_PAYLOAD_MISMATCH",
            tampered,
        )
    )
    fresh = research.validate_experiment_registration(experiment("exp-b", ["episode-8"]), [first])
    reused = research.validate_experiment_registration(experiment("exp-b", ["episode-7"]), [first])
    checks.append(check("sealed_reuse.positive", fresh["ok"], fresh))
    checks.append(check("sealed_reuse.synthetic_negative", reused["reason_code"] == "SEALED_DATASET_REUSE", reused))

    source_entry = experiment("exp-entry", ["episode-entry"])
    source_exit = experiment("exp-exit", ["episode-exit"])
    source_entry["registry_record_hash"] = research.canonical_json_hash(source_entry)
    source_exit["registry_record_hash"] = research.canonical_json_hash(source_exit)
    composed = research.build_experiment_pre_registration(
        {
            **{
                key: value
                for key, value in experiment("exp-composed", ["episode-9"]).items()
                if key != "experiment_id"
            },
            "component_source_experiment_ids": [
                source_entry["experiment_id"],
                source_exit["experiment_id"],
            ],
            "component_source_hashes": {
                source_entry["experiment_id"]: source_entry["registry_record_hash"],
                source_exit["experiment_id"]: source_exit["registry_record_hash"],
            },
            "fresh_composition_experiment": True,
        }
    )
    composition_ok = research.validate_experiment_registration(composed, [source_entry, source_exit])
    composition_bad = {**composed, "experiment_id": "exp-entry", "fresh_composition_experiment": False}
    checks.append(check("composition.positive", composition_ok["ok"], composition_ok))
    checks.append(
        check(
            "composition.synthetic_negative",
            research.validate_experiment_registration(composition_bad, [source_entry, source_exit])["reason_code"]
            == "CROSS_EXPERIMENT_COMPOSITION",
            "old experiment id rejected",
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "experiments.jsonl"
        funnel_candidate = experiment("exp-funnel", ["episode-10"])
        research.append_experiment_registry(registry_path, funnel_candidate)
        funnel_ok = research.transition_experiment_registry(
            registry_path,
            experiment_id=funnel_candidate["experiment_id"],
            target_state="COARSE_SCREEN",
            evidence_path="artifacts/coarse.json",
        )
        funnel_bad = research.transition_experiment_registry(
            registry_path,
            experiment_id=funnel_candidate["experiment_id"],
            target_state="SEALED_OOS",
            evidence_path="artifacts/sealed.json",
        )
    checks.append(check("funnel.positive", funnel_ok["reason_code"] == "TRANSITION_RECORDED", funnel_ok))
    checks.append(check("funnel.synthetic_negative", funnel_bad["reason_code"] == "ILLEGAL_STATE_TRANSITION", funnel_bad))

    coverage_records = [
        {"regime_id": "BROAD_RISK_ON|BIG_BULL", "combination_id": combo_id, "status": "REJECTED"}
        for combo_id in universe["legal_combination_ids"]
    ]
    closed = research.coverage_summary(universe, ["BROAD_RISK_ON|BIG_BULL"], coverage_records)
    repeated = research.coverage_summary(universe, ["BROAD_RISK_ON|BIG_BULL"], coverage_records)
    open_coverage = research.coverage_summary(universe, ["BROAD_RISK_ON|BIG_BULL"], coverage_records[:-1])
    checks.append(
        check(
            "coverage.positive",
            closed["regimes"][0]["coverage_closed"] and closed["coverage_hash"] == repeated["coverage_hash"],
            closed["regimes"][0],
        )
    )
    checks.append(check("coverage.synthetic_negative", not open_coverage["regimes"][0]["coverage_closed"], open_coverage["regimes"][0]))

    topic = {"regime_identity": exact}
    score_args = {
        "current_regime": exact,
        "coverage": {"evidence_gap": 0.5},
        "information_gain": 0.8,
        "product_value": 1.0,
        "feasibility": 0.75,
        "estimated_compute_cost": 2.0,
    }
    score_a = research.score_regime_research_topic(topic, **score_args)
    score_b = research.score_regime_research_topic(topic, **score_args)
    missing_identity = research.score_regime_research_topic({}, **score_args)
    checks.append(check("topic_score.positive", score_a == score_b and score_a["eligible"], score_a))
    checks.append(
        check(
            "topic_score.synthetic_negative",
            missing_identity["reason_code"] == "MISSING_TOPIC_REGIME_IDENTITY",
            missing_identity,
        )
    )

    robust_candidates = [
        {
            "combination_id": "robust",
            "p_value": 0.001,
            "robust_neighbor_lineage": ["neighbor-a", "neighbor-b", "neighbor-c"],
            "robust_neighbor_pass_count": 3,
            "drawdown_within_limit": True,
        },
        {
            "combination_id": "lucky-winner",
            "p_value": 0.02,
            "robust_neighbor_lineage": [],
            "robust_neighbor_pass_count": 0,
            "drawdown_within_limit": True,
        },
        {
            "combination_id": "neighbor-a",
            "p_value": 0.001,
            "robust_neighbor_lineage": [],
            "robust_neighbor_pass_count": 0,
            "drawdown_within_limit": True,
        },
        {
            "combination_id": "neighbor-b",
            "p_value": 0.001,
            "robust_neighbor_lineage": [],
            "robust_neighbor_pass_count": 0,
            "drawdown_within_limit": True,
        },
        {
            "combination_id": "neighbor-c",
            "p_value": 0.001,
            "robust_neighbor_lineage": [],
            "robust_neighbor_pass_count": 0,
            "drawdown_within_limit": True,
        },
    ]
    family_id = research.canonical_json_hash(
        sorted(row["combination_id"] for row in robust_candidates)
    )
    for row in robust_candidates:
        row["correction_family_id"] = family_id
        row["statistical_unit_policy"] = "independent_regime_episode_cluster.v1"
        row["statistical_unit_ids"] = ["episode-1"]
        row["statistical_unit_count"] = 1
        row["pseudo_replication_detected"] = False
    expected_family = {
        "tested_combination_ids": sorted(row["combination_id"] for row in robust_candidates),
        "tested_combination_ids_hash": research.canonical_json_hash(
            sorted(row["combination_id"] for row in robust_candidates)
        ),
        "correction_family_combination_ids": sorted(
            row["combination_id"] for row in robust_candidates
        ),
        "correction_family_id": family_id,
        "correction_family_size": len(robust_candidates),
        "partition_policy": {
            "policy_id": "verifier_complete_family.v1",
            "correction_scope": "global_parameter_universe",
            "tested_combination_ids_hash": research.canonical_json_hash(
                sorted(row["combination_id"] for row in robust_candidates)
            ),
            "correction_family_id": family_id,
            "correction_family_size": len(robust_candidates),
        },
        "registration_valid": True,
    }
    multiple = research.multiple_testing_gate(
        robust_candidates,
        expected_family=expected_family,
    )
    checks.append(check("multiple_testing.positive", multiple["eligible_ids"] == ["robust"], multiple))
    checks.append(check("multiple_testing.synthetic_negative", "lucky-winner" not in multiple["eligible_ids"], multiple))

    universal_base = {
        "universe_declared_complete": True,
        "coverage_closed": True,
        "high_value_regions_remaining": 0,
        "fixed_parameter_hash": "sha256:fixed",
        "fresh_sealed_oos_per_regime": True,
        "required_regime_ids": ["BROAD_RISK_ON|BIG_BULL", "RISK_OFF|"],
        "coverage_regime_ids": ["BROAD_RISK_ON|BIG_BULL", "RISK_OFF|"],
        "regime_results": [
            {
                "regime_id": "BROAD_RISK_ON|BIG_BULL",
                "sufficient_evidence": True,
                "passed": True,
                "parameter_hash": "sha256:fixed",
                "sealed_dataset_slice_hash": "sha256:sealed-bull",
                "independent_emergence": True,
                "transition_forward_shadow_passed": True,
            },
            {
                "regime_id": "RISK_OFF|",
                "sufficient_evidence": True,
                "passed": True,
                "parameter_hash": "sha256:fixed",
                "sealed_dataset_slice_hash": "sha256:sealed-risk-off",
                "independent_emergence": True,
                "transition_forward_shadow_passed": True,
            },
        ],
    }
    universal_contract = json.loads(json.dumps(contract))
    universal_required = [
        "BROAD_RISK_ON|BIG_BULL",
        "RISK_OFF|",
    ]
    universal_contract["parameter_universe"]["declared_complete"] = True
    universal_contract["parameter_universe"]["inventory_status"] = "COMPLETE"
    universal_contract["parameter_universe"]["blocked_dimensions"] = []
    universal_contract["taxonomy"]["universal_identity_policy"] = "explicit_legal_identity_set"
    universal_contract["taxonomy"]["legal_identity_rules"] = [
        "verifier synthetic contract 僅允許列舉的 exact identities",
    ]
    universal_contract["taxonomy"]["legal_universal_regime_ids"] = universal_required
    universal_contract["taxonomy"]["required_universal_regime_ids"] = universal_required
    universal_ok = research.validate_universal_candidate(
        universal_base,
        contract=universal_contract,
    )
    universal_bad = research.validate_universal_candidate(
        {
            **universal_base,
            "regime_results": [
                universal_base["regime_results"][0],
                {
                    **universal_base["regime_results"][1],
                    "passed": False,
                },
            ],
            "full_period_average_passed": True,
        },
        contract=universal_contract,
    )
    checks.append(check("universal_gate.positive", universal_ok["unlocked"], universal_ok))
    checks.append(check("universal_gate.synthetic_negative", universal_bad["reason_code"] == "WORST_REGIME_FAILED", universal_bad))

    paths = changed_paths(base, candidate)
    hashes = {path: sha256_at_ref(candidate, path) for path in EXPECTED_PRODUCTION_HASHES}
    production_unchanged = hashes == EXPECTED_PRODUCTION_HASHES and allowed_change_paths(paths)
    checks.append(check("production_no_change.positive", production_unchanged, {"paths": paths, "hashes": hashes}))
    checks.append(
        check(
            "production_no_change.synthetic_negative",
            not allowed_change_paths([*paths, "models/latest_lgbm.pkl"]),
            "synthetic production path rejected",
        )
    )

    failed = [row for row in checks if not row["ok"]]
    return {
        "schema_version": "regime-research-autonomy-verification.v1",
        "status": "OK" if not failed else "FAILED",
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "parameter_universe": universe_evidence,
        "base": base,
        "candidate": candidate,
        "production_change_paths": paths,
    }


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = PROJECT_ROOT / contract_path
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    report = build_report(contract, base=args.base, candidate=args.candidate)
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
