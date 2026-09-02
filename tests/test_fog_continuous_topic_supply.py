from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from scripts import run_autonomous_research as research


EXACT = {
    "base_regime": "BROAD_RISK_ON",
    "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
}


def _history_rows() -> list[dict]:
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
        for _ in range(24):
            rows.append(
                {
                    "trade_date": cursor.isoformat(),
                    "as_of_date": cursor.isoformat(),
                    **EXACT,
                }
            )
            cursor += timedelta(days=1)
    return rows


def _fixture(tmp_path: Path, monkeypatch):
    contract_path = research.PROJECT_ROOT / "config/regime_research_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    history_rows = _history_rows()
    history_path = tmp_path / "market_regime_history.json"
    history_path.write_text(json.dumps({"rows": history_rows}), encoding="utf-8")
    allowed_dates = research.canonical_exact_regime_allowed_dates(
        rows=history_rows,
        contract=contract,
        regime_identity=EXACT,
        horizons="3",
        as_of_date=history_rows[-1]["trade_date"],
    )
    ranking_date = sorted(allowed_dates)[0]
    candidate_dir = tmp_path / "artifacts" / "backtest" / "candidate"
    baseline_dir = tmp_path / "artifacts" / "backtest" / "baseline"
    candidate_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)
    for directory in (candidate_dir, baseline_dir):
        (directory / f"ranking_{ranking_date}.csv").write_text(
            "rank,stock_id\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(research, "PROJECT_ROOT", tmp_path)
    template = research.ResearchTopic(
        topic_id="strategy-matrix:fixture",
        title="fixture",
        hypothesis="fixture",
        validation_plan="fixture",
        runner="strategy_matrix_comparison",
        candidate_dir="artifacts/backtest/candidate",
        baseline_dir="artifacts/backtest/baseline",
        score=1.0,
        reasons=[],
        evidence_sources=["artifacts/backtest/candidate"],
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
    args = SimpleNamespace(
        date=history_rows[-1]["trade_date"],
        research_contract=str(contract_path),
        market_regime_history=str(history_path),
        coverage_map=None,
        development_screen_topic_count=2,
    )
    return template, args, contract


def _main_args(tmp_path: Path, supply_args: SimpleNamespace):
    return SimpleNamespace(
        date=supply_args.date,
        output=str(tmp_path / "run.json"),
        features="data/clean/features.parquet",
        baseline_dir="artifacts/backtest/baseline",
        candidate_dir=None,
        topic_index=0,
        max_topics=12,
        min_ranking_files=1,
        max_ranking_files=8,
        horizons="3,5,10",
        stop_loss_pcts="none,0.08,0.12",
        take_profit_pcts="none,0.15,0.25",
        max_group_exposures="none,0.35,0.55",
        execute=False,
        execute_topic_count=2,
        from_queue=False,
        rerun=False,
        include_rejected=False,
        no_manager_update=True,
        closed_regime_research=True,
        development_screen_on_sealed_exhaustion=True,
        development_screen_topic_count=2,
        market_regime_history=supply_args.market_regime_history,
        research_contract=supply_args.research_contract,
        coverage_map=supply_args.coverage_map,
    )


def test_supply_creates_stable_novel_development_topics_and_four_way_dedupe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, args, _contract = _fixture(tmp_path, monkeypatch)

    first_topics, first_receipt = research.replenish_development_topics(
        [template],
        args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=4,
    )
    known_ids = [topic.topic_id for topic in first_topics]
    assert len(known_ids) == 4
    assert len(set(known_ids)) == 4
    assert first_receipt["status"] == "TOPICS_SUPPLIED"
    assert all(
        research.topic_research_stage(topic) == research.DEVELOPMENT_SCREEN_STAGE
        for topic in first_topics
    )
    assert all(
        topic.selection_rationale["development_contract"][
            "experiment_registry_write_allowed"
        ]
        is False
        for topic in first_topics
    )
    repeated_topics, _repeated_receipt = research.replenish_development_topics(
        [replace(template)],
        args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=4,
    )
    assert [topic.topic_id for topic in repeated_topics] == known_ids

    next_topics, next_receipt = research.replenish_development_topics(
        [replace(template)],
        args,
        registry_rows={known_ids[0]: {"topic_id": known_ids[0]}},
        history_rows=[{"selected_topic_ids": [known_ids[1]]}],
        queue_rows=[{"topic_id": known_ids[2]}],
        same_round_ids={known_ids[3]},
        limit=4,
    )

    assert not set(known_ids) & {topic.topic_id for topic in next_topics}
    assert next_receipt["exclusion_counts"]["registry_duplicate"] >= 1
    assert next_receipt["exclusion_counts"]["history_duplicate"] >= 1
    assert next_receipt["exclusion_counts"]["queue_duplicate"] >= 1
    assert next_receipt["exclusion_counts"]["same_round_duplicate"] >= 1


def test_supply_rechecks_single_horizon_when_broad_profile_authority_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, args, _contract = _fixture(tmp_path, monkeypatch)
    broad_profile_rejected = replace(
        template,
        eligible=False,
        reason_code="MISSING_EXACT_REGIME_AUTHORITY",
    )

    topics, receipt = research.replenish_development_topics(
        [broad_profile_rejected],
        args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=1,
    )

    assert receipt["status"] == "TOPICS_SUPPLIED"
    assert len(topics) == 1
    assert topics[0].horizons == "3"


def test_supply_reports_exhaustion_with_reason_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, args, contract = _fixture(tmp_path, monkeypatch)
    regime_id = research.regime_identity_id(EXACT)
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "regime_id": regime_id,
                        "combination_id": row["combination_id"],
                        "status": "REJECTED",
                    }
                    for row in research.parameter_combinations(contract)
                ]
            }
        ),
        encoding="utf-8",
    )
    args.coverage_map = str(coverage_path)

    topics, receipt = research.replenish_development_topics(
        [template],
        args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=2,
    )

    assert topics == []
    assert receipt["status"] == "TOPIC_SUPPLY_EXHAUSTED"
    assert receipt["exclusion_counts"]["coverage_processed"] == 720
    assert receipt["candidate_count"] == 720
    assert receipt["evidence_refs"]["research_contract"]
    assert receipt["evidence_refs"]["coverage_map"]


def test_multi_template_no_exact_date_uses_cached_budgeted_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, args, _contract = _fixture(tmp_path, monkeypatch)
    templates = [
        replace(template, topic_id=f"strategy-matrix:fixture:{index}")
        for index in range(3)
    ]
    call_count = 0

    def fake_eligibility(**_kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "eligible": False,
            "reason_code": "NO_EXACT_REGIME_RANKING_DATE",
            "candidate_exact_date_count": 0,
            "baseline_exact_date_count": 0,
        }

    monkeypatch.setattr(
        research,
        "exact_regime_topic_ranking_eligibility",
        fake_eligibility,
    )

    topics, receipt = research.replenish_development_topics(
        templates,
        args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=1,
    )

    assert topics == []
    assert receipt["status"] == "TOPIC_SUPPLY_EXHAUSTED"
    assert receipt["candidate_count"] == 720
    assert receipt["attempt_budget"] < 2160
    assert receipt["ranking_eligibility_cache_misses"] <= receipt["attempt_budget"]
    assert receipt["ranking_eligibility_cache_hits"] > 0
    assert call_count == receipt["ranking_eligibility_cache_misses"]
    assert call_count <= 720


def test_main_reports_true_supply_exhaustion_and_exits_zero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, supply_args, _contract = _fixture(tmp_path, monkeypatch)
    args = _main_args(tmp_path, supply_args)
    receipt = {
        "status": "TOPIC_SUPPLY_EXHAUSTED",
        "candidate_count": 720,
        "supplied_count": 0,
        "exclusion_counts": {"coverage_processed": 720},
        "evidence_refs": {"research_contract": "config/regime_research_contract.json"},
    }
    captured: dict = {}
    monkeypatch.setattr(research, "parse_args", lambda: args)
    monkeypatch.setattr(research, "build_daily_source_lineage", lambda **_kwargs: {})
    monkeypatch.setattr(research, "generate_all_topics", lambda _args: [template])
    monkeypatch.setattr(
        research,
        "apply_closed_experiment_capacity",
        lambda topics, _args: topics,
    )
    monkeypatch.setattr(
        research,
        "select_topics_for_run",
        lambda _topics, _args, **_kwargs: [],
    )
    monkeypatch.setattr(
        research,
        "replenish_development_topics",
        lambda *_args, **_kwargs: ([], receipt),
    )
    monkeypatch.setattr(
        research,
        "write_topic_bank",
        lambda *_args, **_kwargs: tmp_path / "topic_bank.json",
    )
    monkeypatch.setattr(research, "queued_topic_ids", lambda: set())
    monkeypatch.setattr(
        research,
        "write_run_artifacts",
        lambda payload, _output: captured.update(payload),
    )

    assert research.main() == 0
    assert captured["status"] == "OK"
    assert captured["outcome"]["decision"] == "TOPIC_SUPPLY_EXHAUSTED"
    assert captured["outcome"]["topic_supply"]["exclusion_counts"][
        "coverage_processed"
    ] == 720


def test_main_preserves_attempt_budget_exceeded_topic_supply_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, supply_args, _contract = _fixture(tmp_path, monkeypatch)
    args = _main_args(tmp_path, supply_args)
    receipt = {
        "status": "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED",
        "candidate_count": 720,
        "supplied_count": 0,
        "attempt_budget": 1,
        "attempt_budget_exhausted": True,
        "reason_code": "ATTEMPT_BUDGET_EXCEEDED",
        "exclusion_counts": {"no_exact_regime_ranking_date": 1},
        "evidence_refs": {"research_contract": "config/regime_research_contract.json"},
    }
    captured: dict = {}
    monkeypatch.setattr(research, "parse_args", lambda: args)
    monkeypatch.setattr(research, "build_daily_source_lineage", lambda **_kwargs: {})
    monkeypatch.setattr(research, "generate_all_topics", lambda _args: [template])
    monkeypatch.setattr(
        research,
        "apply_closed_experiment_capacity",
        lambda topics, _args: topics,
    )
    monkeypatch.setattr(
        research,
        "select_topics_for_run",
        lambda _topics, _args, **_kwargs: [],
    )
    monkeypatch.setattr(
        research,
        "replenish_development_topics",
        lambda *_args, **_kwargs: ([], receipt),
    )
    monkeypatch.setattr(
        research,
        "write_topic_bank",
        lambda *_args, **_kwargs: tmp_path / "topic_bank.json",
    )
    monkeypatch.setattr(research, "queued_topic_ids", lambda: set())
    monkeypatch.setattr(
        research,
        "write_run_artifacts",
        lambda payload, _output: captured.update(payload),
    )

    assert research.main() == 0
    assert captured["status"] == "OK"
    assert captured["outcome"]["decision"] == "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"
    assert captured["outcome"]["topic_supply"] == receipt


def test_main_replenishes_when_existing_queue_and_active_routes_are_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, supply_args, _contract = _fixture(tmp_path, monkeypatch)
    args = _main_args(tmp_path, supply_args)
    captured: dict = {}
    existing_registry = {
        template.topic_id: {
            "topic_id": template.topic_id,
            "manager_status": "rejected",
            "run_count": 1,
        }
    }
    original_replenish = research.replenish_development_topics
    monkeypatch.setattr(research, "parse_args", lambda: args)
    monkeypatch.setattr(research, "build_daily_source_lineage", lambda **_kwargs: {})
    monkeypatch.setattr(research, "generate_all_topics", lambda _args: [template])
    monkeypatch.setattr(
        research,
        "apply_closed_experiment_capacity",
        lambda topics, _args: topics,
    )
    monkeypatch.setattr(research, "load_topic_registry", lambda: existing_registry)
    monkeypatch.setattr(research, "load_last_run_at_by_topic", lambda: {})
    monkeypatch.setattr(research, "load_next_action_queue", lambda: [])
    monkeypatch.setattr(research, "queued_topic_ids", lambda: set())
    monkeypatch.setattr(
        research,
        "replenish_development_topics",
        lambda templates, supply_args, **kwargs: original_replenish(
            templates,
            supply_args,
            registry_rows=existing_registry,
            history_rows=[],
            queue_rows=[],
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        research,
        "write_topic_bank",
        lambda *_args, **_kwargs: tmp_path / "topic_bank.json",
    )
    monkeypatch.setattr(
        research,
        "write_run_artifacts",
        lambda payload, _output: captured.update(payload),
    )

    assert research.main() == 0
    assert captured["outcome"]["topic_supply"]["status"] == "TOPICS_SUPPLIED"
    assert captured["selected_topics"]
    assert all(
        row["reason_code"] == "DEVELOPMENT_SCREEN_ONLY"
        for row in captured["selected_topics"]
    )


def test_supplied_topic_keeps_development_only_episode_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    template, supply_args, _contract = _fixture(tmp_path, monkeypatch)
    topics, _receipt = research.replenish_development_topics(
        [template],
        supply_args,
        registry_rows={},
        history_rows=[],
        queue_rows=[],
        same_round_ids=set(),
        limit=1,
    )
    topic = topics[0]
    lineage = {
        "dataset_hash": "sha256:dataset",
        "split_id": "sha256:split",
        "split_artifact_hash": "sha256:split-artifact",
        "development_episode_ids": ["sha256:development-1"],
        "validation_episode_ids": ["sha256:validation"],
        "embargo_episode_ids": ["sha256:embargo"],
        "sealed_episode_ids": ["sha256:sealed"],
        "sealed_trade_date_hash": "sha256:sealed-dates",
    }
    monkeypatch.setattr(
        research,
        "closed_experiment_context",
        lambda _args, _topic: {
            "lineage": lineage,
            "regime_id": research.regime_identity_id(EXACT),
        },
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    args = SimpleNamespace(
        features="data/clean/features.parquet",
        max_ranking_files=8,
        horizons="3,5,10",
        stop_loss_pcts="none,0.08,0.12",
        take_profit_pcts="none,0.15,0.25",
        max_group_exposures="none,0.35,0.55",
        closed_regime_research=True,
        market_regime_history=supply_args.market_regime_history,
    )

    development = research.prepare_development_screen(args, topic, run_dir)
    command = research.matrix_command(
        args,
        topic.candidate_dir,
        str(run_dir / "matrix.json"),
        topic,
        allowed_episode_ids=development["development_episode_ids"],
        research_stage=research.DEVELOPMENT_SCREEN_STAGE,
    )

    assert development["contract"]["excluded_episode_ids"] == {
        "validation": ["sha256:validation"],
        "embargo": ["sha256:embargo"],
        "sealed": ["sha256:sealed"],
    }
    assert development["contract"]["boundary"][
        "experiment_registry_write_allowed"
    ] is False
    assert "--development-only" in command
    assert "--pre-registration" not in command
    assert "--experiment-registry" not in command
