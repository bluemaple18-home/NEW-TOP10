"""RADAR-01 P1-C deterministic no-rank Daily Radar read-model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from app.research.contracts import content_hash

from .occurrences import (
    RADAR_PROJECTION_BUILD_VERSION,
    RANKING_IMPACT_NONE,
    SignalOccurrence,
    build_signal_occurrences,
)
from .scanner import DailySignalScanReport, DailySignalScanWarning
from .specs import SignalDirection, SignalSpec


DAILY_RADAR_PROJECTION_SCHEMA_VERSION = "daily-radar-projection.v1"


@dataclass(frozen=True)
class DailyRadarInstrumentItem:
    """單一 instrument 的 occurrence ID 分組；不含分數、排名或建議。"""

    instrument_id: str
    bullish_occurrence_ids: tuple[str, ...]
    bearish_occurrence_ids: tuple[str, ...]
    neutral_occurrence_ids: tuple[str, ...]


@dataclass(frozen=True)
class DailyRadarProjection:
    """不可變、只存在記憶體中的 Daily Radar read-model。"""

    projection_id: str
    schema_version: str
    projection_build_version: str
    scanner_contract_version: str
    scan_content_id: str
    scan_date: str
    snapshot_id: str
    records_content_id: str
    feature_artifact_content_id: str
    indicator_semantics_ref: str
    eligible_signal_count: int
    occurrence_count: int
    item_count: int
    coverage_status: str
    feature_matched_row_count: int
    feature_missing_row_count: int
    no_eligible: bool
    ranking_impact: str
    warnings: tuple[DailySignalScanWarning, ...]
    occurrences: tuple[SignalOccurrence, ...]
    items: tuple[DailyRadarInstrumentItem, ...]

    def identity_payload(self) -> dict[str, Any]:
        """回傳 projection 的 canonical content identity payload。"""

        payload = asdict(self)
        payload.pop("projection_id")
        return payload


def build_daily_radar_projection(
    report: DailySignalScanReport,
    snapshot_manifest_path: Path | str,
    *,
    specs: Iterable[SignalSpec] | None = None,
) -> DailyRadarProjection:
    """建立 deterministic、無 score/rank authority 的 in-memory projection。"""

    occurrences = build_signal_occurrences(
        report,
        snapshot_manifest_path,
        specs=specs,
    )
    items = _project_items(occurrences)
    payload = DailyRadarProjection(
        projection_id="",
        schema_version=DAILY_RADAR_PROJECTION_SCHEMA_VERSION,
        projection_build_version=RADAR_PROJECTION_BUILD_VERSION,
        scanner_contract_version=report.scanner_contract_version,
        scan_content_id=report.scan_content_id,
        scan_date=report.scan_date,
        snapshot_id=report.snapshot_id,
        records_content_id=report.records_content_id,
        feature_artifact_content_id=report.feature_artifact_content_id,
        indicator_semantics_ref=report.indicator_semantics_ref,
        eligible_signal_count=report.eligible_signal_count,
        occurrence_count=len(occurrences),
        item_count=len(items),
        coverage_status=report.status.value,
        feature_matched_row_count=report.feature_matched_row_count,
        feature_missing_row_count=report.feature_missing_row_count,
        no_eligible=report.eligible_signal_count == 0,
        ranking_impact=RANKING_IMPACT_NONE,
        warnings=tuple(report.warnings),
        occurrences=occurrences,
        items=items,
    )
    projection_id = content_hash(payload.identity_payload())
    return replace(payload, projection_id=projection_id)


def _project_items(
    occurrences: tuple[SignalOccurrence, ...],
) -> tuple[DailyRadarInstrumentItem, ...]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for occurrence in occurrences:
        buckets = grouped.setdefault(
            occurrence.instrument_id,
            {direction.value: [] for direction in SignalDirection},
        )
        buckets[occurrence.direction].append(occurrence.occurrence_id)
    return tuple(
        DailyRadarInstrumentItem(
            instrument_id=instrument_id,
            bullish_occurrence_ids=tuple(sorted(buckets[SignalDirection.BULLISH.value])),
            bearish_occurrence_ids=tuple(sorted(buckets[SignalDirection.BEARISH.value])),
            neutral_occurrence_ids=tuple(sorted(buckets[SignalDirection.NEUTRAL.value])),
        )
        for instrument_id, buckets in sorted(grouped.items())
    )
