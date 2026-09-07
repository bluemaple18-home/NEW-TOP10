from dataclasses import replace

import pandas as pd
import pytest

from app.signals.specs import (
    DAILY_CLOSE_DATASET_CONTRACT,
    INITIAL_SIGNAL_SPECS,
    SignalCalendarPolicy,
    SignalDirection,
    SignalEligibilityStatus,
    SignalEvaluationState,
    SignalSpec,
    SignalSpecContractError,
    radar_eligible_signal_specs,
    resolve_signal_evaluation,
    validate_signal_parity,
)


def _signal_values() -> dict[str, list[int]]:
    return {
        "ma5_cross_ma20_up": [0, 0, 1, 0],
        "ma5_cross_ma20_down": [0, 0, 0, 0],
        "rsi_rebound_from_40": [0, 0, 0, 1],
        "rsi_break_below_50": [0, 0, 0, 0],
    }


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-08-31", "2026-08-31", "2026-09-01", "2026-09-01"]
            ),
            "stock_id": ["2330", "6488", "2330", "6488"],
            "ma5": [98.0, 78.0, 100.0, 80.0],
            "ma20": [99.0, 79.0, 99.0, None],
            "rsi": [50.0, 39.0, 55.0, 41.0],
            **_signal_values(),
        }
    )


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-08-31", "2026-08-31", "2026-09-01", "2026-09-01"]
            ),
            "stock_id": ["2330", "6488", "2330", "6488"],
            **_signal_values(),
        }
    )


def _assert_reason(reason_code: str, callback) -> None:
    with pytest.raises(SignalSpecContractError) as caught:
        callback()
    assert caught.value.reason_code == reason_code


def test_signal_spec_identity_is_stable_and_covers_semantics() -> None:
    spec = INITIAL_SIGNAL_SPECS["ma5_cross_ma20_up"]

    assert replace(spec).spec_content_id == spec.spec_content_id
    assert (
        replace(
            spec, calendar_policy=SignalCalendarPolicy.PREVIOUS_OBSERVED_ROW
        ).spec_content_id
        != spec.spec_content_id
    )
    assert replace(spec, required_features=("ma5",)).spec_content_id != spec.spec_content_id
    assert replace(spec, required_history_sessions=2).spec_content_id != spec.spec_content_id
    assert replace(spec, rule_expression="different semantics").spec_content_id != spec.spec_content_id


def test_initial_catalog_is_bounded_and_not_radar_eligible() -> None:
    assert tuple(INITIAL_SIGNAL_SPECS) == (
        "ma5_cross_ma20_up",
        "ma5_cross_ma20_down",
        "rsi_rebound_from_40",
        "rsi_break_below_50",
    )
    assert radar_eligible_signal_specs() == ()

    for signal_id, spec in INITIAL_SIGNAL_SPECS.items():
        assert spec.signal_id == signal_id
        assert spec.required_dataset_contract == DAILY_CLOSE_DATASET_CONTRACT
        assert spec.required_features
        assert spec.required_history_sessions == 1
        assert spec.rule_reference
        assert spec.rule_expression
        assert spec.signal_column == signal_id
        assert spec.eligibility_status is SignalEligibilityStatus.CONTRACT_ONLY
        assert spec.evaluation_horizon_days is None
        assert spec.research_evidence_ref is None


def test_radar_eligible_spec_requires_horizon_and_research_evidence() -> None:
    _assert_reason(
        "RADAR_ELIGIBILITY_EVIDENCE_INCOMPLETE",
        lambda: SignalSpec(
            signal_id="example_signal",
            signal_version="1.0.0",
            name="測試訊號",
            category="test",
            direction=SignalDirection.BULLISH,
            signal_column="example_signal",
            rule_reference="example.module:rule",
            rule_expression="close[t] > close[t-1]",
            calendar_policy=SignalCalendarPolicy.DATASET_SESSION_CONTIGUOUS,
            required_features=("close",),
            required_history_sessions=0,
            required_dataset_contract=DAILY_CLOSE_DATASET_CONTRACT,
            evaluation_horizon_days=None,
            regime_applicability="UNASSESSED",
            research_evidence_ref=None,
            eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
            educational_explanation_ref=None,
        ),
    )


def test_signal_spec_rejects_non_daily_dataset_contract() -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    _assert_reason(
        "SIGNAL_DATASET_CONTRACT_UNSUPPORTED",
        lambda: replace(spec, required_dataset_contract="intraday.v1"),
    )


def test_signal_spec_rejects_mutable_required_features() -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    _assert_reason(
        "SIGNAL_REQUIRED_FEATURES_TYPE_INVALID",
        lambda: replace(spec, required_features=["rsi"]),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("rule_result", "expected"),
    [(1, SignalEvaluationState.TRIGGERED), (True, SignalEvaluationState.TRIGGERED), (0, SignalEvaluationState.NOT_TRIGGERED), (False, SignalEvaluationState.NOT_TRIGGERED)],
)
def test_resolver_returns_triggered_or_not_triggered(rule_result, expected) -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    result = resolve_signal_evaluation(spec, rule_result=rule_result)

    assert result.state is expected
    assert result.reason_code is None
    assert result.unavailable_features == ()


def test_resolver_reports_required_feature_unavailable() -> None:
    spec = INITIAL_SIGNAL_SPECS["ma5_cross_ma20_up"]

    result = resolve_signal_evaluation(
        spec,
        rule_result=0,
        unavailable_features=("ma20", "ma5", "ma20"),
    )

    assert result.state is SignalEvaluationState.NOT_OBSERVABLE
    assert result.reason_code == "REQUIRED_FEATURE_UNAVAILABLE"
    assert result.unavailable_features == ("ma5", "ma20")


def test_resolver_reports_missing_rule_result_and_evaluation_error() -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    unavailable = resolve_signal_evaluation(spec, rule_result=None)
    failed = resolve_signal_evaluation(
        spec,
        rule_result=0,
        evaluation_error="indicator calculation failed",
    )

    assert unavailable.state is SignalEvaluationState.NOT_OBSERVABLE
    assert unavailable.reason_code == "RULE_RESULT_UNAVAILABLE"
    assert failed.state is SignalEvaluationState.NOT_OBSERVABLE
    assert failed.reason_code == "RULE_EVALUATION_ERROR"
    assert failed.detail == "indicator calculation failed"


def test_resolver_reports_required_history_unavailable() -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    result = resolve_signal_evaluation(
        spec,
        rule_result=0,
        history_available=False,
    )

    assert result.state is SignalEvaluationState.NOT_OBSERVABLE
    assert result.reason_code == "REQUIRED_HISTORY_UNAVAILABLE"


def test_resolver_rejects_non_binary_result() -> None:
    spec = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]

    _assert_reason(
        "RULE_RESULT_INVALID",
        lambda: resolve_signal_evaluation(spec, rule_result=2),
    )


def test_parity_validator_reports_observability_without_mutating_inputs() -> None:
    features = _features()
    events = _events().iloc[::-1].reset_index(drop=True)
    before_features = features.copy(deep=True)
    before_events = events.copy(deep=True)

    report = validate_signal_parity(features, events)

    assert report.row_count == 4
    assert report.signal_count == 4
    assert report.radar_eligible_signal_count == 0
    assert report.catalog_status == "CONTRACT_ONLY_PARITY_VERIFIED"
    by_id = {row.signal_id: row for row in report.signal_results}
    assert by_id["ma5_cross_ma20_up"].observable_rows == 1
    assert by_id["ma5_cross_ma20_up"].unobservable_rows == 3
    assert by_id["rsi_rebound_from_40"].observable_rows == 2
    assert by_id["rsi_rebound_from_40"].unobservable_rows == 2
    assert all(row.mismatch_count == 0 for row in report.signal_results)
    warnings = {
        (row.signal_id, row.reason_code): row.affected_rows
        for row in report.warnings
    }
    assert warnings[("ma5_cross_ma20_up", "REQUIRED_FEATURE_UNAVAILABLE")] == 1
    assert warnings[("ma5_cross_ma20_up", "REQUIRED_HISTORY_UNAVAILABLE")] == 2
    assert warnings[("rsi_rebound_from_40", "REQUIRED_HISTORY_UNAVAILABLE")] == 2
    pd.testing.assert_frame_equal(features, before_features)
    pd.testing.assert_frame_equal(events, before_events)


def test_calendar_policy_changes_history_observability() -> None:
    base = INITIAL_SIGNAL_SPECS["rsi_rebound_from_40"]
    dataset_session_spec = replace(base)
    previous_observation_spec = replace(
        base,
        calendar_policy=SignalCalendarPolicy.PREVIOUS_OBSERVED_ROW,
    )
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-31", "2026-09-01", "2026-09-02"]),
            "stock_id": ["2330", "6488", "2330"],
            "rsi": [39.0, 55.0, 41.0],
            "rsi_rebound_from_40": [0, 0, 1],
        }
    )
    events = features[["date", "stock_id", "rsi_rebound_from_40"]].copy()

    dataset_report = validate_signal_parity(
        features,
        events,
        specs=(dataset_session_spec,),
    )
    observation_report = validate_signal_parity(
        features,
        events,
        specs=(previous_observation_spec,),
    )

    assert dataset_report.signal_results[0].observable_rows == 0
    assert observation_report.signal_results[0].observable_rows == 1


@pytest.mark.parametrize(
    ("reason_code", "mutate"),
    [
        (
            "PARITY_DUPLICATE_KEY",
            lambda features, events: (
                pd.concat([features, features.iloc[[0]]], ignore_index=True),
                events,
            ),
        ),
        (
            "PARITY_KEY_DRIFT",
            lambda features, events: (
                features,
                events.assign(stock_id=["2330", "6488", "2330", "9999"]),
            ),
        ),
        (
            "PARITY_SIGNAL_COLUMN_MISSING",
            lambda features, events: (
                features,
                events.drop(columns=["rsi_rebound_from_40"]),
            ),
        ),
        (
            "PARITY_REQUIRED_FEATURE_MISSING",
            lambda features, events: (features.drop(columns=["rsi"]), events),
        ),
        (
            "PARITY_SIGNAL_VALUE_INVALID",
            lambda features, events: (
                features,
                events.assign(rsi_rebound_from_40=[0, 0, 0, 2]),
            ),
        ),
        (
            "PARITY_SIGNAL_DRIFT",
            lambda features, events: (
                features,
                events.assign(rsi_rebound_from_40=[0, 0, 1, 1]),
            ),
        ),
    ],
)
def test_parity_validator_fails_closed(reason_code, mutate) -> None:
    features, events = mutate(_features(), _events())

    _assert_reason(
        reason_code,
        lambda: validate_signal_parity(features, events),
    )


def test_parity_validator_rejects_null_key() -> None:
    features = _features()
    features.loc[0, "stock_id"] = None

    _assert_reason(
        "PARITY_KEY_NULL",
        lambda: validate_signal_parity(features, _events()),
    )
