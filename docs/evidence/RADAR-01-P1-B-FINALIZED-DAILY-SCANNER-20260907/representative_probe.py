"""P1-B 代表性本機資料 probe；只在暫存目錄建立 validation replay。"""

from __future__ import annotations

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
from app.signals import INITIAL_SIGNAL_SPECS, SignalEligibilityStatus
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
    specs = tuple(
        replace(
            spec,
            evaluation_horizon_days=5,
            research_evidence_ref="test-only://radar-p1b/representative-replay",
            eligibility_status=SignalEligibilityStatus.RADAR_ELIGIBLE,
        )
        for spec in INITIAL_SIGNAL_SPECS.values()
    )
    with tempfile.TemporaryDirectory(prefix="radar-p1b-representative-") as temp:
        snapshot = materialize_daily_close_snapshot(
            raw,
            root=Path(temp) / "daily-close-snapshots",
            source={
                "provider_identity": f"validation-file@{feature_content_id}",
                "adapter_contract": "radar-p1b-legacy-clean-replay.v1",
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
            indicator_semantics_ref=_git_blob_ref(PATTERN_PATH),
            specs=specs,
        )
        replay = scan_finalized_daily_signals(
            snapshot.manifest_path,
            FEATURE_PATH,
            indicator_semantics_ref=_git_blob_ref(PATTERN_PATH),
            specs=specs,
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
                "feature_artifact_content_id": report.feature_artifact_content_id,
                "indicator_semantics_ref": report.indicator_semantics_ref,
                "snapshot_row_count": report.snapshot_row_count,
                "feature_matched_row_count": report.feature_matched_row_count,
                "feature_missing_row_count": report.feature_missing_row_count,
                "eligible_signal_count": report.eligible_signal_count,
                "scan_content_id": report.scan_content_id,
                "deterministic_replay_equal": report == replay,
                "replay_scan_content_id": replay.scan_content_id,
                "signal_summaries": [
                    asdict(summary) for summary in report.signal_summaries
                ],
                "hit_count": len(report.hits),
                "warnings": [asdict(warning) for warning in report.warnings],
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
