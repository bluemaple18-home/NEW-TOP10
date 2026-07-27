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
    contract["taxonomy"]["required_universal_regime_ids"] = [
        "BROAD_RISK_ON|BIG_BULL",
        "RISK_OFF|",
    ]
    return contract


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
    gate = research.multiple_testing_gate(gate_candidates)

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
        contract=_universal_contract(),
    )

    assert result == {"unlocked": False, "reason_code": "PARAMETER_UNIVERSE_INCOMPLETE"}


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
        "trades": [{"net_return": value} for value in (0.03, 0.04, 0.02, -0.01)],
    }

    row = matrix.matrix_row(scenario, replay)

    assert row["combination_id"] == research.canonical_json_hash(scenario)
    assert row["p_value"] is not None
    assert row["robust_neighbor_lineage"] == []
    assert row["robust_neighbor_pass_count"] == 0
    assert row["drawdown_within_limit"] is True
    matrix.annotate_statistical_lineage([row])
    gate = research.multiple_testing_gate([row])
    assert gate["evidence_complete"] is True
    assert gate["reason_code"] == "MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED"


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
        horizons="3",
        stop_loss_pcts="none",
        take_profit_pcts="none",
        max_group_exposures="none",
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
        horizons="3",
        stop_loss_pcts="none",
        take_profit_pcts="none",
        max_group_exposures="none",
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
    assert [event.get("target_state") for event in events[1:]] == ["COARSE_SCREEN", "BLOCKED"]
    assert Path(payload["outputs"]["closed_episode_split"]).exists()
    assert Path(payload["outputs"]["closed_pre_registration"]).exists()


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
