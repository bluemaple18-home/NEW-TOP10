"""P1-C 代表性本機資料 probe；只在暫存目錄建立 validation replay。"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.pipeline.daily_close_snapshot import (
    FINALIZATION_AUTHORITY,
    RECORD_COLUMNS,
    materialize_daily_close_snapshot,
)
from app.research.contracts import content_hash
from app.signals import INITIAL_SIGNAL_SPECS, SignalEligibilityStatus
from app.signals.radar_projection import build_daily_radar_projection
from app.signals.scanner import scan_finalized_daily_signals


FEATURE_PATH = ROOT / "data" / "clean" / "features.parquet"
PATTERN_PATH = ROOT / "app" / "indicators" / "mixins" / "pattern.py"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git_blob_ref(path: Path) -> str:
    payload = path.read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload)
    return "git-sha1:" + digest.hexdigest()


def main() -> int:
    features = pd.read_parquet(FEATURE_PATH)
    raw = features.loc[:, list(RECORD_COLUMNS)].copy()
    start = pd.Timestamp(raw["date"].min()).date().isoformat()
    end = pd.Timestamp(raw["date"].max()).date().isoformat()
    feature_content_id = _sha256_file(FEATURE_PATH)
    indicator_ref = _git_blob_ref(PATTERN_PATH)
    specs = tuple(
        replace(
            spec,
            evaluation_horizon_days=5,
            research_evidence_ref="test-only://radar-p1c/representative-replay",
            eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
        )
        for spec in INITIAL_SIGNAL_SPECS.values()
    )
    with tempfile.TemporaryDirectory(prefix="radar-p1c-representative-") as temp:
        snapshot = materialize_daily_close_snapshot(
            raw,
            root=Path(temp) / "daily-close-snapshots",
            source={
                "provider_identity": f"validation-file@{feature_content_id}",
                "adapter_contract": "radar-p1c-legacy-clean-replay.v1",
                "endpoint_contract": {
                    "transport": "LOCAL_FILE",
                    "format": "parquet",
                    "finalization_authority": FINALIZATION_AUTHORITY,
                },
            },
            fetched_at="2026-09-07T09:30:00Z",
            requested_start=start,
            requested_end=end,
        )
        report = scan_finalized_daily_signals(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=indicator_ref,
            specs=specs,
        )
        first = build_daily_radar_projection(
            report,
            snapshot.manifest_path,
            specs=specs,
        )
        second = build_daily_radar_projection(
            report,
            snapshot.manifest_path,
            specs=specs,
        )
        default_report = scan_finalized_daily_signals(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=indicator_ref,
        )
        default_projection = build_daily_radar_projection(
            default_report,
            snapshot.manifest_path,
        )
        occurrence_ids = [item.occurrence_id for item in first.occurrences]
        projected_ids = sorted(
            occurrence_id
            for item in first.items
            for occurrence_id in (
                *item.bullish_occurrence_ids,
                *item.bearish_occurrence_ids,
                *item.neutral_occurrence_ids,
            )
        )
        payload = {
            "authority": "VALIDATION_ONLY_NO_RADAR_ELIGIBILITY",
            "feature_source": str(FEATURE_PATH.relative_to(ROOT)),
            "input_rows": len(features),
            "input_stocks": int(features["stock_id"].nunique()),
            "input_date_start": start,
            "input_date_end": end,
            "snapshot_resolution_status": snapshot.manifest["identity_payload"][
                "resolution_status"
            ],
            "report": {
                "status": report.status.value,
                "scan_date": report.scan_date,
                "snapshot_id": report.snapshot_id,
                "records_content_id": report.records_content_id,
                "scan_content_id": report.scan_content_id,
                "snapshot_row_count": report.snapshot_row_count,
                "eligible_signal_count": report.eligible_signal_count,
                "hit_count": len(report.hits),
                "warning_reason_codes": [
                    warning.reason_code for warning in report.warnings
                ],
            },
            "projection": {
                "schema_version": first.schema_version,
                "projection_build_version": first.projection_build_version,
                "projection_id": first.projection_id,
                "projection_id_recomputes": first.projection_id
                == content_hash(first.identity_payload()),
                "replay_projection_id": second.projection_id,
                "deterministic_replay_equal": first == second,
                "ranking_impact": first.ranking_impact,
                "coverage_status": first.coverage_status,
                "occurrence_count": first.occurrence_count,
                "unique_occurrence_id_count": len(set(occurrence_ids)),
                "all_occurrence_ids_recompute": all(
                    item.occurrence_id == content_hash(item.identity_payload())
                    for item in first.occurrences
                ),
                "item_count": first.item_count,
                "items_cover_each_occurrence_once": sorted(occurrence_ids)
                == projected_ids,
                "direction_counts": dict(
                    sorted(Counter(item.direction for item in first.occurrences).items())
                ),
                "warnings_preserved": first.warnings == report.warnings,
                "sample_occurrence": (
                    asdict(first.occurrences[0]) if first.occurrences else None
                ),
            },
            "default_catalog": {
                "report_status": default_report.status.value,
                "eligible_signal_count": default_projection.eligible_signal_count,
                "occurrence_count": default_projection.occurrence_count,
                "item_count": default_projection.item_count,
                "no_eligible": default_projection.no_eligible,
                "ranking_impact": default_projection.ranking_impact,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
