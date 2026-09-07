"""RADAR-01 P1-A 的 SignalSpec authority 與可觀測性契約。

本模組只定義既有 deterministic signal 的 identity、admission metadata 與
read-only parity gate；不負責掃描市場、保存 occurrence、計算績效或排名。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from numbers import Real
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


DAILY_CLOSE_DATASET_CONTRACT = "daily-close-snapshot.v1"
_SIGNAL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMVER_RE = re.compile(r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")


class SignalSpecContractError(ValueError):
    """Signal contract 無法安全判讀時使用的穩定錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class SignalCalendarPolicy(str, Enum):
    """跨日 rule 對前序資料的時間語意。"""

    DATASET_SESSION_CONTIGUOUS = "DATASET_SESSION_CONTIGUOUS"
    PREVIOUS_OBSERVED_ROW = "PREVIOUS_OBSERVED_ROW"


class SignalDirection(str, Enum):
    """訊號方向；不代表交易建議或 ranking authority。"""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SignalEligibilityStatus(str, Enum):
    """SignalSpec 的 Radar admission 狀態。"""

    CONTRACT_ONLY = "CONTRACT_ONLY"
    RADAR_ELIGIBLE = "RADAR_ELIGIBLE"
    REJECTED = "REJECTED"


class SignalEvaluationState(str, Enum):
    """單次 rule result 的三態語意。"""

    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    NOT_OBSERVABLE = "NOT_OBSERVABLE"


@dataclass(frozen=True)
class SignalSpec:
    """可 content-address、不可變的 SignalSpec。"""

    signal_id: str
    signal_version: str
    name: str
    category: str
    direction: SignalDirection
    signal_column: str
    rule_reference: str
    rule_expression: str
    calendar_policy: SignalCalendarPolicy
    required_features: tuple[str, ...]
    required_history_sessions: int
    required_dataset_contract: str
    evaluation_horizon_days: int | None
    regime_applicability: str
    research_evidence_ref: str | None
    eligibility_status: SignalEligibilityStatus
    educational_explanation_ref: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.signal_id, str) or not _SIGNAL_ID_RE.fullmatch(
            self.signal_id
        ):
            raise SignalSpecContractError(
                "SIGNAL_ID_INVALID", f"signal_id={self.signal_id!r}"
            )
        if not isinstance(self.signal_version, str) or not _SEMVER_RE.fullmatch(
            self.signal_version
        ):
            raise SignalSpecContractError(
                "SIGNAL_VERSION_INVALID", f"signal_version={self.signal_version!r}"
            )
        if not isinstance(self.direction, SignalDirection):
            raise SignalSpecContractError(
                "SIGNAL_DIRECTION_INVALID", f"direction={self.direction!r}"
            )
        if not isinstance(self.calendar_policy, SignalCalendarPolicy):
            raise SignalSpecContractError(
                "SIGNAL_CALENDAR_POLICY_INVALID",
                f"calendar_policy={self.calendar_policy!r}",
            )
        if not isinstance(self.eligibility_status, SignalEligibilityStatus):
            raise SignalSpecContractError(
                "SIGNAL_ELIGIBILITY_INVALID",
                f"eligibility_status={self.eligibility_status!r}",
            )
        required_text = {
            "name": self.name,
            "category": self.category,
            "signal_column": self.signal_column,
            "rule_reference": self.rule_reference,
            "rule_expression": self.rule_expression,
            "required_dataset_contract": self.required_dataset_contract,
            "regime_applicability": self.regime_applicability,
        }
        empty = sorted(
            name
            for name, value in required_text.items()
            if not isinstance(value, str) or not value.strip()
        )
        if empty:
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_FIELD_EMPTY", f"fields={','.join(empty)}"
            )
        if not isinstance(self.required_features, tuple):
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_FEATURES_TYPE_INVALID",
                f"type={type(self.required_features).__name__}",
            )
        if not self.required_features:
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_FEATURES_EMPTY", f"signal_id={self.signal_id}"
            )
        if len(set(self.required_features)) != len(self.required_features):
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_FEATURES_DUPLICATE", f"signal_id={self.signal_id}"
            )
        if any(
            not isinstance(name, str) or not _SIGNAL_ID_RE.fullmatch(name)
            for name in self.required_features
        ):
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_FEATURE_INVALID",
                f"signal_id={self.signal_id}; features={self.required_features!r}",
            )
        if self.required_dataset_contract != DAILY_CLOSE_DATASET_CONTRACT:
            raise SignalSpecContractError(
                "SIGNAL_DATASET_CONTRACT_UNSUPPORTED",
                f"required_dataset_contract={self.required_dataset_contract!r}",
            )
        for field_name, value in (
            ("research_evidence_ref", self.research_evidence_ref),
            ("educational_explanation_ref", self.educational_explanation_ref),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise SignalSpecContractError(
                    "SIGNAL_OPTIONAL_REF_INVALID",
                    f"field={field_name}; value={value!r}",
                )
        if (
            isinstance(self.required_history_sessions, bool)
            or not isinstance(self.required_history_sessions, int)
            or self.required_history_sessions < 0
        ):
            raise SignalSpecContractError(
                "SIGNAL_REQUIRED_HISTORY_INVALID",
                f"required_history_sessions={self.required_history_sessions!r}",
            )
        if self.evaluation_horizon_days is not None:
            if (
                isinstance(self.evaluation_horizon_days, bool)
                or not isinstance(self.evaluation_horizon_days, int)
                or self.evaluation_horizon_days <= 0
            ):
                raise SignalSpecContractError(
                    "SIGNAL_EVALUATION_HORIZON_INVALID",
                    f"evaluation_horizon_days={self.evaluation_horizon_days!r}",
                )
        if self.eligibility_status is SignalEligibilityStatus.RADAR_ELIGIBLE and (
            self.evaluation_horizon_days is None or not self.research_evidence_ref
        ):
            raise SignalSpecContractError(
                "RADAR_ELIGIBILITY_EVIDENCE_INCOMPLETE",
                "RADAR_ELIGIBLE 需要 evaluation_horizon_days 與 research_evidence_ref",
            )

    def identity_payload(self) -> dict[str, Any]:
        """回傳所有 authority／semantic 欄位的 canonical identity payload。"""

        return {
            "calendar_policy": self.calendar_policy.value,
            "category": self.category,
            "direction": self.direction.value,
            "educational_explanation_ref": self.educational_explanation_ref,
            "eligibility_status": self.eligibility_status.value,
            "evaluation_horizon_days": self.evaluation_horizon_days,
            "name": self.name,
            "regime_applicability": self.regime_applicability,
            "required_dataset_contract": self.required_dataset_contract,
            "required_features": list(self.required_features),
            "required_history_sessions": self.required_history_sessions,
            "research_evidence_ref": self.research_evidence_ref,
            "rule_expression": self.rule_expression,
            "rule_reference": self.rule_reference,
            "signal_column": self.signal_column,
            "signal_id": self.signal_id,
            "signal_version": self.signal_version,
        }

    @property
    def spec_content_id(self) -> str:
        """以 canonical JSON 計算穩定 SignalSpec content ID。"""

        encoded = json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class SignalEvaluation:
    """單筆 rule result 的非持久化語意結果；不是 SignalOccurrence。"""

    signal_id: str
    signal_version: str
    state: SignalEvaluationState
    reason_code: str | None = None
    unavailable_features: tuple[str, ...] = ()
    detail: str | None = None


@dataclass(frozen=True)
class SignalParityResult:
    """一個 SignalSpec 的 parity 與 observability 摘要。"""

    signal_id: str
    signal_version: str
    spec_content_id: str
    compared_rows: int
    observable_rows: int
    unobservable_rows: int
    mismatch_count: int


@dataclass(frozen=True)
class SignalObservabilityWarning:
    """不可觀測列的穩定 reason、stage 與影響筆數。"""

    signal_id: str
    reason_code: str
    stage: str
    affected_rows: int


@dataclass(frozen=True)
class SignalParityReport:
    """整批 SignalSpec 的 read-only parity 結果。"""

    row_count: int
    signal_count: int
    radar_eligible_signal_count: int
    catalog_status: str
    signal_results: tuple[SignalParityResult, ...]
    warnings: tuple[SignalObservabilityWarning, ...]


def _initial_spec(
    signal_id: str,
    *,
    name: str,
    category: str,
    direction: SignalDirection,
    required_features: tuple[str, ...],
    rule_expression: str,
) -> SignalSpec:
    """建立不帶績效宣稱的 bounded initial contract。"""

    return SignalSpec(
        signal_id=signal_id,
        signal_version="1.0.0",
        name=name,
        category=category,
        direction=direction,
        signal_column=signal_id,
        rule_reference=(
            "app.indicators.mixins.pattern:"
            f"PatternIndicatorsMixin.calculate_binary_events#{signal_id}"
        ),
        rule_expression=rule_expression,
        calendar_policy=SignalCalendarPolicy.DATASET_SESSION_CONTIGUOUS,
        required_features=required_features,
        required_history_sessions=1,
        required_dataset_contract=DAILY_CLOSE_DATASET_CONTRACT,
        evaluation_horizon_days=None,
        regime_applicability="UNASSESSED",
        research_evidence_ref=None,
        eligibility_status=SignalEligibilityStatus.CONTRACT_ONLY,
        educational_explanation_ref=None,
    )


INITIAL_SIGNAL_SPECS: Mapping[str, SignalSpec] = MappingProxyType(
    {
        "ma5_cross_ma20_up": _initial_spec(
            "ma5_cross_ma20_up",
            name="MA5 上穿 MA20",
            category="moving_average_cross",
            direction=SignalDirection.BULLISH,
            required_features=("ma5", "ma20"),
            rule_expression="ma5[t] > ma20[t] AND ma5[t-1] <= ma20[t-1]",
        ),
        "ma5_cross_ma20_down": _initial_spec(
            "ma5_cross_ma20_down",
            name="MA5 下穿 MA20",
            category="moving_average_cross",
            direction=SignalDirection.BEARISH,
            required_features=("ma5", "ma20"),
            rule_expression="ma5[t] < ma20[t] AND ma5[t-1] >= ma20[t-1]",
        ),
        "rsi_rebound_from_40": _initial_spec(
            "rsi_rebound_from_40",
            name="RSI 自 40 反彈",
            category="momentum_threshold_cross",
            direction=SignalDirection.BULLISH,
            required_features=("rsi",),
            rule_expression="rsi[t] > 40 AND rsi[t-1] <= 40",
        ),
        "rsi_break_below_50": _initial_spec(
            "rsi_break_below_50",
            name="RSI 跌破 50",
            category="momentum_threshold_cross",
            direction=SignalDirection.BEARISH,
            required_features=("rsi",),
            rule_expression="rsi[t] < 50 AND rsi[t-1] >= 50",
        ),
    }
)


def radar_eligible_signal_specs(
    specs: Iterable[SignalSpec] | None = None,
) -> tuple[SignalSpec, ...]:
    """只回傳已具研究 evidence 與 horizon 的 Radar-eligible specs。"""

    selected = tuple(INITIAL_SIGNAL_SPECS.values()) if specs is None else tuple(specs)
    return tuple(
        spec
        for spec in selected
        if spec.eligibility_status is SignalEligibilityStatus.RADAR_ELIGIBLE
    )


def resolve_signal_evaluation(
    spec: SignalSpec,
    *,
    rule_result: Any,
    unavailable_features: Iterable[str] = (),
    history_available: bool = True,
    evaluation_error: str | None = None,
) -> SignalEvaluation:
    """把 caller 已計算的 rule result 解析為三態，禁止 missing 變成 0。"""

    requested_unavailable = set(unavailable_features)
    unexpected = sorted(requested_unavailable - set(spec.required_features))
    if unexpected:
        raise SignalSpecContractError(
            "UNAVAILABLE_FEATURE_NOT_REQUIRED",
            f"signal_id={spec.signal_id}; features={unexpected!r}",
        )
    unavailable = tuple(
        feature for feature in spec.required_features if feature in requested_unavailable
    )
    if evaluation_error:
        return SignalEvaluation(
            signal_id=spec.signal_id,
            signal_version=spec.signal_version,
            state=SignalEvaluationState.NOT_OBSERVABLE,
            reason_code="RULE_EVALUATION_ERROR",
            unavailable_features=unavailable,
            detail=evaluation_error,
        )
    if unavailable:
        return SignalEvaluation(
            signal_id=spec.signal_id,
            signal_version=spec.signal_version,
            state=SignalEvaluationState.NOT_OBSERVABLE,
            reason_code="REQUIRED_FEATURE_UNAVAILABLE",
            unavailable_features=unavailable,
        )
    if spec.required_history_sessions and not history_available:
        return SignalEvaluation(
            signal_id=spec.signal_id,
            signal_version=spec.signal_version,
            state=SignalEvaluationState.NOT_OBSERVABLE,
            reason_code="REQUIRED_HISTORY_UNAVAILABLE",
        )
    try:
        missing = bool(pd.isna(rule_result))
    except (TypeError, ValueError):
        missing = False
    if missing:
        return SignalEvaluation(
            signal_id=spec.signal_id,
            signal_version=spec.signal_version,
            state=SignalEvaluationState.NOT_OBSERVABLE,
            reason_code="RULE_RESULT_UNAVAILABLE",
        )
    if not isinstance(rule_result, Real) or rule_result not in (0, 1):
        raise SignalSpecContractError(
            "RULE_RESULT_INVALID",
            f"signal_id={spec.signal_id}; rule_result={rule_result!r}",
        )
    state = (
        SignalEvaluationState.TRIGGERED
        if int(rule_result) == 1
        else SignalEvaluationState.NOT_TRIGGERED
    )
    return SignalEvaluation(
        signal_id=spec.signal_id,
        signal_version=spec.signal_version,
        state=state,
    )


def _require_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    side: str,
    reason_code: str,
) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise SignalSpecContractError(
            reason_code, f"side={side}; missing_columns={missing!r}"
        )


def _validate_binary(series: pd.Series, *, signal_id: str, side: str) -> None:
    valid = series.notna() & series.isin([0, 1])
    if bool(valid.all()):
        return
    invalid_count = int((~valid).sum())
    raise SignalSpecContractError(
        "PARITY_SIGNAL_VALUE_INVALID",
        f"side={side}; signal_id={signal_id}; invalid_count={invalid_count}",
    )


def _signal_observability(
    frame: pd.DataFrame,
    spec: SignalSpec,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """計算當日 feature 與連續市場 session history 的可觀測性。"""

    current_available = frame.loc[:, list(spec.required_features)].notna().all(axis=1)
    history_available = pd.Series(True, index=frame.index, dtype=bool)
    if spec.required_history_sessions:
        _require_columns(
            frame,
            ("date", "stock_id"),
            side="features",
            reason_code="PARITY_HISTORY_KEY_MISSING",
        )
        normalized_dates = pd.to_datetime(frame["date"], errors="coerce")
        invalid_dates = int(normalized_dates.isna().sum())
        if invalid_dates:
            raise SignalSpecContractError(
                "PARITY_DATE_INVALID", f"side=features; row_count={invalid_dates}"
            )
        session_dates = sorted(normalized_dates.unique())
        session_positions = {value: index for index, value in enumerate(session_dates)}
        working = frame.loc[
            :, ["stock_id", *list(spec.required_features)]
        ].reset_index(drop=True)
        working["_session_position"] = (
            normalized_dates.reset_index(drop=True).map(session_positions)
        )
        working = working.sort_values(["stock_id", "_session_position"])
        grouped = working.groupby("stock_id", sort=False)
        history_in_order = pd.Series(True, index=working.index, dtype=bool)
        for lag in range(1, spec.required_history_sessions + 1):
            prior_position = grouped["_session_position"].shift(lag)
            if (
                spec.calendar_policy
                is SignalCalendarPolicy.DATASET_SESSION_CONTIGUOUS
            ):
                contiguous = prior_position.eq(working["_session_position"] - lag)
            else:
                contiguous = prior_position.notna()
            prior_features_available = (
                grouped[list(spec.required_features)].shift(lag).notna().all(axis=1)
            )
            history_in_order &= contiguous & prior_features_available
        history_available = pd.Series(
            history_in_order.sort_index().to_numpy(), index=frame.index, dtype=bool
        )

    feature_unavailable = ~current_available
    history_unavailable = current_available & ~history_available
    observable = current_available & history_available
    return observable, feature_unavailable, history_unavailable


def validate_signal_parity(
    features: pd.DataFrame,
    events: pd.DataFrame,
    *,
    specs: Iterable[SignalSpec] | None = None,
    key_columns: tuple[str, ...] = ("date", "stock_id"),
) -> SignalParityReport:
    """對齊兩份既有 projection 並 fail closed 驗證初始 SignalSpec parity。

    `features` 是初始 catalog 指認的 rule authority；`events` 只是既有重算
    projection。函式不修改輸入，也不建立 SignalOccurrence 或任何 artifact。
    """

    selected = tuple(INITIAL_SIGNAL_SPECS.values()) if specs is None else tuple(specs)
    if not selected:
        raise SignalSpecContractError("PARITY_SPEC_EMPTY", "至少需要一個 SignalSpec")
    signal_ids = [spec.signal_id for spec in selected]
    if len(set(signal_ids)) != len(signal_ids):
        raise SignalSpecContractError(
            "PARITY_SPEC_DUPLICATE", f"signal_ids={signal_ids!r}"
        )

    _require_columns(
        features,
        key_columns,
        side="features",
        reason_code="PARITY_KEY_COLUMN_MISSING",
    )
    _require_columns(
        events,
        key_columns,
        side="events",
        reason_code="PARITY_KEY_COLUMN_MISSING",
    )
    for side, frame in (("features", features), ("events", events)):
        null_count = int(frame.loc[:, list(key_columns)].isna().any(axis=1).sum())
        if null_count:
            raise SignalSpecContractError(
                "PARITY_KEY_NULL", f"side={side}; row_count={null_count}"
            )
        duplicate_count = int(frame.duplicated(list(key_columns)).sum())
        if duplicate_count:
            raise SignalSpecContractError(
                "PARITY_DUPLICATE_KEY",
                f"side={side}; duplicate_count={duplicate_count}",
            )

    feature_index = pd.MultiIndex.from_frame(features.loc[:, list(key_columns)])
    event_index = pd.MultiIndex.from_frame(events.loc[:, list(key_columns)])
    feature_only = feature_index.difference(event_index)
    event_only = event_index.difference(feature_index)
    if len(feature_only) or len(event_only):
        raise SignalSpecContractError(
            "PARITY_KEY_DRIFT",
            f"features_only={len(feature_only)}; events_only={len(event_only)}",
        )

    left = features.set_index(list(key_columns), drop=False)
    right = events.set_index(list(key_columns), drop=False).reindex(left.index)
    results: list[SignalParityResult] = []
    warnings: list[SignalObservabilityWarning] = []
    for spec in selected:
        _require_columns(
            left,
            (spec.signal_column,),
            side="features",
            reason_code="PARITY_SIGNAL_COLUMN_MISSING",
        )
        _require_columns(
            right,
            (spec.signal_column,),
            side="events",
            reason_code="PARITY_SIGNAL_COLUMN_MISSING",
        )
        _require_columns(
            left,
            spec.required_features,
            side="features",
            reason_code="PARITY_REQUIRED_FEATURE_MISSING",
        )

        feature_values = left[spec.signal_column]
        event_values = right[spec.signal_column]
        _validate_binary(feature_values, signal_id=spec.signal_id, side="features")
        _validate_binary(event_values, signal_id=spec.signal_id, side="events")
        mismatch_count = int(
            (feature_values.astype("int8") != event_values.astype("int8")).sum()
        )
        if mismatch_count:
            raise SignalSpecContractError(
                "PARITY_SIGNAL_DRIFT",
                f"signal_id={spec.signal_id}; mismatch_count={mismatch_count}",
            )

        observable, feature_unavailable, history_unavailable = _signal_observability(
            left, spec
        )
        observable_rows = int(observable.sum())
        for reason_code, reason_mask in (
            ("REQUIRED_FEATURE_UNAVAILABLE", feature_unavailable),
            ("REQUIRED_HISTORY_UNAVAILABLE", history_unavailable),
        ):
            affected_rows = int(reason_mask.sum())
            if affected_rows:
                warnings.append(
                    SignalObservabilityWarning(
                        signal_id=spec.signal_id,
                        reason_code=reason_code,
                        stage="SIGNAL_SPEC_PARITY",
                        affected_rows=affected_rows,
                    )
                )
        results.append(
            SignalParityResult(
                signal_id=spec.signal_id,
                signal_version=spec.signal_version,
                spec_content_id=spec.spec_content_id,
                compared_rows=len(left),
                observable_rows=observable_rows,
                unobservable_rows=len(left) - observable_rows,
                mismatch_count=0,
            )
        )

    eligible_count = len(radar_eligible_signal_specs(selected))
    return SignalParityReport(
        row_count=len(left),
        signal_count=len(selected),
        radar_eligible_signal_count=eligible_count,
        catalog_status=(
            "RADAR_ELIGIBLE_PARITY_VERIFIED"
            if eligible_count
            else "CONTRACT_ONLY_PARITY_VERIFIED"
        ),
        signal_results=tuple(results),
        warnings=tuple(warnings),
    )
