"""RADAR-01 P1-C in-memory SignalOccurrence projection contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
import re
from typing import Any, Iterable

from app.pipeline.daily_close_snapshot import (
    DailyCloseSnapshot,
    DailyCloseSnapshotError,
    FINALIZATION_STATUS,
    load_daily_close_snapshot,
)
from app.research.contracts import content_hash

from .scanner import (
    SCANNER_CONTRACT_VERSION,
    DailySignalScanReport,
    DailySignalScanStatus,
    DailySignalScanHit,
    DailySignalScanSummary,
    DailySignalScanWarning,
)
from .specs import (
    SignalDirection,
    SignalEligibilityStatus,
    SignalEvaluationState,
    SignalSpec,
    radar_eligible_signal_specs,
)


SIGNAL_OCCURRENCE_SCHEMA_VERSION = "signal-occurrence.v1"
RADAR_PROJECTION_BUILD_VERSION = "daily-radar-projection.v1"
RANKING_IMPACT_NONE = "NONE"
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMANTICS_REF_RE = re.compile(r"^(?:git-sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})$")


class SignalOccurrenceError(ValueError):
    """Occurrence/projection input 無法安全判讀時使用的穩定錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class SignalOccurrence:
    """只代表 scanner report 中已觸發的 immutable occurrence。"""

    occurrence_id: str
    schema_version: str
    projection_build_version: str
    instrument_id: str
    trading_date: str
    signal_id: str
    signal_version: str
    spec_content_id: str
    direction: str
    evaluation: str
    snapshot_id: str
    records_content_id: str
    provider_identity: str
    adapter_contract: str
    source_endpoint_provenance_content_id: str
    feature_artifact_content_id: str
    indicator_semantics_ref: str
    research_evidence_ref: str
    scan_content_id: str

    def identity_payload(self) -> dict[str, Any]:
        """回傳 occurrence 的 canonical content identity payload。"""

        payload = asdict(self)
        payload.pop("occurrence_id")
        return payload


def build_signal_occurrences(
    report: DailySignalScanReport,
    snapshot_manifest_path: Path | str,
    *,
    specs: Iterable[SignalSpec] | None = None,
) -> tuple[SignalOccurrence, ...]:
    """從已驗證 scan report 建立 only-triggered content-addressed occurrences。"""

    snapshot = _load_exact_snapshot(snapshot_manifest_path)
    selected = _select_exact_specs(specs)
    _validate_report_against_snapshot(report, snapshot)
    by_identity = _validate_report_against_specs(report, selected)
    source = _validated_source(snapshot)
    occurrences: list[SignalOccurrence] = []
    for hit in report.hits:
        spec = by_identity[(hit.signal_id, hit.signal_version, hit.spec_content_id)]
        payload = SignalOccurrence(
            occurrence_id="",
            schema_version=SIGNAL_OCCURRENCE_SCHEMA_VERSION,
            projection_build_version=RADAR_PROJECTION_BUILD_VERSION,
            instrument_id=hit.stock_id,
            trading_date=hit.trading_date,
            signal_id=hit.signal_id,
            signal_version=hit.signal_version,
            spec_content_id=hit.spec_content_id,
            direction=hit.direction,
            evaluation=SignalEvaluationState.TRIGGERED.value,
            snapshot_id=report.snapshot_id,
            records_content_id=report.records_content_id,
            provider_identity=source["provider_identity"],
            adapter_contract=source["adapter_contract"],
            source_endpoint_provenance_content_id=content_hash(source),
            feature_artifact_content_id=report.feature_artifact_content_id,
            indicator_semantics_ref=report.indicator_semantics_ref,
            research_evidence_ref=spec.research_evidence_ref or "",
            scan_content_id=report.scan_content_id,
        )
        occurrence_id = content_hash(payload.identity_payload())
        occurrences.append(replace(payload, occurrence_id=occurrence_id))
    return tuple(
        sorted(
            occurrences,
            key=lambda item: (
                item.instrument_id,
                item.signal_id,
                item.signal_version,
                item.spec_content_id,
                item.occurrence_id,
            ),
        )
    )


def _occurrence_error(reason_code: str, detail: object) -> SignalOccurrenceError:
    return SignalOccurrenceError(reason_code, str(detail))


def _load_exact_snapshot(snapshot_manifest_path: Path | str) -> DailyCloseSnapshot:
    try:
        snapshot = load_daily_close_snapshot(snapshot_manifest_path)
    except (DailyCloseSnapshotError, OSError) as exc:
        raise _occurrence_error("RADAR_SNAPSHOT_INVALID", exc) from exc
    identity = snapshot.manifest["identity_payload"]
    if (
        identity.get("finalization", {}).get("status") != FINALIZATION_STATUS
        or not identity.get("finalization", {}).get("observed_through_date")
    ):
        raise _occurrence_error(
            "RADAR_SNAPSHOT_UNRESOLVED",
            f"snapshot_id={snapshot.manifest.get('snapshot_id')}",
        )
    return snapshot


def _select_exact_specs(
    specs: Iterable[SignalSpec] | None,
) -> tuple[SignalSpec, ...]:
    selected = radar_eligible_signal_specs() if specs is None else tuple(specs)
    for spec in selected:
        if not isinstance(spec, SignalSpec):
            raise _occurrence_error(
                "RADAR_SPEC_TYPE_INVALID", f"type={type(spec).__name__}"
            )
        if spec.eligibility_status is not SignalEligibilityStatus.RADAR_ELIGIBLE:
            raise _occurrence_error(
                "RADAR_SPEC_NOT_RADAR_ELIGIBLE",
                f"signal_id={spec.signal_id}; status={spec.eligibility_status.value}",
            )
        if spec.research_evidence_ref is None or spec.evaluation_horizon_days is None:
            raise _occurrence_error(
                "RADAR_SPEC_EVIDENCE_INCOMPLETE", f"signal_id={spec.signal_id}"
            )
    identities = [
        (spec.signal_id, spec.signal_version, spec.spec_content_id) for spec in selected
    ]
    if len(identities) != len(set(identities)):
        raise _occurrence_error("RADAR_SPEC_IDENTITY_DUPLICATE", identities)
    signal_ids = [spec.signal_id for spec in selected]
    if len(signal_ids) != len(set(signal_ids)):
        raise _occurrence_error("RADAR_SPEC_ID_DUPLICATE", signal_ids)
    return tuple(
        sorted(
            selected,
            key=lambda item: (item.signal_id, item.signal_version, item.spec_content_id),
        )
    )


def _validate_report_against_snapshot(
    report: DailySignalScanReport,
    snapshot: DailyCloseSnapshot,
) -> None:
    _validate_report_structure(report)
    if type(report) is not DailySignalScanReport:
        raise _occurrence_error(
            "RADAR_REPORT_TYPE_INVALID", f"type={type(report).__name__}"
        )
    identity = snapshot.manifest["identity_payload"]
    if report.scanner_contract_version != SCANNER_CONTRACT_VERSION:
        raise _occurrence_error(
            "RADAR_REPORT_SCANNER_CONTRACT_DRIFT",
            report.scanner_contract_version,
        )
    if report.snapshot_id != snapshot.manifest["snapshot_id"]:
        raise _occurrence_error(
            "RADAR_REPORT_SNAPSHOT_ID_MISMATCH", report.snapshot_id
        )
    if report.records_content_id != identity["records_content_id"]:
        raise _occurrence_error(
            "RADAR_REPORT_RECORDS_ID_MISMATCH", report.records_content_id
        )
    if not _HASH_RE.fullmatch(report.feature_artifact_content_id):
        raise _occurrence_error(
            "RADAR_REPORT_FEATURE_ARTIFACT_ID_INVALID",
            report.feature_artifact_content_id,
        )
    if not _SEMANTICS_REF_RE.fullmatch(report.indicator_semantics_ref):
        raise _occurrence_error(
            "RADAR_REPORT_INDICATOR_SEMANTICS_REF_INVALID",
            report.indicator_semantics_ref,
        )
    scan_date = identity["finalization"]["observed_through_date"]
    if report.scan_date != scan_date:
        raise _occurrence_error("RADAR_REPORT_SCAN_DATE_MISMATCH", report.scan_date)
    snapshot_rows = int(snapshot.frame["date"].dt.date.astype(str).eq(scan_date).sum())
    if report.snapshot_row_count != snapshot_rows:
        raise _occurrence_error(
            "RADAR_REPORT_SNAPSHOT_ROW_COUNT_DRIFT", report.snapshot_row_count
        )
    for field_name, value in (
        ("snapshot_row_count", report.snapshot_row_count),
        ("feature_matched_row_count", report.feature_matched_row_count),
        ("feature_missing_row_count", report.feature_missing_row_count),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise _occurrence_error(
                "RADAR_REPORT_COVERAGE_COUNT_INVALID", f"{field_name}={value!r}"
            )
    if not 0 <= report.feature_matched_row_count <= report.snapshot_row_count:
        raise _occurrence_error(
            "RADAR_REPORT_FEATURE_COVERAGE_INVALID",
            report.feature_matched_row_count,
        )
    if (
        report.feature_missing_row_count
        != report.snapshot_row_count - report.feature_matched_row_count
    ):
        raise _occurrence_error(
            "RADAR_REPORT_FEATURE_COVERAGE_DRIFT",
            report.feature_missing_row_count,
        )
    snapshot_instruments = set(
        snapshot.frame.loc[
            snapshot.frame["date"].dt.date.astype(str).eq(scan_date), "stock_id"
        ]
    )
    for hit in report.hits:
        if hit.stock_id not in snapshot_instruments:
            raise _occurrence_error("RADAR_REPORT_HIT_INSTRUMENT_OUTSIDE_SNAPSHOT", hit.stock_id)


def _validate_report_structure(report: object) -> None:
    """在碰觸 report 任何巢狀欄位前，封閉驗證 scanner 輸出形狀。"""

    if type(report) is not DailySignalScanReport:
        raise _occurrence_error("RADAR_REPORT_TYPE_INVALID", f"type={type(report).__name__}")
    if type(report.status) is not DailySignalScanStatus:
        raise _occurrence_error("RADAR_REPORT_STATUS_TYPE_INVALID", type(report.status).__name__)
    for field_name in (
        "scanner_contract_version", "scan_date", "snapshot_id", "records_content_id",
        "feature_artifact_content_id", "indicator_semantics_ref",
    ):
        value = getattr(report, field_name)
        if type(value) is not str or not value:
            raise _occurrence_error("RADAR_REPORT_FIELD_INVALID", field_name)
    for field_name in (
        "snapshot_row_count", "feature_matched_row_count", "feature_missing_row_count",
        "eligible_signal_count",
    ):
        value = getattr(report, field_name)
        if type(value) is not int or value < 0:
            raise _occurrence_error("RADAR_REPORT_COVERAGE_COUNT_INVALID", f"{field_name}={value!r}")
    for field_name, item_type in (
        ("signal_summaries", DailySignalScanSummary),
        ("hits", DailySignalScanHit),
        ("warnings", DailySignalScanWarning),
    ):
        container = getattr(report, field_name)
        if type(container) is not tuple:
            raise _occurrence_error("RADAR_REPORT_CONTAINER_INVALID", field_name)
        for item in container:
            if type(item) is not item_type:
                raise _occurrence_error("RADAR_REPORT_NESTED_TYPE_INVALID", field_name)
            _validate_report_item(item, field_name)


def _validate_report_item(item: object, container_name: str) -> None:
    if container_name == "signal_summaries":
        text_fields = ("signal_id", "signal_version", "spec_content_id")
        count_fields = (
            "evaluated_rows", "triggered_rows", "not_triggered_rows", "not_observable_rows",
        )
    elif container_name == "hits":
        text_fields = (
            "trading_date", "stock_id", "signal_id", "signal_version", "spec_content_id", "direction",
        )
        count_fields = ()
    else:
        text_fields = ("record_key", "reason_code", "stage")
        count_fields = ("affected_count",)
        if item.signal_id is not None and (type(item.signal_id) is not str or not item.signal_id):
            raise _occurrence_error("RADAR_REPORT_WARNING_FIELD_INVALID", "signal_id")
    for field_name in text_fields:
        value = getattr(item, field_name)
        if type(value) is not str or not value:
            reason = "RADAR_REPORT_WARNING_FIELD_INVALID" if container_name == "warnings" else "RADAR_REPORT_NESTED_FIELD_INVALID"
            raise _occurrence_error(reason, field_name)
    for field_name in count_fields:
        value = getattr(item, field_name)
        if type(value) is not int or value < 0:
            reason = "RADAR_REPORT_WARNING_FIELD_INVALID" if container_name == "warnings" else "RADAR_REPORT_SUMMARY_COUNT_INVALID"
            raise _occurrence_error(reason, f"{field_name}={value!r}")


def _validated_source(snapshot: DailyCloseSnapshot) -> dict[str, Any]:
    """只保留 immutable scalar provenance，並將完整來源語意雜湊入 occurrence。"""

    try:
        source = snapshot.manifest["identity_payload"]["source"]
        if not isinstance(source, dict):
            raise TypeError("source")
        for field_name in ("provider_identity", "adapter_contract"):
            if type(source.get(field_name)) is not str or not source[field_name]:
                raise TypeError(field_name)
        if not source.get("endpoint_contract"):
            raise TypeError("endpoint_contract")
        content_hash(source)
    except (KeyError, TypeError, ValueError) as exc:
        raise _occurrence_error("RADAR_SNAPSHOT_SOURCE_INVALID", exc) from exc
    return source


def _validate_report_against_specs(
    report: DailySignalScanReport,
    specs: tuple[SignalSpec, ...],
) -> dict[tuple[str, str, str], SignalSpec]:
    expected_status = (
        DailySignalScanStatus.NO_RADAR_ELIGIBLE_SIGNAL_SPEC
        if not specs
        else DailySignalScanStatus.PARTIAL
        if report.warnings
        else DailySignalScanStatus.COMPLETE
    )
    if report.status is not expected_status:
        raise _occurrence_error("RADAR_REPORT_STATUS_DRIFT", report.status.value)
    if report.eligible_signal_count != len(specs):
        raise _occurrence_error(
            "RADAR_REPORT_ELIGIBLE_COUNT_DRIFT", report.eligible_signal_count
        )
    expected_summary_identities = tuple(
        (spec.signal_id, spec.signal_version, spec.spec_content_id) for spec in specs
    )
    observed_summary_identities = tuple(
        (item.signal_id, item.signal_version, item.spec_content_id)
        for item in report.signal_summaries
    )
    if observed_summary_identities != expected_summary_identities:
        raise _occurrence_error(
            "RADAR_REPORT_SUMMARY_IDENTITY_DRIFT", observed_summary_identities
        )
    if not specs:
        if report.hits:
            raise _occurrence_error("RADAR_REPORT_NO_ELIGIBLE_HIT_DRIFT", len(report.hits))
        return {}

    by_identity = {
        (spec.signal_id, spec.signal_version, spec.spec_content_id): spec
        for spec in specs
    }
    expected_hit_counts: dict[tuple[str, str, str], int] = {}
    for summary in report.signal_summaries:
        for field_name, value in (
            ("evaluated_rows", summary.evaluated_rows),
            ("triggered_rows", summary.triggered_rows),
            ("not_triggered_rows", summary.not_triggered_rows),
            ("not_observable_rows", summary.not_observable_rows),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise _occurrence_error(
                    "RADAR_REPORT_SUMMARY_COUNT_INVALID",
                    f"{summary.signal_id}.{field_name}={value!r}",
                )
        if summary.evaluated_rows != report.snapshot_row_count:
            raise _occurrence_error(
                "RADAR_REPORT_SUMMARY_EVALUATED_DRIFT", summary.signal_id
            )
        observed_total = (
            summary.triggered_rows
            + summary.not_triggered_rows
            + summary.not_observable_rows
        )
        if observed_total != summary.evaluated_rows:
            raise _occurrence_error(
                "RADAR_REPORT_SUMMARY_COUNT_DRIFT", summary.signal_id
            )
        expected_hit_counts[
            (summary.signal_id, summary.signal_version, summary.spec_content_id)
        ] = summary.triggered_rows

    seen_hits: set[tuple[str, str, str, str, str]] = set()
    observed_hit_counts = {key: 0 for key in expected_hit_counts}
    for hit in report.hits:
        if hit.trading_date != report.scan_date:
            raise _occurrence_error("RADAR_REPORT_HIT_DATE_DRIFT", hit.trading_date)
        identity = (hit.signal_id, hit.signal_version, hit.spec_content_id)
        spec = by_identity.get(identity)
        if spec is None or hit.direction != spec.direction.value:
            raise _occurrence_error("RADAR_REPORT_HIT_SPEC_DRIFT", identity)
        if hit.direction not in {item.value for item in SignalDirection}:
            raise _occurrence_error("RADAR_REPORT_HIT_DIRECTION_INVALID", hit.direction)
        key = (hit.trading_date, hit.stock_id, *identity)
        if key in seen_hits:
            raise _occurrence_error("RADAR_REPORT_HIT_DUPLICATE", key)
        seen_hits.add(key)
        observed_hit_counts[identity] += 1
    if observed_hit_counts != expected_hit_counts:
        raise _occurrence_error(
            "RADAR_REPORT_HIT_COUNT_DRIFT", observed_hit_counts
        )
    return by_identity
