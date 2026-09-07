"""RADAR-01 P1-D 唯讀歷史統計與 relevant base-rate projection。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from numbers import Real
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.research.contracts import content_hash

from .scanner import DailySignalScannerError, _load_validated_signal_history
from .specs import (
    SignalCalendarPolicy,
    SignalDirection,
    SignalEligibilityStatus,
    SignalSpec,
)


HISTORICAL_STATISTICS_CONTRACT_VERSION = "signal-historical-statistics.v1"
OUTCOME_POLICY_VERSION = "observed-session-direction-adjusted-price-return.v1"
EFFECTIVE_SAMPLE_POLICY = "PER_INSTRUMENT_NON_OVERLAPPING_FORWARD_WINDOWS_V1"
PRICE_RETURN_BASIS = "UNADJUSTED_PRICE_RETURN"
_KEY_COLUMNS = ("date", "stock_id")
_QUANTILES = (0.05, 0.25, 0.75, 0.95)


class HistoricalStatisticsError(ValueError):
    """P1-D input 或統計契約無法安全判讀時使用的穩定錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class HistoricalStatisticsStatus(str, Enum):
    """歷史統計 projection 的可用狀態。"""

    COMPLETE = "COMPLETE"
    COMPLETE_WITH_EXCLUSIONS = "COMPLETE_WITH_EXCLUSIONS"
    NO_RADAR_ELIGIBLE_SIGNAL_SPEC = "NO_RADAR_ELIGIBLE_SIGNAL_SPEC"


@dataclass(frozen=True)
class HistoricalStatisticsWarning:
    """被排除或不可觀測資料的穩定、可搜尋證據。"""

    record_key: str
    signal_id: str | None
    reason_code: str
    stage: str
    affected_count: int


@dataclass(frozen=True)
class HistoricalUniverse:
    """本次 baseline 與 conditional 共用的 exact universe。"""

    markets: tuple[str, ...]
    instrument_count: int
    instrument_ids: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalCoverage:
    """Signal 三態與 outcome tail 的完整覆蓋帳。"""

    evaluated_rows: int
    triggered_rows: int
    not_triggered_rows: int
    not_observable_rows: int
    triggered_complete_outcomes: int
    triggered_outcome_incomplete_rows: int
    baseline_complete_outcomes: int
    baseline_outcome_incomplete_rows: int


@dataclass(frozen=True)
class QuantileEstimate:
    """固定 quantile policy 的單一估計值。"""

    probability: float
    value: float | None


@dataclass(frozen=True)
class HistoricalSampleStatistics:
    """以 effective sample 計算的方向調整後分布摘要。"""

    raw_sample_size: int
    effective_sample_size: int
    event_date_count: int
    overlap_count: int
    direction_positive_rate: float | None
    mean_return: float | None
    median_return: float | None
    return_quantiles: tuple[QuantileEstimate, ...]
    downside_count: int
    downside_rate: float | None
    downside_mean_return: float | None
    maximum_adverse_excursion_mean: float | None
    maximum_adverse_excursion_median: float | None
    maximum_adverse_excursion_quantiles: tuple[QuantileEstimate, ...]


@dataclass(frozen=True)
class IncrementalEdge:
    """Conditional 相對同窗 relevant baseline 的可重算差值。"""

    direction_positive_rate_percentage_points: float | None
    mean_return_edge: float | None
    median_return_edge: float | None


@dataclass(frozen=True)
class SignalHistoricalStatistics:
    """單一 exact SignalSpec 的歷史統計。"""

    signal_id: str
    signal_version: str
    spec_content_id: str
    direction: str
    forward_horizon_sessions: int
    research_evidence_ref: str
    regime_applicability: str
    regime_match: str
    coverage: HistoricalCoverage
    conditional: HistoricalSampleStatistics
    baseline: HistoricalSampleStatistics
    incremental_edge: IncrementalEdge


@dataclass(frozen=True)
class SignalHistoricalStatisticsReport:
    """Immutable、content-addressed、無 ranking authority 的 P1-D read-model。"""

    contract_version: str
    status: HistoricalStatisticsStatus
    snapshot_id: str
    records_content_id: str
    feature_artifact_content_id: str
    indicator_semantics_ref: str
    source_provenance_content_id: str
    sample_window_start: str
    sample_window_end: str
    universe: HistoricalUniverse
    price_return_basis: str
    currency: str
    dividend_assumption: str
    fees_assumption: str
    tax_assumption: str
    research_status: str
    oos_status: str
    sealed_status: str
    authority_scope: str
    effective_sample_policy: str
    outcome_policy_version: str
    maximum_adverse_excursion_basis: str
    eligible_signal_count: int
    signal_statistics: tuple[SignalHistoricalStatistics, ...]
    warnings: tuple[HistoricalStatisticsWarning, ...]

    def identity_payload(self) -> dict[str, Any]:
        """回傳完整 input、policy、result 與 limitation identity。"""

        return {
            "authority_scope": self.authority_scope,
            "contract_version": self.contract_version,
            "currency": self.currency,
            "dividend_assumption": self.dividend_assumption,
            "effective_sample_policy": self.effective_sample_policy,
            "eligible_signal_count": self.eligible_signal_count,
            "feature_artifact_content_id": self.feature_artifact_content_id,
            "fees_assumption": self.fees_assumption,
            "indicator_semantics_ref": self.indicator_semantics_ref,
            "maximum_adverse_excursion_basis": self.maximum_adverse_excursion_basis,
            "oos_status": self.oos_status,
            "outcome_policy_version": self.outcome_policy_version,
            "price_return_basis": self.price_return_basis,
            "records_content_id": self.records_content_id,
            "research_status": self.research_status,
            "sample_window_end": self.sample_window_end,
            "sample_window_start": self.sample_window_start,
            "sealed_status": self.sealed_status,
            "signal_statistics": [asdict(item) for item in self.signal_statistics],
            "snapshot_id": self.snapshot_id,
            "source_provenance_content_id": self.source_provenance_content_id,
            "status": self.status.value,
            "tax_assumption": self.tax_assumption,
            "universe": asdict(self.universe),
            "warnings": [asdict(item) for item in self.warnings],
        }

    @property
    def result_content_id(self) -> str:
        """以完整 immutable read-model 計算穩定 content ID。"""

        return content_hash(self.identity_payload())


def _historical_error(reason_code: str, detail: object) -> HistoricalStatisticsError:
    return HistoricalStatisticsError(reason_code, str(detail))


def _translate_scanner_error(exc: DailySignalScannerError) -> HistoricalStatisticsError:
    suffix = exc.reason_code[5:] if exc.reason_code.startswith("SCAN_") else exc.reason_code
    return _historical_error(f"HIST_{suffix}", exc.detail)


def _materialize_explicit_specs(
    specs: Iterable[SignalSpec] | None,
) -> tuple[SignalSpec, ...] | None:
    if specs is None:
        return None
    try:
        selected = tuple(specs)
    except TypeError as exc:
        raise _historical_error(
            "HIST_SPEC_CONTAINER_INVALID", type(specs).__name__
        ) from exc
    except Exception as exc:
        raise _historical_error(
            "HIST_SPEC_CONTAINER_UNREADABLE", type(specs).__name__
        ) from exc
    for spec in selected:
        if type(spec) is not SignalSpec:
            raise _historical_error("HIST_SPEC_TYPE_INVALID", type(spec).__name__)
        if type(spec.direction) is not SignalDirection:
            raise _historical_error("HIST_DIRECTION_INVALID", repr(spec.direction))
        if type(spec.calendar_policy) is not SignalCalendarPolicy:
            raise _historical_error(
                "HIST_CALENDAR_POLICY_INVALID", repr(spec.calendar_policy)
            )
        if type(spec.eligibility_status) is not SignalEligibilityStatus:
            raise _historical_error(
                "HIST_SPEC_ELIGIBILITY_INVALID", repr(spec.eligibility_status)
            )
    return selected


def _validate_supported_specs(specs: tuple[SignalSpec, ...]) -> None:
    for spec in specs:
        if spec.signal_column in spec.required_features:
            raise _historical_error(
                "HIST_SIGNAL_COLUMN_CONFLICT",
                f"signal_id={spec.signal_id}; column={spec.signal_column}",
            )
        if spec.direction not in {SignalDirection.BULLISH, SignalDirection.BEARISH}:
            raise _historical_error(
                "HIST_DIRECTION_UNSUPPORTED",
                f"signal_id={spec.signal_id}; direction={spec.direction.value}",
            )
        horizon = spec.evaluation_horizon_days
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
            raise _historical_error(
                "HIST_EVALUATION_HORIZON_INVALID",
                f"signal_id={spec.signal_id}; horizon={horizon!r}",
            )


def _validate_required_feature_values(
    features: pd.DataFrame,
    specs: tuple[SignalSpec, ...],
) -> None:
    for feature in sorted({name for spec in specs for name in spec.required_features}):
        invalid_count = 0
        for value in features.loc[features[feature].notna(), feature]:
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
            ):
                invalid_count += 1
        if invalid_count:
            raise _historical_error(
                "HIST_REQUIRED_FEATURE_VALUE_INVALID",
                f"feature={feature}; affected_count={invalid_count}",
            )
    for spec in specs:
        values = features[spec.signal_column]
        invalid_count = int((values.notna() & ~values.isin([0, 1])).sum())
        if invalid_count:
            raise _historical_error(
                "HIST_RULE_RESULT_INVALID",
                f"signal_id={spec.signal_id}; affected_count={invalid_count}",
            )


def _aligned_history(
    snapshot_frame: pd.DataFrame,
    features: pd.DataFrame,
    spec: SignalSpec,
) -> pd.DataFrame:
    ordered = snapshot_frame.sort_values(
        ["stock_id", "date"], kind="mergesort"
    ).reset_index(drop=True)
    semantic_columns = [*spec.required_features, spec.signal_column]
    indexed_features = features.set_index(list(_KEY_COLUMNS))
    snapshot_index = pd.MultiIndex.from_frame(ordered.loc[:, list(_KEY_COLUMNS)])
    aligned = indexed_features.loc[:, semantic_columns].reindex(snapshot_index)
    aligned.index = ordered.index
    output = pd.concat(
        [
            ordered.loc[:, ["date", "stock_id", "market", "close", "high", "low"]],
            aligned,
        ],
        axis=1,
    )
    output["_feature_row_present"] = snapshot_index.isin(indexed_features.index)
    output["_instrument_position"] = output.groupby(
        "stock_id", sort=False
    ).cumcount()
    return output


def _history_available(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    spec: SignalSpec,
    candidate_positions: dict[pd.Timestamp, int],
) -> pd.Series:
    required = spec.required_history_sessions
    if not required:
        return pd.Series(True, index=frame.index, dtype=bool)
    if spec.calendar_policy is SignalCalendarPolicy.DATASET_SESSION_CONTIGUOUS:
        working = frame.copy()
        working["_candidate_position"] = working["date"].map(candidate_positions)
        grouped = working.groupby("stock_id", sort=False)
        available = pd.Series(True, index=working.index, dtype=bool)
        for lag in range(1, required + 1):
            prior_position = grouped["_candidate_position"].shift(lag)
            contiguous = prior_position.eq(working["_candidate_position"] - lag)
            prior_features = (
                grouped[list(spec.required_features)].shift(lag).notna().all(axis=1)
            )
            prior_projection = grouped["_feature_row_present"].shift(lag).eq(True)
            available &= contiguous & prior_features & prior_projection
        return available

    feature_history = features.sort_values(
        ["stock_id", "date"], kind="mergesort"
    ).reset_index(drop=True)
    grouped = feature_history.groupby("stock_id", sort=False)
    available = pd.Series(True, index=feature_history.index, dtype=bool)
    for lag in range(1, required + 1):
        available &= (
            grouped[list(spec.required_features)].shift(lag).notna().all(axis=1)
        )
    history_by_key = pd.Series(
        available.to_numpy(),
        index=pd.MultiIndex.from_frame(feature_history.loc[:, list(_KEY_COLUMNS)]),
    )
    keys = pd.MultiIndex.from_frame(frame.loc[:, list(_KEY_COLUMNS)])
    return history_by_key.reindex(keys, fill_value=False).set_axis(frame.index)


def _outcomes(frame: pd.DataFrame, spec: SignalSpec) -> tuple[pd.DataFrame, pd.Series]:
    horizon = int(spec.evaluation_horizon_days or 0)
    multiplier = 1.0 if spec.direction is SignalDirection.BULLISH else -1.0
    grouped_close = frame.groupby("stock_id", sort=False)["close"]
    final_return = (grouped_close.shift(-horizon) / frame["close"] - 1.0) * multiplier
    adverse_price_column = "low" if spec.direction is SignalDirection.BULLISH else "high"
    grouped_adverse_price = frame.groupby("stock_id", sort=False)[adverse_price_column]
    paths = [
        (grouped_adverse_price.shift(-lag) / frame["close"] - 1.0) * multiplier
        for lag in range(1, horizon + 1)
    ]
    complete = final_return.notna()
    adverse = pd.concat(paths, axis=1).min(axis=1).clip(upper=0.0)
    output = frame.loc[:, ["date", "stock_id", "_instrument_position"]].copy()
    output["directional_return"] = final_return
    output["maximum_adverse_excursion"] = adverse
    return output, complete


def _effective_rows(rows: pd.DataFrame, horizon: int) -> pd.DataFrame:
    selected: list[int] = []
    for _stock_id, group in rows.groupby("stock_id", sort=False):
        next_available_position = -1
        ordered = group.sort_values("_instrument_position", kind="mergesort")
        for index, position in ordered["_instrument_position"].items():
            position = int(position)
            if position < next_available_position:
                continue
            selected.append(int(index))
            next_available_position = position + horizon
    return rows.loc[selected].sort_values(
        ["stock_id", "date"], kind="mergesort"
    )


def _quantile_estimates(values: pd.Series) -> tuple[QuantileEstimate, ...]:
    return tuple(
        QuantileEstimate(
            probability=probability,
            value=None if values.empty else float(values.quantile(probability)),
        )
        for probability in _QUANTILES
    )


def _sample_statistics(rows: pd.DataFrame, horizon: int) -> HistoricalSampleStatistics:
    effective = _effective_rows(rows, horizon) if not rows.empty else rows
    returns = effective["directional_return"].astype(float)
    adverse = effective["maximum_adverse_excursion"].astype(float)
    downside = returns.loc[returns.lt(0.0)]
    size = len(effective)
    return HistoricalSampleStatistics(
        raw_sample_size=len(rows),
        effective_sample_size=size,
        event_date_count=int(rows["date"].nunique()),
        overlap_count=len(rows) - size,
        direction_positive_rate=None if not size else float(returns.gt(0.0).mean()),
        mean_return=None if not size else float(returns.mean()),
        median_return=None if not size else float(returns.median()),
        return_quantiles=_quantile_estimates(returns),
        downside_count=len(downside),
        downside_rate=None if not size else float(returns.lt(0.0).mean()),
        downside_mean_return=None if downside.empty else float(downside.mean()),
        maximum_adverse_excursion_mean=None if not size else float(adverse.mean()),
        maximum_adverse_excursion_median=(
            None if not size else float(adverse.median())
        ),
        maximum_adverse_excursion_quantiles=_quantile_estimates(adverse),
    )


def _incremental_edge(
    conditional: HistoricalSampleStatistics,
    baseline: HistoricalSampleStatistics,
) -> IncrementalEdge:
    def difference(left: float | None, right: float | None) -> float | None:
        return None if left is None or right is None else left - right

    rate = difference(
        conditional.direction_positive_rate, baseline.direction_positive_rate
    )
    return IncrementalEdge(
        direction_positive_rate_percentage_points=(
            None if rate is None else rate * 100.0
        ),
        mean_return_edge=difference(conditional.mean_return, baseline.mean_return),
        median_return_edge=difference(
            conditional.median_return, baseline.median_return
        ),
    )


def _warning_from_mask(
    frame: pd.DataFrame,
    mask: pd.Series,
    *,
    signal_id: str | None,
    reason_code: str,
    stage: str,
) -> HistoricalStatisticsWarning | None:
    affected = frame.loc[mask, ["date", "stock_id"]]
    if affected.empty:
        return None
    keys = [
        f"{row.date.date().isoformat()}/{row.stock_id}"
        for row in affected.head(5).itertuples(index=False)
    ]
    return HistoricalStatisticsWarning(
        record_key=",".join(keys),
        signal_id=signal_id,
        reason_code=reason_code,
        stage=stage,
        affected_count=len(affected),
    )


def _snapshot_gap_warning(snapshot: Any) -> HistoricalStatisticsWarning | None:
    identity = snapshot.manifest["identity_payload"]
    if identity["resolution_status"] == "RESOLVED":
        return None
    evidence = identity["observation_evidence"]
    affected = len(evidence["no_observation_dates"]) + sum(
        len(item["missing_markets"]) for item in evidence["partial_market_dates"]
    )
    return HistoricalStatisticsWarning(
        record_key=(
            f"{evidence['business_date_candidates'][0]}.."
            f"{evidence['business_date_candidates'][-1]}/*"
        ),
        signal_id=None,
        reason_code="SNAPSHOT_RESOLVED_WITH_GAPS",
        stage="FINALIZED_DAILY_INPUT",
        affected_count=affected,
    )


def _signal_statistics(
    snapshot_frame: pd.DataFrame,
    features: pd.DataFrame,
    spec: SignalSpec,
    candidate_positions: dict[pd.Timestamp, int],
) -> tuple[SignalHistoricalStatistics, list[HistoricalStatisticsWarning]]:
    frame = _aligned_history(snapshot_frame, features, spec)
    history_available = _history_available(frame, features, spec, candidate_positions)
    feature_present = frame["_feature_row_present"].astype(bool)
    current_available = frame.loc[:, list(spec.required_features)].notna().all(axis=1)
    rule = frame[spec.signal_column]
    rule_observable = feature_present & current_available & history_available
    invalid_rule = rule_observable & rule.notna() & ~rule.isin([0, 1])
    if bool(invalid_rule.any()):
        raise _historical_error(
            "HIST_RULE_RESULT_INVALID",
            f"signal_id={spec.signal_id}; affected_count={int(invalid_rule.sum())}",
        )

    masks = {
        "FEATURE_PROJECTION_ROW_MISSING": ~feature_present,
        "REQUIRED_FEATURE_UNAVAILABLE": feature_present & ~current_available,
        "REQUIRED_HISTORY_UNAVAILABLE": (
            feature_present & current_available & ~history_available
        ),
        "RULE_RESULT_UNAVAILABLE": rule_observable & rule.isna(),
    }
    not_observable = pd.Series(False, index=frame.index, dtype=bool)
    warnings: list[HistoricalStatisticsWarning] = []
    for reason_code, mask in masks.items():
        not_observable |= mask
        warning = _warning_from_mask(
            frame,
            mask,
            signal_id=spec.signal_id,
            reason_code=reason_code,
            stage="SIGNAL_EVALUATION",
        )
        if warning is not None:
            warnings.append(warning)
    triggered = ~not_observable & rule.eq(1)
    not_triggered = ~not_observable & rule.eq(0)
    if int((triggered | not_triggered | not_observable).sum()) != len(frame):
        raise _historical_error(
            "HIST_EVALUATION_STATE_DRIFT", f"signal_id={spec.signal_id}"
        )

    outcomes, complete = _outcomes(frame, spec)
    conditional_rows = outcomes.loc[triggered & complete].copy()
    baseline_rows = outcomes.loc[complete].copy()
    conditional = _sample_statistics(
        conditional_rows, int(spec.evaluation_horizon_days or 0)
    )
    baseline = _sample_statistics(
        baseline_rows, int(spec.evaluation_horizon_days or 0)
    )
    for reason_code, mask, stage in (
        (
            "TRIGGERED_OUTCOME_HORIZON_UNAVAILABLE",
            triggered & ~complete,
            "CONDITIONAL_OUTCOME_ALIGNMENT",
        ),
        (
            "BASELINE_OUTCOME_HORIZON_UNAVAILABLE",
            ~complete,
            "BASE_RATE_OUTCOME_ALIGNMENT",
        ),
    ):
        warning = _warning_from_mask(
            frame,
            mask,
            signal_id=spec.signal_id,
            reason_code=reason_code,
            stage=stage,
        )
        if warning is not None:
            warnings.append(warning)

    coverage = HistoricalCoverage(
        evaluated_rows=len(frame),
        triggered_rows=int(triggered.sum()),
        not_triggered_rows=int(not_triggered.sum()),
        not_observable_rows=int(not_observable.sum()),
        triggered_complete_outcomes=len(conditional_rows),
        triggered_outcome_incomplete_rows=int((triggered & ~complete).sum()),
        baseline_complete_outcomes=len(baseline_rows),
        baseline_outcome_incomplete_rows=int((~complete).sum()),
    )
    return (
        SignalHistoricalStatistics(
            signal_id=spec.signal_id,
            signal_version=spec.signal_version,
            spec_content_id=spec.spec_content_id,
            direction=spec.direction.value,
            forward_horizon_sessions=int(spec.evaluation_horizon_days or 0),
            research_evidence_ref=spec.research_evidence_ref or "",
            regime_applicability=spec.regime_applicability,
            regime_match="NOT_ASSESSED",
            coverage=coverage,
            conditional=conditional,
            baseline=baseline,
            incremental_edge=_incremental_edge(conditional, baseline),
        ),
        warnings,
    )


def build_signal_historical_statistics(
    snapshot_manifest_path: Path | str,
    feature_artifact_path: Path | str,
    *,
    indicator_semantics_ref: str,
    specs: Iterable[SignalSpec] | None = None,
) -> SignalHistoricalStatisticsReport:
    """由 exact finalized Daily Close 建立不落盤的歷史統計 read-model。"""

    for value, reason_code in (
        (snapshot_manifest_path, "HIST_SNAPSHOT_MANIFEST_PATH_TYPE_INVALID"),
        (feature_artifact_path, "HIST_FEATURE_ARTIFACT_PATH_TYPE_INVALID"),
    ):
        if not isinstance(value, (str, Path)):
            raise _historical_error(reason_code, type(value).__name__)
    explicit_specs = _materialize_explicit_specs(specs)
    try:
        snapshot, features, feature_content_id, semantics_ref, selected = (
            _load_validated_signal_history(
                snapshot_manifest_path,
                feature_artifact_path,
                indicator_semantics_ref=indicator_semantics_ref,
                specs=explicit_specs,
            )
        )
    except DailySignalScannerError as exc:
        raise _translate_scanner_error(exc) from exc
    _validate_supported_specs(selected)
    _validate_required_feature_values(features, selected)

    identity = snapshot.manifest["identity_payload"]
    evidence = identity["observation_evidence"]
    candidate_dates = tuple(
        pd.Timestamp(value) for value in evidence["business_date_candidates"]
    )
    candidate_positions = {
        value: position for position, value in enumerate(candidate_dates)
    }
    instrument_ids = tuple(sorted(snapshot.frame["stock_id"].astype(str).unique()))
    universe = HistoricalUniverse(
        markets=tuple(sorted(snapshot.frame["market"].astype(str).unique())),
        instrument_count=len(instrument_ids),
        instrument_ids=instrument_ids,
    )
    warnings: list[HistoricalStatisticsWarning] = []
    gap_warning = _snapshot_gap_warning(snapshot)
    if gap_warning is not None:
        warnings.append(gap_warning)
    statistics: list[SignalHistoricalStatistics] = []
    for spec in selected:
        result, signal_warnings = _signal_statistics(
            snapshot.frame, features, spec, candidate_positions
        )
        statistics.append(result)
        warnings.extend(signal_warnings)
    if not selected:
        warnings.append(
            HistoricalStatisticsWarning(
                record_key=f"{candidate_dates[0].date()}..{candidate_dates[-1].date()}/*",
                signal_id=None,
                reason_code="NO_RADAR_ELIGIBLE_SIGNAL_SPEC",
                stage="SIGNAL_ELIGIBILITY_GATE",
                affected_count=0,
            )
        )
        status = HistoricalStatisticsStatus.NO_RADAR_ELIGIBLE_SIGNAL_SPEC
    else:
        status = (
            HistoricalStatisticsStatus.COMPLETE_WITH_EXCLUSIONS
            if warnings
            else HistoricalStatisticsStatus.COMPLETE
        )
    ordered_warnings = tuple(
        sorted(
            warnings,
            key=lambda item: (
                item.signal_id or "",
                item.reason_code,
                item.stage,
                item.record_key,
            ),
        )
    )
    return SignalHistoricalStatisticsReport(
        contract_version=HISTORICAL_STATISTICS_CONTRACT_VERSION,
        status=status,
        snapshot_id=snapshot.manifest["snapshot_id"],
        records_content_id=identity["records_content_id"],
        feature_artifact_content_id=feature_content_id,
        indicator_semantics_ref=semantics_ref,
        source_provenance_content_id=content_hash(identity["source"]),
        sample_window_start=candidate_dates[0].date().isoformat(),
        sample_window_end=candidate_dates[-1].date().isoformat(),
        universe=universe,
        price_return_basis=PRICE_RETURN_BASIS,
        currency="TWD",
        dividend_assumption="EXCLUDED_NOT_TOTAL_RETURN",
        fees_assumption="EXCLUDED",
        tax_assumption="EXCLUDED",
        research_status="VALIDATION_ONLY",
        oos_status="NOT_OOS",
        sealed_status="NOT_SEALED",
        authority_scope="NO_ELIGIBILITY_OR_RANKING_AUTHORITY",
        effective_sample_policy=EFFECTIVE_SAMPLE_POLICY,
        outcome_policy_version=OUTCOME_POLICY_VERSION,
        maximum_adverse_excursion_basis="FUTURE_SESSION_LOW_HIGH_VS_ENTRY_CLOSE",
        eligible_signal_count=len(selected),
        signal_statistics=tuple(statistics),
        warnings=ordered_warnings,
    )
