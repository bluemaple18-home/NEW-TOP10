from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.research import entry_regime_cohort_feasibility as feasibility
from app.research.contracts import content_hash


def _dates(count: int) -> list[date]:
    return [date(2026, 1, 1) + timedelta(days=index) for index in range(count)]


def _scenario(dates: list[date]) -> dict[str, dict[str, object]]:
    fingerprints = {item.isoformat(): "sha256:" + f"{index:064x}" for index, item in enumerate(dates)}
    return {"candidate": {"date_fingerprints": fingerprints}}


def _regime_rows(dates: list[date]) -> list[dict[str, object]]:
    return [
        {"trade_date": item.isoformat(), "as_of_date": item.isoformat(), "base_regime": "RISK_OFF", "family_tags": []}
        for item in dates
    ]


def test_selection_uses_only_d_row_and_canonical_d1_h20_calendar() -> None:
    calendar = _dates(50)
    ranking_dates = [item.isoformat() for item in calendar[:3]]
    rows = _regime_rows(calendar)
    selections, observations, exclusions = feasibility._entry_rows(
        ranking_dates=ranking_dates,
        regime_rows=rows,
        trade_dates=calendar,
        scenarios=_scenario(calendar),
    )

    assert len(selections) == 3
    assert not exclusions
    assert observations[0]["entry_date"] == calendar[1].isoformat()
    assert observations[0]["exit_date"] == calendar[20].isoformat()

    rows[-1]["is_transition"] = True
    same_selections, same_observations, same_exclusions = feasibility._entry_rows(
        ranking_dates=ranking_dates,
        regime_rows=rows,
        trade_dates=calendar,
        scenarios=_scenario(calendar),
    )
    assert same_selections == selections
    assert same_observations == observations
    assert same_exclusions == exclusions


def test_calendar_shortfall_and_duplicate_d_row_are_structured_exclusions() -> None:
    calendar = _dates(20)
    rows = _regime_rows(calendar)
    rows.append(dict(rows[0]))
    selections, observations, exclusions = feasibility._entry_rows(
        ranking_dates=[calendar[0].isoformat(), calendar[-1].isoformat()],
        regime_rows=rows,
        trade_dates=calendar,
        scenarios=_scenario(calendar),
    )

    assert len(selections) == 1
    assert observations == []
    assert exclusions == [
        {"ranking_date": calendar[0].isoformat(), "reason_code": "D_REGIME_DUPLICATE"},
        {"ranking_date": calendar[-1].isoformat(), "reason_code": "ENTRY_D1_MISSING"},
    ]


def test_overlap_components_are_transitive_and_closed_interval() -> None:
    rows = [
        {"ranking_date": "2026-01-01", "scenario": "candidate", "entry_cohort_id": "A", "entry_date": "2026-01-02", "exit_date": "2026-01-04", "portfolio_fingerprint": "a"},
        {"ranking_date": "2026-01-02", "scenario": "candidate", "entry_cohort_id": "A", "entry_date": "2026-01-04", "exit_date": "2026-01-06", "portfolio_fingerprint": "b"},
        {"ranking_date": "2026-01-03", "scenario": "candidate", "entry_cohort_id": "A", "entry_date": "2026-01-06", "exit_date": "2026-01-08", "portfolio_fingerprint": "c"},
    ]

    components = feasibility.overlap_components(rows)

    assert len(components) == 1
    assert components[0]["observation_count"] == 3


def test_portfolio_alias_is_rejected() -> None:
    rows = [
        {"ranking_date": "2026-01-01", "scenario": "candidate", "entry_cohort_id": "A", "entry_date": "2026-01-02", "exit_date": "2026-01-04", "portfolio_fingerprint": "a"},
        {"ranking_date": "2026-01-01", "scenario": "candidate", "entry_cohort_id": "A", "entry_date": "2026-01-02", "exit_date": "2026-01-04", "portfolio_fingerprint": "b"},
    ]

    with pytest.raises(feasibility.EntryCohortFeasibilityError, match="PORTFOLIO_ALIAS_CONFLICT"):
        feasibility.overlap_components(rows)


def test_global_split_purges_both_boundaries_with_twenty_trade_day_embargo() -> None:
    calendar = _dates(180)
    selections, observations, exclusions = feasibility._entry_rows(
        ranking_dates=[item.isoformat() for item in calendar[:140]],
        regime_rows=_regime_rows(calendar),
        trade_dates=calendar,
        scenarios=_scenario(calendar),
    )
    assert exclusions == []

    split = feasibility.build_global_split(selections, observations, calendar)

    assert split["status"] == "ALLOCATED"
    assert [item["embargo_trade_days"] for item in split["boundaries"]] == [20, 20]
    for item in split["roles"]["development"]:
        assert item["exit_date"] < split["boundaries"][0]["cutoff"]
    for item in split["roles"]["validation"]:
        assert item["entry_date"] > split["boundaries"][0]["cutoff"]
        assert item["exit_date"] < split["boundaries"][1]["cutoff"]
    for item in split["roles"]["sealed"]:
        assert item["entry_date"] > split["boundaries"][1]["cutoff"]


def test_validator_rejects_false_go_and_outcome_metric() -> None:
    payload = {
        "schema_version": feasibility.SCHEMA_VERSION,
        "audit_id": "",
        "status": "FEASIBLE_FOR_PREREGISTRATION",
        "reason_codes": [],
        "contract": {
            "research_only": True,
            "horizon_trade_bars": 20,
            "entry_delay_trade_days": 1,
            "future_path_controls_selection": False,
            "old_episode_split_reuse_allowed": False,
            "sealed_outcome_access_allowed": False,
        },
        "sources": {"ranking_manifest": {"provenance_complete": False}},
        "split": {"schema_version": "entry-cohort-calendar-split.v1", "status": "INSUFFICIENT_GLOBAL_DATES", "roles": {}, "selection_roles": {}, "boundaries": [], "metric": "sharpe"},
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})

    errors = feasibility.validate_audit(payload)

    assert "FALSE_GO_PROVENANCE_INCOMPLETE" in errors
    assert "OUTCOME_METRIC_FORBIDDEN" in errors


def test_manifest_rejects_scenario_date_mismatch() -> None:
    availability_payload = {
        "sources": {
            "ranking_roots": {
                "baseline": {
                    "status": "AVAILABLE", "sha256": "sha256:baseline", "ranking_dates": ["2026-01-01"],
                    "files": [{"path": "ranking_2026-01-01.csv", "sha256": "sha256:a"}],
                },
                "candidate": {
                    "status": "AVAILABLE", "sha256": "sha256:candidate", "ranking_dates": ["2026-01-02"],
                    "files": [{"path": "ranking_2026-01-02.csv", "sha256": "sha256:b"}],
                },
            }
        }
    }

    with pytest.raises(feasibility.EntryCohortFeasibilityError, match="RANKING_MANIFEST_SCENARIO_DATE_CONFLICT"):
        feasibility._manifest(availability_payload)


def test_validator_rejects_synthetic_go_without_capacity_or_authoritative_split() -> None:
    payload = {
        "schema_version": feasibility.SCHEMA_VERSION,
        "audit_id": "",
        "status": "FEASIBLE_FOR_PREREGISTRATION",
        "reason_codes": [],
        "contract": {
            "research_only": True, "horizon_trade_bars": 20, "entry_delay_trade_days": 1,
            "future_path_controls_selection": False, "old_episode_split_reuse_allowed": False,
            "sealed_outcome_access_allowed": False,
        },
        "sources": {
            "architecture_decision": {"commit_status": "MATCHED"},
            "availability_manifest": {"commit_status": "MATCHED"},
            "reconciliation": {"commit_status": "MATCHED"},
            "ranking_manifest": {"provenance_complete": True},
        },
        "split": {
            "schema_version": "entry-cohort-calendar-split.v1", "status": "ALLOCATED", "authoritative": False,
            "roles": {role: [] for role in feasibility.ROLES},
            "selection_role_counts": {role: 0 for role in feasibility.ROLES},
            "boundaries": [{"embargo_trade_days": 20}, {"embargo_trade_days": 20}],
        },
        "family": {"predeclared_scenarios": ["candidate"], "predeclared_cohorts": ["A"], "family_size": 1, "minimum_independent_components": 20},
        "capacity": {"A": {role: {"independent_component_count": 0} for role in feasibility.ROLES}},
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})

    errors = feasibility.validate_audit(payload)

    assert "FALSE_GO_SPLIT_NOT_AUTHORITATIVE" in errors
    assert "FALSE_GO_CAPACITY_INVALID" in errors


def test_module_does_not_reuse_old_episode_split_or_scan_ranking_roots() -> None:
    source = feasibility.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()

    assert "build_regime_episode_split" not in text
    assert "RANKING_ROOTS" not in text
