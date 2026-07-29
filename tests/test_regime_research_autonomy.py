from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.modeling.sealed_oos import build_regime_episode_split
from scripts import build_market_regime_history as regime_builder
from scripts import run_autonomous_research as research
from scripts import run_backtest_strategy_matrix as matrix
from scripts import verify_regime_research_autonomy as verifier


EXACT = {"base_regime": "BROAD_RISK_ON", "family_tags": ["BIG_BULL", "HIGH_CHOPPY"]}


def test_regime_name_does_not_grant_eligibility_without_current_context() -> None:
    topic = {
        "topic_id": "strategy-matrix:shadow-rankings-regime-guard",
        "candidate_dir": "artifacts/backtest/shadow_rankings_regime_guard",
    }

    result = research.score_regime_research_topic(
        topic,
        current_regime=EXACT,
        coverage={"evidence_gap": 1.0},
        information_gain=1.0,
        product_value=1.0,
        feasibility=1.0,
        estimated_compute_cost=1.0,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "MISSING_TOPIC_REGIME_IDENTITY"


def test_exact_base_match_rejects_family_tag_mismatch() -> None:
    rows = [
        {"trade_date": "2026-01-02", **EXACT},
        {"trade_date": "2026-01-03", "base_regime": "BROAD_RISK_ON", "family_tags": ["BIG_BULL"]},
    ]

    selected = research.select_exact_regime_rows(rows, EXACT)

    assert [row["trade_date"] for row in selected] == ["2026-01-02"]


def test_transition_and_unknown_are_not_forced_into_nearest_regime() -> None:
    rows = [
        {"trade_date": "2026-01-02", **EXACT},
        {"trade_date": "2026-01-03", **EXACT, "is_transition": True},
        {"trade_date": "2026-01-04", "base_regime": "UNKNOWN", "family_tags": []},
    ]

    selected = research.select_exact_regime_rows(rows, EXACT)

    assert [row["trade_date"] for row in selected] == ["2026-01-02"]


def test_used_sealed_episode_cannot_be_reused_as_new_oos() -> None:
    first = _experiment_with_dates("exp-a", ["episode-3"], ["2026-01-05"])
    candidate = _experiment_with_dates("exp-b", ["episode-alias"], ["2026-01-05"])

    result = research.validate_experiment_registration(candidate, [first])

    assert result["ok"] is False
    assert result["reason_code"] == "SEALED_DATASET_REUSE"
    assert result["source_experiment_id"] == first["experiment_id"]


def test_cross_experiment_composition_requires_new_id_and_fresh_sealed_data() -> None:
    registry = [
        {"experiment_id": "exp-entry", "sealed_episode_ids": ["episode-3"]},
        {"experiment_id": "exp-exit", "sealed_episode_ids": ["episode-4"]},
    ]
    candidate = {
        "experiment_id": "exp-entry",
        "component_source_experiment_ids": ["exp-entry", "exp-exit"],
        "sealed_episode_ids": ["episode-4"],
    }

    result = research.validate_experiment_registration(candidate, registry)

    assert result["ok"] is False
    assert result["reason_code"] == "CROSS_EXPERIMENT_COMPOSITION"


def test_universal_gate_rejects_full_period_average_when_one_regime_fails() -> None:
    result = research.validate_universal_candidate(
        {
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
                {"regime_id": "RISK_OFF|", "sufficient_evidence": True, "passed": False},
            ],
            "full_period_average_passed": True,
        },
        contract=_universal_contract(),
    )

    assert result["unlocked"] is False
    assert result["reason_code"] == "WORST_REGIME_FAILED"


def _contract() -> dict:
    return json.loads((research.PROJECT_ROOT / "config/regime_research_contract.json").read_text(encoding="utf-8"))


def _universal_contract() -> dict:
    contract = _contract()
    required = [
        "BROAD_RISK_ON|BIG_BULL",
        "RISK_OFF|",
    ]
    contract["parameter_universe"]["declared_complete"] = True
    contract["parameter_universe"]["inventory_status"] = "COMPLETE"
    contract["parameter_universe"]["blocked_dimensions"] = []
    contract["taxonomy"]["universal_identity_policy"] = "explicit_legal_identity_set"
    contract["taxonomy"]["legal_identity_rules"] = [
        "此 synthetic contract 僅允許列舉的兩個 exact identities。",
    ]
    contract["taxonomy"]["legal_universal_regime_ids"] = required
    contract["taxonomy"]["required_universal_regime_ids"] = required
    return contract


def _universal_candidate(regime_ids: list[str]) -> dict:
    return {
        "universe_declared_complete": True,
        "coverage_closed": True,
        "high_value_regions_remaining": 0,
        "fixed_parameter_hash": "sha256:fixed",
        "fresh_sealed_oos_per_regime": True,
        "required_regime_ids": regime_ids,
        "coverage_regime_ids": regime_ids,
        "regime_results": [
            {
                "regime_id": regime_id,
                "sufficient_evidence": True,
                "passed": True,
                "parameter_hash": "sha256:fixed",
                "sealed_dataset_slice_hash": f"sha256:sealed-{index}",
                "independent_emergence": True,
                "transition_forward_shadow_passed": True,
            }
            for index, regime_id in enumerate(regime_ids)
        ],
    }


def _expected_family(
    combination_ids: list[str],
    *,
    correction_family_id: str | None = None,
    correction_family_size: int | None = None,
) -> dict:
    tested_ids = sorted(combination_ids)
    family_id = correction_family_id or research.canonical_json_hash(tested_ids)
    return {
        "tested_combination_ids": tested_ids,
        "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
        "correction_family_combination_ids": tested_ids,
        "correction_family_id": family_id,
        "correction_family_size": correction_family_size or len(tested_ids),
        "partition_policy": {
            "policy_id": "test_partition.v1",
            "correction_scope": "global_parameter_universe",
            "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
            "correction_family_id": family_id,
            "correction_family_size": correction_family_size or len(tested_ids),
        },
        "registration_valid": True,
    }


def _experiment(experiment_id: str, sealed: list[str]) -> dict:
    sealed_trade_dates = sorted(
        (
            date(2025, 1, 1)
            + timedelta(days=int(research.canonical_json_hash(item)[7:15], 16) % 300)
        ).isoformat()
        for item in sealed
    )
    return research.build_experiment_pre_registration(
        {
        "experiment_label": experiment_id,
        "research_question": "候選是否優於 exact-match baseline？",
        "baseline_id": "baseline-v1",
        "regime_id": "BROAD_RISK_ON|BIG_BULL",
        "dataset_hash": "sha256:dataset",
        "split_id": "sha256:split",
        "parameter_space_hash": "sha256:space",
        "metric_policy_hash": "sha256:metrics",
        "sealed_episode_ids": sealed,
        "sealed_trade_dates": sealed_trade_dates,
        }
    )


def _experiment_with_dates(experiment_id: str, sealed: list[str], trade_dates: list[str]) -> dict:
    return research.build_experiment_pre_registration(
        {
            "experiment_label": experiment_id,
            "research_question": "候選是否優於 exact-match baseline？",
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


def _episode(index: int, regime_id: str = "BROAD_RISK_ON|BIG_BULL") -> dict:
    return {
        "episode_id": f"episode-{index}",
        "regime_id": regime_id,
        "start_date": f"2026-01-{index * 3 + 1:02d}",
        "end_date": f"2026-01-{index * 3 + 3:02d}",
        "trade_dates": [f"2026-01-{index * 3 + offset:02d}" for offset in (1, 2, 3)],
    }


def _regime_row(day: str, label: str) -> regime_builder.RegimeRow:
    return regime_builder.RegimeRow(
        trade_date=day,
        regime_label=label,
        risk_tone="aggressive",
        equal_weight_return=0.01,
        value_weight_return=0.01,
        breadth_ma20=0.7,
        breadth_ma60=0.6,
        advance_ratio=0.7,
        breakout_ratio=0.1,
        breakdown_ratio=0.01,
        volume_spike_ratio=0.1,
        long_upper_shadow_ratio=0.01,
        avg_rsi=55.0,
        top_sector="semi",
        top_sector_value_share=0.7,
        top_strong_sector="semi",
        top_strong_sector_value_share=0.7,
        notes="fixture",
    )


def test_parameter_universe_inventory_is_deterministic_and_honest() -> None:
    summary_a = research.parameter_universe_summary(_contract())
    summary_b = research.parameter_universe_summary(_contract())

    assert summary_a == summary_b
    assert summary_a["legal_combination_count"] == 720
    assert len(set(summary_a["legal_combination_ids"])) == 720
    assert summary_a["declared_complete"] is False
    assert summary_a["inventory_status"] == "PARTIAL_BLOCKED_SOURCE_UNKNOWN"


def test_regime_builder_is_as_of_and_future_rows_do_not_change_prior_identity() -> None:
    prefix = [_regime_row("2026-01-02", "BROAD_RISK_ON"), _regime_row("2026-01-03", "BROAD_RISK_ON")]
    future = _regime_row("2026-01-04", "RISK_OFF")

    before = regime_builder.enrich_regime_contract_rows(prefix)
    after = regime_builder.enrich_regime_contract_rows([*prefix, future])

    assert before == after[: len(before)]
    assert all(row["as_of_date"] == row["trade_date"] for row in before)
    assert after[-1]["is_transition"] is True


def test_current_regime_context_fails_closed_without_as_of_date(tmp_path: Path) -> None:
    path = tmp_path / "regime.json"
    path.write_text(
        json.dumps({"rows": [{"trade_date": "2026-01-02", **EXACT}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="as_of"):
        research.current_regime_context(path, "2026-01-02")


@pytest.mark.parametrize(
    "row",
    [
        {
            "trade_date": "2026-01-02",
            "as_of_date": "2026-01-02",
            "base_regime": "UNKNOWN",
            "family_tags": [],
        },
        {
            "trade_date": "2026-01-02",
            "as_of_date": "2026-01-02",
            **EXACT,
            "is_transition": True,
        },
    ],
)
def test_current_regime_context_fails_closed_for_unknown_or_transition(
    tmp_path: Path,
    row: dict,
) -> None:
    path = tmp_path / "regime.json"
    path.write_text(json.dumps({"rows": [row]}), encoding="utf-8")

    with pytest.raises(ValueError, match="UNKNOWN/transition"):
        research.current_regime_context(path, "2026-01-02")


def test_episode_builder_and_split_keep_complete_episodes_disjoint() -> None:
    episodes = [_episode(index) for index in range(1, 8)]

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
    assert len(split_ids) == len(set(split_ids))
    assert split.metadata["embargo_covers_horizon"] is True

    with pytest.raises(ValueError, match="同一 exact-match"):
        build_regime_episode_split([*episodes[:-1], _episode(8, "RISK_OFF|")], horizon=3)


def test_episode_split_rejects_overlapping_trade_dates_across_alias_ids() -> None:
    episodes = [
        {
            "episode_id": f"episode-alias-{index}",
            "regime_id": "BROAD_RISK_ON|BIG_BULL",
            "start_date": "2026-01-05",
            "end_date": "2026-01-05",
            "trade_dates": ["2026-01-05"],
        }
        for index in range(5)
    ]

    with pytest.raises(ValueError, match="交易日"):
        build_regime_episode_split(
            episodes,
            horizon=1,
            min_development_episodes=2,
            validation_episodes=1,
            sealed_episodes=1,
            min_embargo_trade_days=1,
        )


def test_append_only_registry_preserves_history_and_rejects_reuse(tmp_path: Path) -> None:
    path = tmp_path / "experiments.jsonl"
    first = research.append_experiment_registry(path, _experiment("exp-a", ["sealed-a"]))
    second = research.append_experiment_registry(path, _experiment("exp-b", ["sealed-b"]))
    reused = research.append_experiment_registry(path, _experiment("exp-c", ["sealed-a"]))

    assert first["ok"] is True
    assert second["ok"] is True
    assert reused["reason_code"] == "SEALED_DATASET_REUSE"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_sealed_reuse_rejects_same_dates_hidden_behind_episode_aliases() -> None:
    first = _experiment_with_dates("exp-a", ["episode-alias-a"], ["2026-01-05", "2026-01-06"])
    candidate = _experiment_with_dates("exp-b", ["episode-alias-b"], ["2026-01-05", "2026-01-06"])

    result = research.validate_experiment_registration(candidate, [first])

    assert result["ok"] is False
    assert result["reason_code"] == "SEALED_DATASET_REUSE"


def test_stitching_rejects_unknown_component_source_and_untraceable_hash() -> None:
    first = _experiment_with_dates("exp-source", ["episode-a"], ["2026-01-05"])
    candidate = research.build_experiment_pre_registration(
        {
            "experiment_label": "exp-composed",
            "research_question": "組合 entry/exit 是否穩健？",
            "baseline_id": "baseline-v1",
            "regime_id": "BROAD_RISK_ON|BIG_BULL",
            "dataset_hash": "sha256:dataset",
            "split_id": "sha256:split",
            "parameter_space_hash": "sha256:space",
            "metric_policy_hash": "sha256:metrics",
            "sealed_episode_ids": ["episode-alias-new"],
            "sealed_trade_dates": ["2026-02-05"],
            "component_source_experiment_ids": [first["experiment_id"], "experiment:unknown"],
            "component_source_hashes": {
                first["experiment_id"]: "sha256:source-record",
                "experiment:unknown": "sha256:unknown",
            },
            "fresh_composition_experiment": True,
        }
    )

    result = research.validate_experiment_registration(candidate, [first])

    assert result["ok"] is False
    assert result["reason_code"] == "UNKNOWN_COMPONENT_SOURCE"


def test_experiment_id_is_derived_from_immutable_pre_registration_payload() -> None:
    candidate = _experiment("exp-a", ["sealed-a"])
    tampered = {**candidate, "research_question": "看完結果後改題目"}

    result = research.validate_experiment_registration(tampered, [])

    assert result["ok"] is False
    assert result["reason_code"] == "EXPERIMENT_ID_PAYLOAD_MISMATCH"


def test_funnel_transition_is_append_only_and_cannot_skip_stage(tmp_path: Path) -> None:
    path = tmp_path / "experiments.jsonl"
    candidate = _experiment("exp-funnel", ["sealed-a"])
    assert research.append_experiment_registry(path, candidate)["ok"] is True

    coarse = research.transition_experiment_registry(
        path,
        experiment_id=candidate["experiment_id"],
        target_state="COARSE_SCREEN",
        evidence_path="artifacts/coarse.json",
    )
    skipped = research.transition_experiment_registry(
        path,
        experiment_id=candidate["experiment_id"],
        target_state="SEALED_OOS",
        evidence_path="artifacts/sealed.json",
    )

    assert coarse["reason_code"] == "TRANSITION_RECORDED"
    assert skipped["reason_code"] == "ILLEGAL_STATE_TRANSITION"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_topic_score_is_reproducible_and_formula_is_auditable() -> None:
    kwargs = {
        "current_regime": EXACT,
        "coverage": {"evidence_gap": 0.5},
        "information_gain": 0.8,
        "product_value": 1.0,
        "feasibility": 0.75,
        "estimated_compute_cost": 2.0,
    }

    first = research.score_regime_research_topic({"regime_identity": EXACT}, **kwargs)
    second = research.score_regime_research_topic({"regime_identity": EXACT}, **kwargs)

    assert first == second
    assert first["priority"] == 0.15
    assert set(first["score_breakdown"]) == {
        "current_regime_relevance",
        "evidence_gap",
        "expected_information_gain",
        "product_value",
        "feasibility",
        "estimated_compute_cost",
    }


def test_closed_topic_explains_coverage_gap_and_search_space_reduction() -> None:
    topic = research.topic_for_dir(
        {"repo_path": "artifacts/backtest/candidate", "count": 12},
        baseline_dir=research.BASELINE_RANKINGS_DIR,
        ledger_candidates=[],
        external_signals=[],
        evidence_sources=[],
        current_regime=EXACT,
        coverage={"evidence_gap": 0.5, "pending_count": 360, "legal_combination_count": 720},
    )

    assert topic is not None
    assert topic.regime_identity == EXACT
    assert topic.score_breakdown["evidence_gap"] == 0.5
    assert topic.selection_rationale == {
        "why_now": "current exact-match regime is BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY",
        "coverage_gap": 0.5,
        "pending_combination_count": 360,
        "estimated_combinations_resolved_on_success_or_failure": 81,
        "selection_is_deterministic": True,
    }


def test_coverage_funnel_multiple_testing_and_no_strategy_are_fail_closed() -> None:
    universe = research.parameter_universe_summary(_contract())
    regime_id = "BROAD_RISK_ON|BIG_BULL"
    records = [
        {"regime_id": regime_id, "combination_id": combo_id, "status": "REJECTED"}
        for combo_id in universe["legal_combination_ids"]
    ]

    closed = research.coverage_summary(universe, [regime_id], records)
    open_summary = research.coverage_summary(universe, [regime_id], records[:-1])
    illegal_transition = research.validate_funnel_transition("REGISTERED", "SEALED_OOS", "evidence.json")
    missing_evidence = research.validate_funnel_transition("REGISTERED", "COARSE_SCREEN", None)
    gate_candidates = [
            {
                "combination_id": "robust",
                "p_value": 0.001,
                "robust_neighbor_lineage": ["neighbor-a", "neighbor-b"],
                "robust_neighbor_pass_count": 2,
                "drawdown_within_limit": True,
            },
            {
                "combination_id": "lucky",
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
        ]
    family_id = research.canonical_json_hash(
        sorted(row["combination_id"] for row in gate_candidates)
    )
    for row in gate_candidates:
        row["correction_family_id"] = family_id
        row["statistical_unit_policy"] = "independent_regime_episode_cluster.v1"
        row["statistical_unit_ids"] = ["episode-1"]
        row["statistical_unit_count"] = 1
        row["pseudo_replication_detected"] = False
    gate = research.multiple_testing_gate(
        gate_candidates,
        expected_family=_expected_family([row["combination_id"] for row in gate_candidates]),
    )

    assert closed["regimes"][0]["coverage_closed"] is True
    assert open_summary["regimes"][0]["coverage_closed"] is False
    assert illegal_transition["reason_code"] == "ILLEGAL_STATE_TRANSITION"
    assert missing_evidence["reason_code"] == "MISSING_TRANSITION_EVIDENCE"
    assert gate["eligible_ids"] == ["robust"]
    assert research.research_round_decision([], sufficient_evidence=True) == "NO_STRATEGY"
    assert research.research_round_decision([], sufficient_evidence=False) == "INSUFFICIENT_EVIDENCE"


def test_universal_gate_stays_locked_while_inventory_is_incomplete() -> None:
    result = research.validate_universal_candidate(
        {
            "universe_declared_complete": False,
            "coverage_closed": True,
            "high_value_regions_remaining": 0,
            "fixed_parameter_hash": "sha256:fixed",
            "regime_results": [{"regime_id": "RISK_OFF|", "sufficient_evidence": True, "passed": True}],
        },
        contract=_contract(),
    )

    assert result == {"unlocked": False, "reason_code": "PARAMETER_UNIVERSE_INCOMPLETE"}


def test_universal_gate_does_not_trust_candidate_completeness_claim() -> None:
    contract = _contract()
    required = contract["taxonomy"]["required_universal_regime_ids"]

    result = research.validate_universal_candidate(
        _universal_candidate(required),
        contract=contract,
    )

    assert result["unlocked"] is False
    assert result["reason_code"] == "PARAMETER_UNIVERSE_INCOMPLETE"


def test_universal_gate_requires_all_legal_tagged_exact_identities() -> None:
    contract = _contract()
    contract["parameter_universe"]["declared_complete"] = True
    contract["parameter_universe"]["inventory_status"] = "COMPLETE"
    contract["parameter_universe"]["blocked_dimensions"] = []
    contract["taxonomy"]["universal_identity_policy"] = "full_cartesian_product"
    base_only = [
        regime_id
        for regime_id in contract["taxonomy"]["required_universal_regime_ids"]
        if regime_id.endswith("|")
    ]

    result = research.validate_universal_candidate(
        _universal_candidate(base_only),
        contract=contract,
    )

    assert result["unlocked"] is False
    assert result["reason_code"] in {
        "REQUIRED_REGIME_POLICY_MISMATCH",
        "MISSING_REQUIRED_REGIMES",
    }
    assert "BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY" in result.get("missing_regime_ids", [])


def test_universal_gate_fails_closed_on_missing_fields_and_missing_regimes() -> None:
    result = research.validate_universal_candidate(
        {
            "coverage_closed": True,
            "high_value_regions_remaining": 0,
            "fixed_parameter_hash": "sha256:fixed",
            "required_regime_ids": ["BROAD_RISK_ON|BIG_BULL", "RISK_OFF|"],
            "coverage_regime_ids": ["BROAD_RISK_ON|BIG_BULL"],
            "regime_results": [
                {
                    "regime_id": "BROAD_RISK_ON|BIG_BULL",
                    "sufficient_evidence": True,
                    "passed": True,
                }
            ],
        },
        contract=_universal_contract(),
    )

    assert result["unlocked"] is False
    assert result["reason_code"] in {"MISSING_UNIVERSAL_FIELDS", "MISSING_REQUIRED_REGIMES"}


def test_strategy_matrix_filters_ranking_files_before_replay(tmp_path: Path) -> None:
    for day in ("2026-01-02", "2026-01-03", "2026-01-04"):
        (tmp_path / f"ranking_{day}.csv").write_text("stock_id\n2330\n", encoding="utf-8")

    with matrix.exact_ranking_file_scope({"2026-01-03"}):
        paths = matrix.run_portfolio_replay.run_backtest_replay.ranking_files(tmp_path, None)

    assert [path.name for path in paths] == ["ranking_2026-01-03.csv"]


def test_strategy_matrix_excludes_episode_tail_without_complete_holding_window() -> None:
    trade_dates = [
        date(2026, 2, 2),
        date(2026, 2, 3),
        date(2026, 2, 4),
        date(2026, 2, 5),
        date(2026, 2, 6),
    ]
    episode_by_date = {item.isoformat(): "episode-a" for item in trade_dates}

    safe = matrix.exact_horizon_safe_ranking_dates(
        {item.isoformat() for item in trade_dates},
        episode_by_date,
        trade_dates,
        horizon=3,
        entry_delay_trade_days=1,
    )

    assert safe == {"2026-02-02", "2026-02-03"}


def test_exact_match_replay_rejects_holding_window_crossing_episode(tmp_path: Path) -> None:
    (tmp_path / "ranking_2026-03-02.csv").write_text("stock_id\n2330\n", encoding="utf-8")
    price_frame = pd.DataFrame(
        {
            "stock_id": ["2330"] * 4,
            "trade_date": [
                date(2026, 3, 2),
                date(2026, 3, 3),
                date(2026, 3, 4),
                date(2026, 3, 5),
            ],
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
        }
    )
    args = SimpleNamespace(
        rankings_dir=str(tmp_path),
        max_ranking_files=None,
        horizon=3,
        top_n=10,
        entry_delay_trade_days=1,
        max_gross_exposure=0.65,
        max_position_weight=0.2,
        exact_regime_episode_by_date={
            "2026-03-02": "episode-a",
            "2026-03-03": "episode-a",
            "2026-03-04": "episode-b",
            "2026-03-05": "episode-b",
        },
    )

    with pytest.raises(ValueError, match="完整 exact-match episode"):
        matrix.run_portfolio_replay.build_entry_plans(
            args,
            price_frame,
            list(price_frame["trade_date"]),
            {},
        )


def test_strategy_matrix_replay_args_preserve_regime_history() -> None:
    base = SimpleNamespace(
        rankings_dir="rankings",
        features="features.parquet",
        top_n=10,
        max_ranking_files=None,
        max_gross_exposure=0.65,
        market_regime_history="regime.json",
        max_position_weight=0.2,
        fee_rate=0.001,
        tax_rate=0.003,
        slippage_rate=0.001,
        same_day_hit_priority="stop_loss",
    )
    scenario = {"horizon": 5, "stop_loss_pct": None, "take_profit_pct": None, "max_group_exposure": None}

    replay = matrix.replay_args(base, scenario)

    assert replay.market_regime_history == "regime.json"


def test_real_matrix_row_contains_pre_registered_statistical_evidence() -> None:
    scenario = {
        "horizon": 5,
        "stop_loss_pct": None,
        "take_profit_pct": 0.15,
        "max_group_exposure": 0.35,
    }
    replay = {
        "summary": {
            "total_return": 0.12,
            "max_drawdown": -0.08,
            "avg_trade_return": 0.03,
            "win_rate": 0.75,
            "trade_count": 4,
        },
        "trades": [
            {
                "stock_id": f"stock-{index}",
                "entry_date": f"2026-01-{index + 1:02d}",
                "exit_date": f"2026-01-{index + 2:02d}",
                "regime_episode_id": f"episode-{index}",
                "net_return": value,
            }
            for index, value in enumerate((0.03, 0.04, 0.02, -0.01))
        ],
    }

    row = matrix.matrix_row(scenario, replay)

    assert row["combination_id"] == research.canonical_json_hash(scenario)
    assert row["p_value"] is not None
    assert row["robust_neighbor_lineage"] == []
    assert row["robust_neighbor_pass_count"] == 0
    assert row["drawdown_within_limit"] is True
    expected_family = _expected_family([row["combination_id"]])
    matrix.annotate_statistical_lineage(
        [row],
        correction_family_id=expected_family["correction_family_id"],
    )
    gate = research.multiple_testing_gate([row], expected_family=expected_family)
    assert gate["evidence_complete"] is True
    assert gate["reason_code"] == "MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED"


def _adversarial_matrix_args(
    pre_registration: Path,
    experiment_registry: Path | None = None,
    *,
    market_regime_history: Path | None = None,
    allowed_episode_ids: list[str] | None = None,
) -> SimpleNamespace:
    default_history_path = pre_registration.parent / "market-regime-history.json"
    effective_history_path = market_regime_history or default_history_path
    effective_allowed_episode_ids = allowed_episode_ids
    if effective_allowed_episode_ids is None and default_history_path.exists():
        history = json.loads(default_history_path.read_text(encoding="utf-8"))
        runtime_lineage = research.statistical_lineage_authority(
            rows=history["rows"],
            contract=_contract(),
            regime_id=research.regime_identity_id(EXACT),
            horizons=[3, 5, 10],
        )
        effective_allowed_episode_ids = runtime_lineage["development_episode_ids"]
    return SimpleNamespace(
        rankings_dir="unused",
        features="unused.parquet",
        max_ranking_files=1,
        top_n=10,
        horizons="3,5,10",
        stop_loss_pcts="none,0.08,0.12",
        take_profit_pcts="none,0.15,0.25",
        max_group_exposures="none,0.35,0.55",
        max_gross_exposure=0.65,
        max_position_weight=0.2,
        fee_rate=0.001,
        tax_rate=0.003,
        slippage_rate=0.001,
        same_day_hit_priority="stop_loss",
        require_exact_regime=True,
        market_regime_history=str(effective_history_path),
        base_regime="BROAD_RISK_ON",
        family_tags="BIG_BULL,HIGH_CHOPPY",
        allowed_episode_ids=",".join(effective_allowed_episode_ids or ["episode-1"]),
        pre_registration=str(pre_registration),
        experiment_registry=str(experiment_registry) if experiment_registry else None,
    )


def _write_registered_matrix_registration(
    tmp_path: Path,
    *,
    tested_ids: list[str],
    correction_family_ids: list[str],
    partition_id: str,
    correction_scope: str,
    lineage: dict | None = None,
) -> tuple[Path, Path]:
    contract = _contract()
    universe = research.parameter_universe_summary(contract)
    tested_ids = sorted(tested_ids)
    correction_family_ids = sorted(correction_family_ids)
    correction_family_id = research.canonical_json_hash(correction_family_ids)
    runtime_lineage = None
    if lineage is None:
        _, rows, runtime_split = _write_runtime_history(tmp_path)
        split_artifact = {
            "metadata": runtime_split.metadata,
            "development": runtime_split.development,
            "validation": runtime_split.validation,
            "embargo": runtime_split.embargo,
            "sealed": runtime_split.sealed,
        }
        runtime_split_ids = {
            role: list(runtime_split.metadata[f"{role}_episode_ids"])
            for role in ("development", "validation", "embargo", "sealed")
        }
        runtime_lineage = {
            "dataset_hash": research.canonical_json_hash(rows),
            "split_id": runtime_split.metadata["split_id"],
            "split_artifact_hash": research.canonical_json_hash(split_artifact),
            "split_ids": runtime_split_ids,
            "sealed_trade_dates": [
                str(trade_date)
                for episode in runtime_split.sealed
                for trade_date in episode["trade_dates"]
            ],
        }
    effective_lineage = lineage or runtime_lineage or {}
    split_ids = effective_lineage.get("split_ids") or {
        "development": ["episode-1"],
        "validation": ["validation-1"],
        "embargo": ["embargo-1"],
        "sealed": ["sealed-1"],
    }
    registration = research.build_experiment_pre_registration(
        {
            "research_question": "public matrix trust-boundary adversarial fixture",
            "baseline_id": "baseline-v1",
            "regime_id": "BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY",
            "dataset_hash": effective_lineage.get("dataset_hash", "sha256:dataset"),
            "split_id": effective_lineage.get("split_id", "sha256:split"),
            "split_artifact_hash": effective_lineage.get(
                "split_artifact_hash", "sha256:split-artifact"
            ),
            "parameter_space_hash": universe["parameter_space_hash"],
            "contract_hash": research.canonical_json_hash(contract),
            "global_combination_ids": sorted(universe["legal_combination_ids"]),
            "global_combination_ids_hash": universe["combination_id_hash"],
            "global_family_id": research.canonical_json_hash(
                sorted(universe["legal_combination_ids"])
            ),
            "global_family_size": universe["legal_combination_count"],
            "tested_combination_ids": tested_ids,
            "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
            "correction_family_combination_ids": correction_family_ids,
            "correction_family_id": correction_family_id,
            "correction_family_size": len(correction_family_ids),
            "partition_policy": {
                "policy_id": "validation_profile_partition.v1",
                "partition_id": partition_id,
                "correction_scope": correction_scope,
                "parameter_space_hash": universe["parameter_space_hash"],
                "tested_combination_count": len(tested_ids),
                "tested_combination_ids_hash": research.canonical_json_hash(tested_ids),
                "correction_family_id": correction_family_id,
                "correction_family_size": len(correction_family_ids),
            },
            "metric_policy_hash": research.canonical_json_hash(
                contract["multiple_testing_policy"]
            ),
            "development_episode_ids": split_ids["development"],
            "validation_episode_ids": split_ids["validation"],
            "embargo_episode_ids": split_ids["embargo"],
            "sealed_episode_ids": split_ids["sealed"],
            "episode_split_ids_hash": effective_lineage.get(
                "episode_split_ids_hash",
                research.canonical_json_hash(split_ids),
            ),
            "sealed_trade_dates": effective_lineage.get(
                "sealed_trade_dates", ["2026-01-31"]
            ),
        }
    )
    registry_path = tmp_path / "registry.jsonl"
    registered = research.append_experiment_registry(registry_path, registration)
    assert registered["ok"] is True
    registration_path = tmp_path / "pre_registration.json"
    registration_path.write_text(
        json.dumps(
            {
                **registration,
                "registry_record_hash": registered["registry_record_hash"],
            }
        ),
        encoding="utf-8",
    )
    return registration_path, registry_path


def _rewrite_content_addressed_registration_field(
    registration_path: Path,
    registry_path: Path,
    *,
    field: str,
    value: object,
) -> None:
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    artifact = {
        key: item
        for key, item in registration.items()
        if key != "registry_record_hash"
    }
    artifact[field] = value
    artifact["experiment_id"] = research.deterministic_experiment_id(artifact)
    registry_record_hash = research.canonical_json_hash(artifact)
    registration_path.write_text(
        json.dumps(
            {
                **artifact,
                "registry_record_hash": registry_record_hash,
            }
        ),
        encoding="utf-8",
    )
    registry_path.write_text(
        json.dumps(
            {
                **artifact,
                "event_type": "PRE_REGISTRATION",
                "registry_record_hash": registry_record_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_runtime_history(tmp_path: Path) -> tuple[Path, list[dict], object]:
    rows: list[dict] = []
    cursor = date(2025, 1, 2)
    for _ in range(10):
        for _ in range(15):
            trade_date = cursor.isoformat()
            rows.append(
                {
                    "trade_date": trade_date,
                    "as_of_date": trade_date,
                    **EXACT,
                    "is_transition": False,
                }
            )
            cursor += timedelta(days=1)
        transition_date = cursor.isoformat()
        rows.append(
            {
                "trade_date": transition_date,
                "as_of_date": transition_date,
                **EXACT,
                "is_transition": True,
            }
        )
        cursor += timedelta(days=1)
    history_path = tmp_path / "market-regime-history.json"
    history_path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    split = build_regime_episode_split(
        research.build_regime_episodes(rows),
        horizon=10,
        min_development_episodes=2,
        validation_episodes=1,
        sealed_episodes=1,
        min_embargo_trade_days=10,
    )
    return history_path, rows, split


def test_public_matrix_rejects_content_addressed_forged_runtime_lineage(
    tmp_path: Path,
) -> None:
    history_path, _, runtime_split = _write_runtime_history(tmp_path)
    authority = research.statistical_family_contract(_contract())
    forged_split_ids = {
        "development": list(runtime_split.metadata["development_episode_ids"]),
        "validation": ["sha256:forged-validation"],
        "embargo": ["sha256:forged-embargo"],
        "sealed": ["sha256:forged-sealed"],
    }
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=authority["legal_partitions"]["standard"],
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
        lineage={
            "dataset_hash": "sha256:forged-runtime-lineage",
            "split_id": "sha256:forged-split",
            "split_artifact_hash": "sha256:forged-split-artifact",
            "split_ids": forged_split_ids,
        },
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(
            registration_path,
            registry_path,
            market_regime_history=history_path,
            allowed_episode_ids=runtime_split.metadata["development_episode_ids"],
        )
    )

    assert expected_family["registration_valid"] is False
    assert expected_family["registration_validation_reason"] == "DATASET_HASH_MISMATCH"


def test_public_matrix_rejects_content_addressed_forged_sealed_trade_dates(
    tmp_path: Path,
) -> None:
    history_path, rows, runtime_split = _write_runtime_history(tmp_path)
    contract = _contract()
    authority = research.statistical_family_contract(contract)
    runtime_lineage = research.statistical_lineage_authority(
        rows=rows,
        contract=contract,
        regime_id=research.regime_identity_id(EXACT),
        horizons=[3, 5, 10],
    )
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=authority["legal_partitions"]["standard"],
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
        lineage={
            "dataset_hash": runtime_lineage["dataset_hash"],
            "split_id": runtime_lineage["split_id"],
            "split_artifact_hash": runtime_lineage["split_artifact_hash"],
            "split_ids": {
                role: list(runtime_lineage[f"{role}_episode_ids"])
                for role in ("development", "validation", "embargo", "sealed")
            },
            "sealed_trade_dates": ["2099-01-01"],
        },
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(
            registration_path,
            registry_path,
            market_regime_history=history_path,
            allowed_episode_ids=runtime_split.metadata["development_episode_ids"],
        )
    )
    gate = research.multiple_testing_gate(
        _statistical_rows(
            authority["legal_partitions"]["standard"],
            authority["global_family_id"],
        ),
        expected_family=expected_family,
    )

    assert gate["family_validation_reason"] == "SEALED_TRADE_DATES_MISMATCH"
    assert (
        expected_family["registration_validation_reason"]
        == "SEALED_TRADE_DATES_MISMATCH"
    )
    assert expected_family["registration_valid"] is False


@pytest.mark.parametrize(
    ("forged_field", "forged_value", "reason_code"),
    [
        (
            "sealed_trade_dates",
            ["2099-01-01"],
            "SEALED_TRADE_DATES_MISMATCH",
        ),
        (
            "sealed_trade_date_hash",
            "sha256:forged-sealed-trade-date-hash",
            "SEALED_TRADE_DATE_HASH_MISMATCH",
        ),
        (
            "sealed_dataset_slice_hash",
            "sha256:forged-sealed-dataset-slice-hash",
            "SEALED_DATASET_SLICE_HASH_MISMATCH",
        ),
    ],
)
def test_public_matrix_sealed_lineage_mismatch_reason_codes_are_stable(
    tmp_path: Path,
    forged_field: str,
    forged_value: object,
    reason_code: str,
) -> None:
    history_path, rows, runtime_split = _write_runtime_history(tmp_path)
    contract = _contract()
    authority = research.statistical_family_contract(contract)
    runtime_lineage = research.statistical_lineage_authority(
        rows=rows,
        contract=contract,
        regime_id=research.regime_identity_id(EXACT),
        horizons=[3, 5, 10],
    )
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=authority["legal_partitions"]["standard"],
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
        lineage={
            "dataset_hash": runtime_lineage["dataset_hash"],
            "split_id": runtime_lineage["split_id"],
            "split_artifact_hash": runtime_lineage["split_artifact_hash"],
            "split_ids": {
                role: list(runtime_lineage[f"{role}_episode_ids"])
                for role in ("development", "validation", "embargo", "sealed")
            },
            "sealed_trade_dates": runtime_lineage["sealed_trade_dates"],
        },
    )
    _rewrite_content_addressed_registration_field(
        registration_path,
        registry_path,
        field=forged_field,
        value=forged_value,
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(
            registration_path,
            registry_path,
            market_regime_history=history_path,
            allowed_episode_ids=runtime_split.metadata["development_episode_ids"],
        )
    )

    assert expected_family["registration_valid"] is False
    assert expected_family["registration_validation_reason"] == reason_code


@pytest.mark.parametrize(
    ("forged_field", "reason_code"),
    [
        ("dataset_hash", "DATASET_HASH_MISMATCH"),
        ("split_id", "SPLIT_ID_MISMATCH"),
        ("split_artifact_hash", "SPLIT_ARTIFACT_HASH_MISMATCH"),
        ("development", "DEVELOPMENT_EPISODE_IDS_MISMATCH"),
        ("validation", "VALIDATION_EPISODE_IDS_MISMATCH"),
        ("embargo", "EMBARGO_EPISODE_IDS_MISMATCH"),
        ("sealed", "SEALED_EPISODE_IDS_MISMATCH"),
        ("episode_split_ids_hash", "EPISODE_SPLIT_HASH_MISMATCH"),
    ],
)
def test_public_matrix_lineage_mismatch_reason_codes_are_stable(
    tmp_path: Path,
    forged_field: str,
    reason_code: str,
) -> None:
    history_path, rows, runtime_split = _write_runtime_history(tmp_path)
    contract = _contract()
    authority = research.statistical_family_contract(contract)
    runtime_lineage = research.statistical_lineage_authority(
        rows=rows,
        contract=contract,
        regime_id=research.regime_identity_id(EXACT),
        horizons=[3, 5, 10],
    )
    split_ids = {
        role: list(runtime_lineage[f"{role}_episode_ids"])
        for role in ("development", "validation", "embargo", "sealed")
    }
    registration_lineage = {
        "dataset_hash": runtime_lineage["dataset_hash"],
        "split_id": runtime_lineage["split_id"],
        "split_artifact_hash": runtime_lineage["split_artifact_hash"],
        "split_ids": split_ids,
        "sealed_trade_dates": runtime_lineage["sealed_trade_dates"],
    }
    if forged_field in split_ids:
        split_ids[forged_field] = [f"sha256:forged-{forged_field}"]
    elif forged_field == "episode_split_ids_hash":
        registration_lineage[forged_field] = "sha256:forged-episode-split-ids"
    else:
        registration_lineage[forged_field] = f"sha256:forged-{forged_field}"
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=authority["legal_partitions"]["standard"],
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
        lineage=registration_lineage,
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(
            registration_path,
            registry_path,
            market_regime_history=history_path,
            allowed_episode_ids=runtime_split.metadata["development_episode_ids"],
        )
    )

    assert expected_family["registration_valid"] is False
    assert expected_family["registration_validation_reason"] == reason_code


def _statistical_rows(combination_ids: list[str], family_id: str) -> list[dict]:
    return [
        {
            "combination_id": combination_id,
            "correction_family_id": family_id,
            "p_value": 0.015625,
            "robust_neighbor_lineage": sorted(set(combination_ids) - {combination_id}),
            "robust_neighbor_pass_count": len(combination_ids) - 1,
            "drawdown_within_limit": True,
            "statistical_unit_policy": "independent_regime_episode_cluster.v1",
            "statistical_unit_ids": [f"episode-{index}" for index in range(6)],
            "statistical_unit_count": 6,
            "pseudo_replication_detected": False,
        }
        for combination_id in combination_ids
    ]


def test_public_matrix_rejects_manager_registered_local_family(
    tmp_path: Path,
) -> None:
    scenarios = [
        {
            "horizon": horizon,
            "stop_loss_pct": None,
            "take_profit_pct": None,
            "max_group_exposure": None,
        }
        for horizon in (3, 5, 10)
    ]
    tested_ids = sorted(research.canonical_json_hash(scenario) for scenario in scenarios)
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=tested_ids,
        correction_family_ids=tested_ids,
        partition_id="forged-local-three",
        correction_scope="local_profile",
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(registration_path, registry_path)
    )
    gate = research.multiple_testing_gate(
        _statistical_rows(
            tested_ids,
            research.canonical_json_hash(tested_ids),
        ),
        expected_family=expected_family,
    )

    assert gate["ok"] is False
    assert gate["evidence_complete"] is False
    assert gate["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert gate["family_validation_reason"] in {
        "INVALID_PARTITION_ID",
        "INVALID_CORRECTION_FAMILY",
    }


def test_statistical_family_contract_has_81_of_720_standard_partition() -> None:
    authority = research.statistical_family_contract(_contract())
    coverage = research.validation_profile_partition_coverage(_contract())

    assert authority["global_family_size"] == 720
    assert authority["corrected_alpha"] == pytest.approx(0.05 / 720)
    assert authority["minimum_statistical_unit_count"] == 14
    assert coverage["partitions"]["standard"]["tested_combination_count"] == 81
    assert coverage["partitions"]["standard"]["duplicate_ids"] == []
    assert coverage["global_family_size"] == 720


def test_public_matrix_accepts_manager_registered_standard_partition_81_of_720(
    tmp_path: Path,
) -> None:
    coverage = research.validation_profile_partition_coverage(_contract())
    standard_ids = coverage["partitions"]["standard"]["tested_combination_ids"]
    authority = research.statistical_family_contract(_contract())
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=standard_ids,
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
    )

    expected_family = matrix.expected_statistical_family(
        _adversarial_matrix_args(registration_path, registry_path)
    )
    gate = research.multiple_testing_gate(
        _statistical_rows(standard_ids, authority["global_family_id"]),
        expected_family=expected_family,
    )

    assert expected_family["registration_valid"] is True
    assert expected_family["registration_validation_reason"] == (
        "STATISTICAL_FAMILY_AUTHORITY_VALID"
    )
    assert len(expected_family["tested_combination_ids"]) == 81
    assert expected_family["correction_family_size"] == 720
    assert gate["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert gate["corrected_alpha"] == pytest.approx(0.05 / 720)
    assert gate["minimum_statistical_unit_count"] == 14


def test_statistical_partition_rejects_duplicate_and_missing_ids() -> None:
    authority = research.statistical_family_contract(_contract())
    standard_ids = research.validation_profile_partition_coverage(_contract())[
        "partitions"
    ]["standard"]["tested_combination_ids"]

    duplicate = research.validate_statistical_partition(
        partition_id="standard",
        tested_combination_ids=[*standard_ids, standard_ids[0]],
        authority=authority,
    )
    missing = research.validate_statistical_partition(
        partition_id="standard",
        tested_combination_ids=standard_ids[:-1],
        authority=authority,
    )

    assert duplicate["ok"] is False
    assert duplicate["reason_code"] == "DUPLICATE_TESTED_COMBINATION_IDS"
    assert missing["ok"] is False
    assert missing["reason_code"] == "PARTITION_TESTED_IDS_MISMATCH"
    assert missing["missing_ids"] == [standard_ids[-1]]


def test_statistical_authority_rejects_unknown_contract_global_hash_and_registry_hash(
    tmp_path: Path,
) -> None:
    contract = _contract()
    authority = research.statistical_family_contract(contract)
    standard_ids = authority["legal_partitions"]["standard"]
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=standard_ids,
        correction_family_ids=authority["global_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
    )
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registry = [
        json.loads(line)
        for line in registry_path.read_text(encoding="utf-8").splitlines()
    ]

    unknown_contract = research.validate_statistical_family_registration(
        {**registration, "contract_hash": "sha256:unknown"},
        contract=contract,
        registry=registry,
    )
    wrong_global_hash = research.validate_statistical_family_registration(
        {**registration, "global_combination_ids_hash": "sha256:wrong"},
        contract=contract,
        registry=registry,
    )
    wrong_global_ids = research.validate_statistical_family_registration(
        {**registration, "global_combination_ids": registration["global_combination_ids"][:-1]},
        contract=contract,
        registry=registry,
    )
    wrong_registry_hash = research.validate_statistical_family_registration(
        {**registration, "registry_record_hash": "sha256:wrong"},
        contract=contract,
        registry=registry,
    )

    assert unknown_contract["reason_code"] == "UNKNOWN_CONTRACT"
    assert wrong_global_ids["reason_code"] == "GLOBAL_COMBINATION_IDS_MISMATCH"
    assert wrong_global_hash["reason_code"] == "GLOBAL_COMBINATION_IDS_HASH_MISMATCH"
    assert wrong_registry_hash["reason_code"] == "REGISTRY_RECORD_HASH_MISMATCH"


def test_available_data_canary_dry_run_reports_episode_gaps() -> None:
    result = research.closed_mode_episode_evidence_status(
        exact_regime="BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY",
        available_episode_count=2,
        contract=_contract(),
    )

    assert result["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["exact_regime"] == "BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY"
    assert result["available_episode_count"] == 2
    assert result["theoretical_minimum_episode_count"] == 4
    assert result["episode_gaps"] == {
        "development": 0,
        "validation": 1,
        "sealed": 1,
    }


def _run_adversarial_matrix_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tested_ids: list[str],
) -> dict:
    universe = research.parameter_universe_summary(_contract())
    registration_path, registry_path = _write_registered_matrix_registration(
        tmp_path,
        tested_ids=tested_ids,
        correction_family_ids=universe["legal_combination_ids"],
        partition_id="standard",
        correction_scope="global_parameter_universe",
    )
    monkeypatch.setattr(
        matrix.run_portfolio_replay.run_backtest_replay,
        "load_price_frame",
        lambda _: pd.DataFrame(),
    )
    monkeypatch.setattr(
        matrix,
        "exact_regime_context",
        lambda _: (EXACT, {"2026-01-02"}, {"2026-01-02": "episode-1"}),
    )
    monkeypatch.setattr(
        matrix,
        "exact_horizon_safe_ranking_dates",
        lambda allowed_dates, *_args, **_kwargs: allowed_dates,
    )
    monkeypatch.setattr(
        matrix.run_portfolio_replay.run_backtest_replay,
        "market_trade_dates",
        lambda _: [date(2026, 1, 2)],
    )
    repeated_trade = {
        "stock_id": "2330",
        "ranking_date": "2026-01-02",
        "entry_date": "2026-01-02",
        "exit_date": "2026-01-03",
        "regime_episode_id": "episode-1",
        "net_return": 0.01,
    }
    replay = {
        "summary": {
            "total_return": 0.2,
            "max_drawdown": -0.05,
            "avg_trade_return": 0.01,
            "win_rate": 1.0,
            "trade_count": 20,
        },
        "trades": [dict(repeated_trade) for _ in range(20)],
    }
    monkeypatch.setattr(
        matrix.run_portfolio_replay,
        "run_portfolio_from_price_frame",
        lambda *_: replay,
    )
    return matrix.build_payload(
        _adversarial_matrix_args(registration_path, registry_path)
    )


def test_public_matrix_blocks_pre_registration_family_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios = research.validation_profile_combinations(
        "3,5,10",
        "none,0.08,0.12",
        "none,0.15,0.25",
        "none,0.35,0.55",
    )
    tested_ids = [research.canonical_json_hash(scenario) for scenario in scenarios]
    tested_ids[-1] = "sha256:not-the-executed-combination"

    payload = _run_adversarial_matrix_payload(tmp_path, monkeypatch, tested_ids)

    gate = payload["summary"]["statistical_gate"]
    assert gate["ok"] is False
    assert gate["evidence_complete"] is False
    assert gate["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert gate["family_validation_reason"] == "PARTITION_TESTED_IDS_MISMATCH"


def test_public_matrix_rejects_duplicate_trade_pseudo_replication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios = research.validation_profile_combinations(
        "3,5,10",
        "none,0.08,0.12",
        "none,0.15,0.25",
        "none,0.35,0.55",
    )
    tested_ids = [research.canonical_json_hash(scenario) for scenario in scenarios]

    payload = _run_adversarial_matrix_payload(tmp_path, monkeypatch, tested_ids)

    gate = payload["summary"]["statistical_gate"]
    assert gate["ok"] is False
    assert gate["evidence_complete"] is False
    assert gate["reason_code"] == "INSUFFICIENT_EVIDENCE"
    assert gate["pseudo_replication_detected"] is True


def _ineligible_topic() -> research.ResearchTopic:
    return research.ResearchTopic(
        topic_id="review:ineligible-zero-coverage",
        title="ineligible",
        hypothesis="coverage closed",
        validation_plan="monitor only",
        runner="strategy_matrix_comparison",
        candidate_dir="candidate",
        baseline_dir="baseline",
        score=0.0,
        reasons=[],
        evidence_sources=[],
        ranking_file_count=10,
        eligible=False,
        reason_code="ZERO_INFORMATION_VALUE",
    )


def test_zero_exact_date_topic_is_ineligible_across_selection_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = research.PROJECT_ROOT / "config/regime_research_contract.json"
    candidate_dir = tmp_path / "artifacts" / "backtest" / "candidate"
    baseline_dir = tmp_path / "artifacts" / "backtest" / "baseline"
    candidate_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    (candidate_dir / "ranking_2025-01-02.csv").write_text("rank,stock_id\n", encoding="utf-8")
    (baseline_dir / "ranking_2025-01-03.csv").write_text("rank,stock_id\n", encoding="utf-8")
    history_path = tmp_path / "market_regime_history.json"
    history_rows = _closed_history_rows()
    history_path.write_text(json.dumps({"rows": history_rows}), encoding="utf-8")

    monkeypatch.setattr(research, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(research, "ARTIFACTS_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(research, "OUTPUT_DIR", tmp_path / "artifacts" / "autonomous_research")
    monkeypatch.setattr(research, "ledger_signals", lambda: ([], []))
    monkeypatch.setattr(research, "external_review_signals", lambda: ([], []))
    monkeypatch.setattr(research, "load_topic_registry", lambda: {})
    monkeypatch.setattr(research, "load_last_run_at_by_topic", lambda: {})

    args = SimpleNamespace(
        date=history_rows[-1]["trade_date"],
        candidate_dir="artifacts/backtest/candidate",
        baseline_dir="artifacts/backtest/baseline",
        min_ranking_files=1,
        max_topics=12,
        closed_regime_research=True,
        market_regime_history=str(history_path),
        research_contract=str(contract_path),
        coverage_map=None,
    )
    topics = research.generate_all_topics(args)
    zero_exact_topic = topics[0]
    selection_args = SimpleNamespace(
        execute_topic_count=1,
        from_queue=False,
        topic_index=0,
        execute=True,
        rerun=False,
        include_rejected=False,
    )
    index_selection = research.select_topics_for_run([zero_exact_topic], selection_args)
    fallback_selection = research.select_topics_for_run(
        [_ineligible_topic(), zero_exact_topic],
        selection_args,
    )
    monkeypatch.setattr(
        research,
        "load_next_action_queue",
        lambda: [{"topic_id": zero_exact_topic.topic_id}],
    )
    selection_args.from_queue = True
    queue_selection = research.select_topics_for_run([zero_exact_topic], selection_args)

    observed = {
        "eligible": zero_exact_topic.eligible,
        "reason_code": zero_exact_topic.reason_code,
        "index": [topic.topic_id for topic in index_selection],
        "fallback": [topic.topic_id for topic in fallback_selection],
        "queue": [topic.topic_id for topic in queue_selection],
    }
    assert observed == {
        "eligible": False,
        "reason_code": "NO_EXACT_REGIME_RANKING_DATE",
        "index": [],
        "fallback": [],
        "queue": [],
    }


def test_legal_exact_date_topic_remains_selectable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_dir = tmp_path / "artifacts" / "backtest" / "candidate"
    baseline_dir = tmp_path / "artifacts" / "backtest" / "baseline"
    candidate_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    for path in (candidate_dir, baseline_dir):
        (path / "ranking_2026-01-02.csv").write_text("rank,stock_id\n", encoding="utf-8")
    monkeypatch.setattr(research, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(research, "load_topic_registry", lambda: {})
    monkeypatch.setattr(research, "load_last_run_at_by_topic", lambda: {})

    topic = research.topic_for_dir(
        {"repo_path": "artifacts/backtest/candidate", "count": 1},
        baseline_dir="artifacts/backtest/baseline",
        ledger_candidates=[],
        external_signals=[],
        evidence_sources=[],
        current_regime=EXACT,
        coverage={"evidence_gap": 1.0},
        enforce_exact_regime_ranking_dates=True,
        exact_regime_allowed_dates={"2026-01-02"},
        exact_regime_as_of_date="2026-01-03",
    )
    assert topic is not None
    args = SimpleNamespace(
        execute_topic_count=1,
        from_queue=False,
        topic_index=0,
        execute=True,
        rerun=False,
        include_rejected=False,
    )

    assert topic.eligible is True
    assert topic.reason_code == "ELIGIBLE"
    assert research.select_topics_for_run([topic], args) == [topic]


@pytest.mark.parametrize(
    ("case", "expected_reason", "expected_role"),
    [
        ("missing_authority", "MISSING_EXACT_REGIME_AUTHORITY", None),
        ("malformed", "MALFORMED_RANKING_DATE", "candidate"),
        ("future_only", "FUTURE_ONLY_RANKING_DATE", "candidate"),
        ("path_escape", "RANKING_INVENTORY_PATH_ESCAPE", "candidate"),
        ("baseline_no_exact", "NO_EXACT_REGIME_RANKING_DATE", "baseline"),
    ],
)
def test_exact_regime_ranking_inventory_hostile_cases_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_reason: str,
    expected_role: str | None,
) -> None:
    repo_root = tmp_path / "repo"
    candidate_dir = repo_root / "artifacts" / "backtest" / "candidate"
    baseline_dir = repo_root / "artifacts" / "backtest" / "baseline"
    candidate_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    baseline_ranking_date = "2025-01-02" if case == "baseline_no_exact" else "2026-01-02"
    (baseline_dir / f"ranking_{baseline_ranking_date}.csv").write_text("rank,stock_id\n", encoding="utf-8")
    allowed_dates: set[str] | None = {"2026-01-02"}
    if case == "missing_authority":
        allowed_dates = None
        (candidate_dir / "ranking_2026-01-02.csv").write_text("rank,stock_id\n", encoding="utf-8")
    elif case == "malformed":
        (candidate_dir / "ranking_not-a-date.csv").write_text("rank,stock_id\n", encoding="utf-8")
    elif case == "future_only":
        (candidate_dir / "ranking_2026-02-01.csv").write_text("rank,stock_id\n", encoding="utf-8")
    elif case == "path_escape":
        candidate_dir = tmp_path / "outside"
        candidate_dir.mkdir()
        (candidate_dir / "ranking_2026-01-02.csv").write_text("rank,stock_id\n", encoding="utf-8")
    else:
        (candidate_dir / "ranking_2026-01-02.csv").write_text("rank,stock_id\n", encoding="utf-8")
    monkeypatch.setattr(research, "PROJECT_ROOT", repo_root)

    result = research.exact_regime_topic_ranking_eligibility(
        candidate_dir=str(candidate_dir),
        baseline_dir=str(baseline_dir),
        allowed_dates=allowed_dates,
        as_of_date="2026-01-03",
    )

    assert result["eligible"] is False
    assert result["reason_code"] == expected_reason
    assert result.get("inventory_role") == expected_role


@pytest.mark.parametrize("symlink_role", ["candidate", "baseline"])
def test_exact_regime_ranking_inventory_rejects_external_file_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    symlink_role: str,
) -> None:
    repo_root = tmp_path / "repo"
    candidate_dir = repo_root / "artifacts" / "backtest" / "candidate"
    baseline_dir = repo_root / "artifacts" / "backtest" / "baseline"
    candidate_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    ranking_name = "ranking_2026-01-02.csv"
    for directory in (candidate_dir, baseline_dir):
        (directory / ranking_name).write_text("rank,stock_id\n", encoding="utf-8")

    outside_file = tmp_path / "outside" / ranking_name
    outside_file.parent.mkdir()
    outside_file.write_text("rank,stock_id\n1,9999\n", encoding="utf-8")
    escaped_entry = {
        "candidate": candidate_dir,
        "baseline": baseline_dir,
    }[symlink_role] / ranking_name
    escaped_entry.unlink()
    escaped_entry.symlink_to(outside_file)
    monkeypatch.setattr(research, "PROJECT_ROOT", repo_root)

    result = research.exact_regime_topic_ranking_eligibility(
        candidate_dir=str(candidate_dir),
        baseline_dir=str(baseline_dir),
        allowed_dates={"2026-01-02"},
        as_of_date="2026-01-03",
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "RANKING_INVENTORY_PATH_ESCAPE"
    assert result["inventory_role"] == symlink_role


def test_ineligible_topic_is_excluded_from_selection_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(research, "load_topic_registry", lambda: {})
    monkeypatch.setattr(research, "load_last_run_at_by_topic", lambda: {})
    args = SimpleNamespace(
        execute_topic_count=1,
        from_queue=False,
        topic_index=0,
        execute=True,
        rerun=False,
        include_rejected=False,
    )

    selected = research.select_topics_for_run([_ineligible_topic()], args)

    assert selected == []


def test_closed_comparison_cannot_promote_raw_best_without_statistical_gate(tmp_path: Path) -> None:
    path = tmp_path / "comparison.json"
    path.write_text(
        json.dumps(
            {
                "summary": [
                    {
                        "variant": "baseline",
                        "best_score": 0.1,
                        "best_total_return": 0.01,
                        "best_max_drawdown": -0.1,
                        "exact_match_regime_required": True,
                        "statistical_gate_ok": False,
                    },
                    {
                        "variant": "candidate",
                        "best_score": 9.9,
                        "best_total_return": 0.5,
                        "best_max_drawdown": -0.05,
                        "exact_match_regime_required": True,
                        "statistical_gate_ok": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    outcome = research.outcome_from_comparison(path)

    assert outcome["decision"] == "NO_STRATEGY"
    assert outcome["reason_code"] == "MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED"


def _closed_history_rows() -> list[dict]:
    rows: list[dict] = []
    cursor = date(2026, 1, 1)
    for episode_index in range(8):
        if episode_index:
            rows.append(
                {
                    "trade_date": cursor.isoformat(),
                    "as_of_date": cursor.isoformat(),
                    **EXACT,
                    "is_transition": True,
                }
            )
            cursor += timedelta(days=1)
        for _ in range(12):
            rows.append({"trade_date": cursor.isoformat(), "as_of_date": cursor.isoformat(), **EXACT})
            cursor += timedelta(days=1)
    return rows


def test_development_matrix_scope_accepts_only_authoritative_development_episodes(
    tmp_path: Path,
) -> None:
    history_rows = _closed_history_rows()
    history_path = tmp_path / "market_regime_history.json"
    history_path.write_text(json.dumps({"rows": history_rows}), encoding="utf-8")
    contract = json.loads(
        (research.PROJECT_ROOT / "config/regime_research_contract.json").read_text(
            encoding="utf-8"
        )
    )
    lineage = research.statistical_lineage_authority(
        rows=history_rows,
        contract=contract,
        regime_id=research.regime_identity_id(EXACT),
        horizons=[3, 5, 10],
    )
    args = SimpleNamespace(
        development_only=True,
        require_exact_regime=True,
        pre_registration=None,
        experiment_registry=None,
        market_regime_history=str(history_path),
        base_regime=EXACT["base_regime"],
        family_tags=",".join(EXACT["family_tags"]),
        allowed_episode_ids=",".join(lineage["development_episode_ids"]),
        horizons="3,5,10",
    )

    accepted = matrix.validate_development_scope(args)
    assert accepted is not None
    assert accepted["reason_code"] == "DEVELOPMENT_EPISODES_ONLY"

    args.allowed_episode_ids = ",".join(lineage["sealed_episode_ids"])
    with pytest.raises(ValueError, match="DEVELOPMENT_EPISODE_SCOPE_MISMATCH"):
        matrix.validate_development_scope(args)


def test_closed_manager_cli_writes_registration_split_and_append_only_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_path = tmp_path / "market_regime_history.json"
    history_rows = _closed_history_rows()
    history_path.write_text(json.dumps({"rows": history_rows}), encoding="utf-8")
    topic = research.ResearchTopic(
        topic_id="closed:cli-e2e",
        title="closed cli",
        hypothesis="closed manager 必須先完成治理證據",
        validation_plan="coarse screen",
        runner="strategy_matrix_comparison",
        candidate_dir=str(tmp_path / "candidate"),
        baseline_dir=str(tmp_path / "baseline"),
        score=1.0,
        reasons=[],
        evidence_sources=[],
        ranking_file_count=1,
        validation_profile="standard",
        horizons="3,5,10",
        stop_loss_pcts="none,0.08,0.12",
        take_profit_pcts="none,0.15,0.25",
        max_group_exposures="none,0.35,0.55",
        regime_identity=EXACT,
        eligible=True,
        reason_code="ELIGIBLE",
    )
    output = tmp_path / "closed_run.json"
    args = SimpleNamespace(
        date=history_rows[-1]["trade_date"],
        output=str(output),
        features=str(tmp_path / "features.parquet"),
        baseline_dir=topic.baseline_dir,
        candidate_dir=topic.candidate_dir,
        topic_index=0,
        max_topics=1,
        min_ranking_files=1,
        max_ranking_files=1,
        horizons="3,5,10",
        stop_loss_pcts="none,0.08,0.12",
        take_profit_pcts="none,0.15,0.25",
        max_group_exposures="none,0.35,0.55",
        execute=True,
        execute_topic_count=1,
        from_queue=False,
        rerun=False,
        include_rejected=False,
        no_manager_update=True,
        closed_regime_research=True,
        market_regime_history=str(history_path),
        research_contract=str(research.PROJECT_ROOT / "config/regime_research_contract.json"),
        coverage_map=None,
    )
    monkeypatch.setattr(research, "OUTPUT_DIR", tmp_path / "manager")
    monkeypatch.setattr(research, "parse_args", lambda: args)
    monkeypatch.setattr(research, "generate_all_topics", lambda _: [topic])
    monkeypatch.setattr(
        research,
        "build_daily_source_lineage",
        lambda **_: {
            "schema_version": "fog-daily-source-lineage.v1",
            "features_path": "data/clean/features.parquet",
            "features_sha256": "a" * 64,
            "daily_source_date": history_rows[-1]["trade_date"],
        },
    )

    def fake_run_step(name: str, command: list[str]) -> dict:
        output_path = Path(command[command.index("--output") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if command[1].endswith("run_backtest_strategy_matrix.py"):
            output_path.write_text(
                json.dumps(
                    {
                        "contract": {"exact_match_regime_required": True},
                        "summary": {
                            "statistical_gate": {
                                "ok": False,
                                "reason_code": "INSUFFICIENT_EVIDENCE",
                            },
                            "formal_candidate_scenario_ids": [],
                        },
                        "scenarios": [],
                    }
                ),
                encoding="utf-8",
            )
        else:
            baseline_path = command[command.index("--variant") + 1].split("=", 1)[1]
            candidate_path = command[command.index("--variant", command.index("--variant") + 1) + 1].split("=", 1)[1]
            output_path.write_text(
                json.dumps(
                    {
                        "summary": [
                            {
                                "variant": "baseline",
                                "path": baseline_path,
                                "exact_match_regime_required": True,
                                "statistical_gate_ok": False,
                            },
                            {
                                "variant": "candidate",
                                "path": candidate_path,
                                "exact_match_regime_required": True,
                                "statistical_gate_ok": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
        return {
            "name": name,
            "status": "OK",
            "returncode": 0,
            "started_at": "2026-07-27T00:00:00+00:00",
            "ended_at": "2026-07-27T00:00:01+00:00",
            "command": command,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(research, "run_step", fake_run_step)

    assert research.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    registry_path = Path(payload["outputs"]["closed_experiment_registry"])
    events = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]

    assert [event["event_type"] for event in events] == [
        "PRE_REGISTRATION",
        "STATE_TRANSITION",
        "STATE_TRANSITION",
    ]
    assert [event.get("target_state") for event in events[1:]] == [
        "COARSE_SCREEN",
        "INSUFFICIENT_EVIDENCE",
    ]
    assert Path(payload["outputs"]["closed_episode_split"]).exists()
    registration_path = Path(payload["outputs"]["closed_pre_registration"])
    assert registration_path.exists()
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    assert len(registration["tested_combination_ids"]) == 81
    assert registration["tested_combination_ids_hash"] == research.canonical_json_hash(
        registration["tested_combination_ids"]
    )
    assert registration["correction_family_size"] == 720
    assert registration["global_family_size"] == 720
    assert registration["correction_family_id"] == research.canonical_json_hash(
        registration["correction_family_combination_ids"]
    )
    assert registration["partition_policy"]["correction_scope"] == "global_parameter_universe"
    assert registration["registry_record_hash"] == events[0]["registry_record_hash"]
    matrix_steps = [
        step
        for step in payload["steps"]
        if step["name"].endswith(("baseline.strategy_matrix", "candidate.strategy_matrix"))
    ]
    assert len(matrix_steps) == 2
    for step in matrix_steps:
        assert step["command"][step["command"].index("--pre-registration") + 1] == str(
            registration_path
        )
        assert step["command"][step["command"].index("--experiment-registry") + 1] == str(
            registry_path
        )


def test_consolidated_verifier_has_positive_and_synthetic_negative_checks() -> None:
    report = verifier.build_report(
        _contract(),
        base="7efda43641118f36b10261b4a04e0278bba941a2",
        candidate="5cc87798804a48046cd9698b901e2b1bc8995871",
    )

    assert report["status"] == "OK"
    names = {row["name"] for row in report["checks"]}
    categories = {
        "parameter_universe",
        "statistical_family_authority",
        "as_of_regime",
        "exact_match",
        "episode_split",
        "pre_registration",
        "sealed_reuse",
        "composition",
        "funnel",
        "coverage",
        "topic_score",
        "multiple_testing",
        "universal_gate",
        "production_no_change",
    }
    for category in categories:
        assert f"{category}.positive" in names
        assert f"{category}.synthetic_negative" in names
