"""RADAR-01 P1-B finalized Daily Close 唯讀 scanner。

本模組只把已驗證的 ME-D1 snapshot、feature artifact 與 Radar-eligible
SignalSpec 組成暫態 scan report；不保存 SignalOccurrence，也不改 ranking/runtime。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
from pathlib import Path
import re
from typing import Iterable

import pandas as pd
import pyarrow.parquet as pq

from app.pipeline.daily_close_snapshot import (
    DailyCloseSnapshot,
    DailyCloseSnapshotError,
    FINALIZATION_STATUS,
    RECORD_COLUMNS,
    load_daily_close_snapshot,
)
from app.research.contracts import content_hash

from .specs import (
    SignalCalendarPolicy,
    SignalEligibilityStatus,
    SignalEvaluationState,
    SignalSpec,
    SignalSpecContractError,
    radar_eligible_signal_specs,
    resolve_signal_evaluation,
)


SCANNER_CONTRACT_VERSION = "finalized-daily-signal-scanner.v1"
_KEY_COLUMNS = ("date", "stock_id")
_RAW_COMPARE_COLUMNS = tuple(
    column for column in RECORD_COLUMNS if column not in _KEY_COLUMNS
)
_SEMANTICS_REF_RE = re.compile(r"^(?:git-sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})$")


class DailySignalScannerError(ValueError):
    """Scanner input 無法安全判讀時使用的穩定錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class DailySignalScanStatus(str, Enum):
    """單次 scanner report 的完整度。"""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_RADAR_ELIGIBLE_SIGNAL_SPEC = "NO_RADAR_ELIGIBLE_SIGNAL_SPEC"


@dataclass(frozen=True)
class DailySignalScanHit:
    """暫態觸發列；不是 canonical SignalOccurrence。"""

    trading_date: str
    stock_id: str
    signal_id: str
    signal_version: str
    spec_content_id: str
    direction: str


@dataclass(frozen=True)
class DailySignalScanSummary:
    """每一個 eligible SignalSpec 的三態計數。"""

    signal_id: str
    signal_version: str
    spec_content_id: str
    evaluated_rows: int
    triggered_rows: int
    not_triggered_rows: int
    not_observable_rows: int


@dataclass(frozen=True)
class DailySignalScanWarning:
    """資料消失或降級的結構化證據。"""

    record_key: str
    signal_id: str | None
    reason_code: str
    stage: str
    affected_count: int


@dataclass(frozen=True)
class DailySignalScanReport:
    """Deterministic、不可變且不持久化的單日 scan report。"""

    scanner_contract_version: str
    status: DailySignalScanStatus
    scan_date: str
    snapshot_id: str
    records_content_id: str
    feature_artifact_content_id: str
    indicator_semantics_ref: str
    snapshot_row_count: int
    feature_matched_row_count: int
    feature_missing_row_count: int
    eligible_signal_count: int
    signal_summaries: tuple[DailySignalScanSummary, ...]
    hits: tuple[DailySignalScanHit, ...]
    warnings: tuple[DailySignalScanWarning, ...]

    def identity_payload(self) -> dict[str, object]:
        """回傳 scanner output 的 canonical identity payload。"""

        return {
            "eligible_signal_count": self.eligible_signal_count,
            "feature_artifact_content_id": self.feature_artifact_content_id,
            "feature_matched_row_count": self.feature_matched_row_count,
            "feature_missing_row_count": self.feature_missing_row_count,
            "hits": [asdict(item) for item in self.hits],
            "indicator_semantics_ref": self.indicator_semantics_ref,
            "records_content_id": self.records_content_id,
            "scan_date": self.scan_date,
            "scanner_contract_version": self.scanner_contract_version,
            "signal_summaries": [asdict(item) for item in self.signal_summaries],
            "snapshot_id": self.snapshot_id,
            "snapshot_row_count": self.snapshot_row_count,
            "status": self.status.value,
            "warnings": [asdict(item) for item in self.warnings],
        }

    @property
    def scan_content_id(self) -> str:
        """以完整 input/result identity 計算穩定 content ID。"""

        return content_hash(self.identity_payload())


def _scanner_error(reason_code: str, detail: object) -> DailySignalScannerError:
    return DailySignalScannerError(reason_code, str(detail))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load_snapshot(manifest_path: Path | str) -> DailyCloseSnapshot:
    try:
        snapshot = load_daily_close_snapshot(manifest_path)
    except (DailyCloseSnapshotError, OSError) as exc:
        raise _scanner_error("SCAN_SNAPSHOT_INVALID", exc) from exc
    identity = snapshot.manifest["identity_payload"]
    if (
        identity.get("resolution_status") == "UNRESOLVED_NO_OBSERVATION"
        or identity.get("finalization", {}).get("status") != FINALIZATION_STATUS
        or not identity.get("finalization", {}).get("observed_through_date")
    ):
        raise _scanner_error(
            "SCAN_SNAPSHOT_UNRESOLVED",
            f"snapshot_id={snapshot.manifest.get('snapshot_id')}",
        )
    return snapshot


def _select_specs(specs: Iterable[SignalSpec] | None) -> tuple[SignalSpec, ...]:
    selected = radar_eligible_signal_specs() if specs is None else tuple(specs)
    for spec in selected:
        if not isinstance(spec, SignalSpec):
            raise _scanner_error(
                "SCAN_SPEC_TYPE_INVALID", f"type={type(spec).__name__}"
            )
        if spec.eligibility_status is not SignalEligibilityStatus.RADAR_ELIGIBLE:
            raise _scanner_error(
                "SCAN_SPEC_NOT_RADAR_ELIGIBLE",
                f"signal_id={spec.signal_id}; status={spec.eligibility_status.value}",
            )
    signal_ids = [spec.signal_id for spec in selected]
    if len(signal_ids) != len(set(signal_ids)):
        raise _scanner_error(
            "SCAN_SPEC_ID_DUPLICATE", f"signal_ids={signal_ids!r}"
        )
    return tuple(
        sorted(
            selected,
            key=lambda spec: (
                spec.signal_id,
                spec.signal_version,
                spec.spec_content_id,
            ),
        )
    )


def _required_feature_columns(specs: tuple[SignalSpec, ...]) -> tuple[str, ...]:
    ordered = [*_KEY_COLUMNS, *_RAW_COMPARE_COLUMNS]
    for spec in specs:
        ordered.extend(spec.required_features)
        ordered.append(spec.signal_column)
    return tuple(dict.fromkeys(ordered))


def _validate_indicator_semantics_ref(value: str) -> str:
    if not isinstance(value, str) or not _SEMANTICS_REF_RE.fullmatch(value):
        raise _scanner_error(
            "SCAN_INDICATOR_SEMANTICS_REF_INVALID", f"value={value!r}"
        )
    return value


def _load_feature_artifact(
    feature_path: Path | str,
    *,
    columns: tuple[str, ...],
) -> tuple[pd.DataFrame, str]:
    path = Path(feature_path)
    if path.suffix.lower() != ".parquet" or path.is_symlink() or not path.is_file():
        raise _scanner_error(
            "SCAN_FEATURE_ARTIFACT_INVALID", f"path={path}"
        )
    try:
        before = _sha256_file(path)
        available_columns = set(pq.read_schema(path).names)
        missing_columns = sorted(set(columns) - available_columns)
        if missing_columns:
            raise _scanner_error(
                "SCAN_FEATURE_SCHEMA_INVALID",
                f"missing_columns={missing_columns!r}",
            )
        frame = pd.read_parquet(path, columns=list(columns))
        after = _sha256_file(path)
    except DailySignalScannerError:
        raise
    except (OSError, ValueError, ImportError) as exc:
        raise _scanner_error("SCAN_FEATURE_ARTIFACT_UNREADABLE", exc) from exc
    except Exception as exc:  # parquet engine 例外型別依版本而異，統一成穩定邊界。
        raise _scanner_error("SCAN_FEATURE_ARTIFACT_UNREADABLE", exc) from exc
    if before != after:
        raise _scanner_error(
            "SCAN_FEATURE_ARTIFACT_CHANGED_DURING_READ", f"path={path}"
        )
    return frame, before


def _normalize_feature_keys(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.normalize()
    normalized["stock_id"] = normalized["stock_id"].astype("string").str.strip()
    invalid_key_count = int(
        (
            normalized["date"].isna()
            | normalized["stock_id"].isna()
            | normalized["stock_id"].eq("")
        ).sum()
    )
    if invalid_key_count:
        raise _scanner_error(
            "SCAN_FEATURE_KEY_INVALID", f"affected_count={invalid_key_count}"
        )
    duplicate_count = int(normalized.duplicated(list(_KEY_COLUMNS)).sum())
    if duplicate_count:
        raise _scanner_error(
            "SCAN_FEATURE_KEY_DUPLICATE", f"affected_count={duplicate_count}"
        )
    return normalized.sort_values(list(_KEY_COLUMNS), kind="mergesort").reset_index(
        drop=True
    )


def _key_index(frame: pd.DataFrame) -> pd.MultiIndex:
    return pd.MultiIndex.from_frame(frame.loc[:, list(_KEY_COLUMNS)])


def _validate_feature_snapshot_boundary(
    snapshot: DailyCloseSnapshot,
    features: pd.DataFrame,
) -> pd.DataFrame:
    normalized = _normalize_feature_keys(features)
    snapshot_frame = snapshot.frame.sort_values(
        list(_KEY_COLUMNS), kind="mergesort"
    ).reset_index(drop=True)
    feature_index = _key_index(normalized)
    snapshot_index = _key_index(snapshot_frame)
    outside = feature_index.difference(snapshot_index)
    if len(outside):
        raise _scanner_error(
            "SCAN_FEATURE_KEY_OUTSIDE_SNAPSHOT", f"affected_count={len(outside)}"
        )

    if normalized.empty:
        return normalized
    expected = snapshot_frame.set_index(list(_KEY_COLUMNS)).loc[
        feature_index, list(_RAW_COMPARE_COLUMNS)
    ]
    observed = normalized.set_index(list(_KEY_COLUMNS)).loc[
        :, list(_RAW_COMPARE_COLUMNS)
    ]
    mismatch_count = 0
    for column in _RAW_COMPARE_COLUMNS:
        left = expected[column].reset_index(drop=True)
        right = observed[column].reset_index(drop=True)
        if column in {"stock_name", "market"}:
            equal = left.astype("string").eq(right.astype("string"))
        else:
            left_numeric = pd.to_numeric(left, errors="coerce")
            right_numeric = pd.to_numeric(right, errors="coerce")
            equal = left_numeric.eq(right_numeric) | (
                left_numeric.isna() & right_numeric.isna()
            )
            equal &= ~(right.notna() & right_numeric.isna())
        mismatch_count += int((~equal.fillna(False)).sum())
    if mismatch_count:
        raise _scanner_error(
            "SCAN_DAILY_CLOSE_VALUE_DRIFT", f"affected_values={mismatch_count}"
        )
    return normalized


def _candidate_dates(snapshot: DailyCloseSnapshot) -> tuple[pd.Timestamp, ...]:
    raw = snapshot.manifest["identity_payload"]["observation_evidence"][
        "business_date_candidates"
    ]
    return tuple(pd.Timestamp(value) for value in raw)


def _history_available(
    *,
    spec: SignalSpec,
    stock_id: str,
    scan_date: pd.Timestamp,
    indexed: pd.DataFrame,
    candidates: tuple[pd.Timestamp, ...],
    history_by_stock: dict[str, pd.DataFrame] | None,
) -> bool:
    required = spec.required_history_sessions
    if not required:
        return True
    if spec.calendar_policy is SignalCalendarPolicy.DATASET_SESSION_CONTIGUOUS:
        try:
            position = candidates.index(scan_date)
        except ValueError as exc:
            raise _scanner_error(
                "SCAN_DATE_OUTSIDE_SNAPSHOT_CALENDAR", scan_date.date().isoformat()
            ) from exc
        if position < required:
            return False
        for lag in range(1, required + 1):
            key = (candidates[position - lag], stock_id)
            if key not in indexed.index:
                return False
            previous = indexed.loc[key]
            if isinstance(previous, pd.DataFrame):
                raise _scanner_error("SCAN_FEATURE_KEY_DUPLICATE", f"key={key!r}")
            if previous.loc[list(spec.required_features)].isna().any():
                return False
        return True

    stock_history = (
        None if history_by_stock is None else history_by_stock.get(stock_id)
    )
    if stock_history is None:
        return False
    prior = stock_history.loc[stock_history["date"].lt(scan_date)]
    if len(prior) < required:
        return False
    return bool(
        prior.tail(required).loc[:, list(spec.required_features)].notna().all().all()
    )


def _snapshot_gap_warnings(
    snapshot: DailyCloseSnapshot,
    *,
    scan_date: str,
) -> list[DailySignalScanWarning]:
    identity = snapshot.manifest["identity_payload"]
    if identity["resolution_status"] == "RESOLVED":
        return []
    evidence = identity["observation_evidence"]
    affected = len(evidence["no_observation_dates"]) + sum(
        len(item["missing_markets"]) for item in evidence["partial_market_dates"]
    )
    return [
        DailySignalScanWarning(
            record_key=f"{scan_date}/*",
            signal_id=None,
            reason_code="SNAPSHOT_RESOLVED_WITH_GAPS",
            stage="FINALIZED_DAILY_INPUT",
            affected_count=affected,
        )
    ]


def _build_report(
    *,
    snapshot: DailyCloseSnapshot,
    feature_content_id: str,
    indicator_semantics_ref: str,
    scan_date: str,
    snapshot_rows: int,
    matched_rows: int,
    specs: tuple[SignalSpec, ...],
    summaries: tuple[DailySignalScanSummary, ...],
    hits: tuple[DailySignalScanHit, ...],
    warnings: tuple[DailySignalScanWarning, ...],
) -> DailySignalScanReport:
    if not specs:
        status = DailySignalScanStatus.NO_RADAR_ELIGIBLE_SIGNAL_SPEC
    elif warnings:
        status = DailySignalScanStatus.PARTIAL
    else:
        status = DailySignalScanStatus.COMPLETE
    identity = snapshot.manifest["identity_payload"]
    return DailySignalScanReport(
        scanner_contract_version=SCANNER_CONTRACT_VERSION,
        status=status,
        scan_date=scan_date,
        snapshot_id=snapshot.manifest["snapshot_id"],
        records_content_id=identity["records_content_id"],
        feature_artifact_content_id=feature_content_id,
        indicator_semantics_ref=indicator_semantics_ref,
        snapshot_row_count=snapshot_rows,
        feature_matched_row_count=matched_rows,
        feature_missing_row_count=snapshot_rows - matched_rows,
        eligible_signal_count=len(specs),
        signal_summaries=summaries,
        hits=hits,
        warnings=warnings,
    )


def scan_finalized_daily_signals(
    snapshot_manifest_path: Path | str,
    feature_artifact_path: Path | str,
    *,
    indicator_semantics_ref: str,
    specs: Iterable[SignalSpec] | None = None,
) -> DailySignalScanReport:
    """掃描 snapshot observed-through date，回傳不落盤的 deterministic report。"""

    snapshot = _load_snapshot(snapshot_manifest_path)
    semantics_ref = _validate_indicator_semantics_ref(indicator_semantics_ref)
    selected = _select_specs(specs)
    raw_features, feature_content_id = _load_feature_artifact(
        feature_artifact_path,
        columns=_required_feature_columns(selected),
    )
    features = _validate_feature_snapshot_boundary(snapshot, raw_features)
    identity = snapshot.manifest["identity_payload"]
    scan_date = str(identity["finalization"]["observed_through_date"])
    scan_timestamp = pd.Timestamp(scan_date)
    snapshot_as_of = snapshot.frame.loc[
        snapshot.frame["date"].eq(scan_timestamp)
    ].sort_values("stock_id", kind="mergesort")
    if snapshot_as_of.empty:
        raise _scanner_error("SCAN_SNAPSHOT_UNRESOLVED", f"scan_date={scan_date}")
    feature_as_of = features.loc[features["date"].eq(scan_timestamp)]
    snapshot_stock_ids = set(snapshot_as_of["stock_id"].astype(str))
    matched_stock_ids = set(feature_as_of["stock_id"].astype(str))
    missing_stock_ids = sorted(snapshot_stock_ids - matched_stock_ids)
    warnings = _snapshot_gap_warnings(snapshot, scan_date=scan_date)
    if missing_stock_ids:
        warnings.append(
            DailySignalScanWarning(
                record_key=(
                    f"{scan_date}/" + ",".join(missing_stock_ids[:5])
                ),
                signal_id=None,
                reason_code="FEATURE_PROJECTION_ROW_MISSING",
                stage="FEATURE_PROJECTION_ALIGNMENT",
                affected_count=len(missing_stock_ids),
            )
        )
    if not selected:
        warnings.append(
            DailySignalScanWarning(
                record_key=f"{scan_date}/*",
                signal_id=None,
                reason_code="NO_RADAR_ELIGIBLE_SIGNAL_SPEC",
                stage="SIGNAL_ELIGIBILITY_GATE",
                affected_count=0,
            )
        )
        return _build_report(
            snapshot=snapshot,
            feature_content_id=feature_content_id,
            indicator_semantics_ref=semantics_ref,
            scan_date=scan_date,
            snapshot_rows=len(snapshot_as_of),
            matched_rows=len(feature_as_of),
            specs=selected,
            summaries=(),
            hits=(),
            warnings=tuple(warnings),
        )

    indexed = features.set_index(list(_KEY_COLUMNS), drop=False)
    candidates = _candidate_dates(snapshot)
    history_by_stock = None
    if any(
        spec.calendar_policy is SignalCalendarPolicy.PREVIOUS_OBSERVED_ROW
        for spec in selected
    ):
        history_by_stock = {
            str(stock_id): group.sort_values("date", kind="mergesort")
            for stock_id, group in features.groupby("stock_id", sort=False)
        }
    summaries: list[DailySignalScanSummary] = []
    hits: list[DailySignalScanHit] = []
    warning_counts: dict[tuple[str, str], int] = {}
    warning_keys: dict[tuple[str, str], list[str]] = {}
    for spec in selected:
        counts = {state: 0 for state in SignalEvaluationState}
        for snapshot_row in snapshot_as_of.itertuples(index=False):
            stock_id = str(snapshot_row.stock_id)
            key = (scan_timestamp, stock_id)
            if key not in indexed.index:
                state = SignalEvaluationState.NOT_OBSERVABLE
                reason_code = "FEATURE_PROJECTION_ROW_MISSING"
            else:
                row = indexed.loc[key]
                if isinstance(row, pd.DataFrame):
                    raise _scanner_error("SCAN_FEATURE_KEY_DUPLICATE", f"key={key!r}")
                unavailable = tuple(
                    feature
                    for feature in spec.required_features
                    if pd.isna(row[feature])
                )
                history_available = _history_available(
                    spec=spec,
                    stock_id=stock_id,
                    scan_date=scan_timestamp,
                    indexed=indexed,
                    candidates=candidates,
                    history_by_stock=history_by_stock,
                )
                try:
                    evaluation = resolve_signal_evaluation(
                        spec,
                        rule_result=row[spec.signal_column],
                        unavailable_features=unavailable,
                        history_available=history_available,
                    )
                except SignalSpecContractError as exc:
                    raise _scanner_error(
                        "SCAN_RULE_RESULT_INVALID",
                        f"signal_id={spec.signal_id}; key={key!r}; {exc}",
                    ) from exc
                state = evaluation.state
                reason_code = evaluation.reason_code
            counts[state] += 1
            if state is SignalEvaluationState.TRIGGERED:
                hits.append(
                    DailySignalScanHit(
                        trading_date=scan_date,
                        stock_id=stock_id,
                        signal_id=spec.signal_id,
                        signal_version=spec.signal_version,
                        spec_content_id=spec.spec_content_id,
                        direction=spec.direction.value,
                    )
                )
            elif state is SignalEvaluationState.NOT_OBSERVABLE and reason_code:
                warning_key = (spec.signal_id, reason_code)
                warning_counts[warning_key] = warning_counts.get(warning_key, 0) + 1
                warning_keys.setdefault(warning_key, []).append(stock_id)
        summaries.append(
            DailySignalScanSummary(
                signal_id=spec.signal_id,
                signal_version=spec.signal_version,
                spec_content_id=spec.spec_content_id,
                evaluated_rows=len(snapshot_as_of),
                triggered_rows=counts[SignalEvaluationState.TRIGGERED],
                not_triggered_rows=counts[SignalEvaluationState.NOT_TRIGGERED],
                not_observable_rows=counts[SignalEvaluationState.NOT_OBSERVABLE],
            )
        )

    warnings.extend(
        DailySignalScanWarning(
            record_key=(
                f"{scan_date}/" + ",".join(warning_keys[(signal_id, reason_code)][:5])
            ),
            signal_id=signal_id,
            reason_code=reason_code,
            stage="SIGNAL_EVALUATION",
            affected_count=affected_count,
        )
        for (signal_id, reason_code), affected_count in sorted(warning_counts.items())
    )
    ordered_hits = tuple(
        sorted(hits, key=lambda item: (item.stock_id, item.signal_id, item.signal_version))
    )
    return _build_report(
        snapshot=snapshot,
        feature_content_id=feature_content_id,
        indicator_semantics_ref=semantics_ref,
        scan_date=scan_date,
        snapshot_rows=len(snapshot_as_of),
        matched_rows=len(feature_as_of),
        specs=selected,
        summaries=tuple(summaries),
        hits=ordered_hits,
        warnings=tuple(warnings),
    )
