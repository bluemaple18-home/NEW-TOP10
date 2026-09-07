from __future__ import annotations

import json
import gzip
from pathlib import Path

import pandas as pd
import pytest

from app.research.receipt_store import ImmutableCollisionError


FIXED_FETCHED_AT = "2026-09-07T09:30:00Z"
SOURCE = {
    "provider_identity": "fixture-provider@2026-09-07",
    "adapter_contract": "fixture-daily-close-adapter.v1",
    "endpoint_contract": {
        "method": "GET",
        "path": "/daily-close",
        "finalization_authority": "OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1",
    },
}


def quotes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-09-03",
                "stock_id": "6488",
                "stock_name": "環球晶",
                "market": "TPEX",
                "open": 420,
                "high": 428,
                "low": 418,
                "close": 425,
                "volume": 1000,
                "value": 425000,
            },
            {
                "date": "2026-09-01",
                "stock_id": "2330",
                "stock_name": "台積電",
                "market": "TWSE",
                "open": 1200,
                "high": 1220,
                "low": 1190,
                "close": 1210,
                "volume": 2000,
                "value": 2420000,
            },
        ]
    )


def materialize(tmp_path: Path, frame: pd.DataFrame | None = None, **overrides: object):
    from app.pipeline.daily_close_snapshot import materialize_daily_close_snapshot

    options = {
        "root": tmp_path / "daily_close_snapshots",
        "source": SOURCE,
        "fetched_at": FIXED_FETCHED_AT,
        "requested_start": "2026-09-01",
        "requested_end": "2026-09-03",
        "price_basis": "UNADJUSTED",
        "finalization_status": "FINALIZED_EOD",
    }
    options.update(overrides)
    return materialize_daily_close_snapshot(quotes() if frame is None else frame, **options)


def test_snapshot_is_deterministic_sorted_and_content_addressed(tmp_path: Path) -> None:
    from app.pipeline.daily_close_snapshot import load_daily_close_snapshot

    first = materialize(tmp_path)
    second = materialize(tmp_path, quotes().iloc[::-1].reset_index(drop=True))

    assert first.manifest["snapshot_id"] == second.manifest["snapshot_id"]
    assert first.records_path == second.records_path
    assert first.manifest_path == second.manifest_path
    assert first.records_path.name == f"{first.manifest['identity_payload']['records_content_id'][7:]}.jsonl.gz"
    assert first.manifest_path.stem == first.manifest["snapshot_id"][7:]
    assert second.write_status == "EXISTS_IDENTICAL"

    loaded = load_daily_close_snapshot(first.manifest_path)
    assert list(zip(loaded.frame["date"].dt.strftime("%Y-%m-%d"), loaded.frame["stock_id"])) == [
        ("2026-09-01", "2330"),
        ("2026-09-03", "6488"),
    ]


def test_snapshot_preserves_nullable_transactions_without_inventing_zero(tmp_path: Path) -> None:
    frame = quotes().copy()
    frame["transactions"] = [321, None]

    snapshot = materialize(tmp_path, frame)

    assert list(snapshot.frame["transactions"].astype("Float64")) == [pd.NA, 321.0]
    missing = materialize(tmp_path / "missing", quotes())
    assert missing.frame["transactions"].isna().all()


@pytest.mark.parametrize("invalid", [-1, float("inf")])
def test_snapshot_rejects_invalid_transactions(tmp_path: Path, invalid: float) -> None:
    frame = quotes().copy()
    frame["transactions"] = [invalid, 10]

    from app.pipeline.daily_close_snapshot import DailyCloseSnapshotError

    with pytest.raises(DailyCloseSnapshotError, match="transactions"):
        materialize(tmp_path, frame)


def test_snapshot_preserves_gap_and_partial_market_as_unresolved_evidence(tmp_path: Path) -> None:
    snapshot = materialize(tmp_path)
    identity = snapshot.manifest["identity_payload"]

    assert identity["coverage"]["status"] == "PARTIAL"
    assert identity["observation_evidence"]["no_observation_dates"] == [
        {"date": "2026-09-02", "status": "UNRESOLVED_NO_OBSERVATION"}
    ]
    assert identity["observation_evidence"]["partial_market_dates"] == [
        {
            "date": "2026-09-01",
            "missing_markets": ["TPEX"],
            "observed_markets": ["TWSE"],
            "status": "PARTIAL_MARKET_OBSERVATION",
        },
        {
            "date": "2026-09-03",
            "missing_markets": ["TWSE"],
            "observed_markets": ["TPEX"],
            "status": "PARTIAL_MARKET_OBSERVATION",
        },
    ]
    assert identity["resolution_status"] == "RESOLVED_WITH_GAPS"


def test_snapshot_rejects_same_day_before_versioned_daily_close_cutoff(tmp_path: Path) -> None:
    from app.pipeline.daily_close_snapshot import DailyCloseSnapshotError

    with pytest.raises(DailyCloseSnapshotError, match="cutoff"):
        materialize(tmp_path, fetched_at="2026-09-03T06:00:00Z")


def test_snapshot_accepts_same_day_after_cutoff_and_rejects_future_observation(tmp_path: Path) -> None:
    from app.pipeline.daily_close_snapshot import DailyCloseSnapshotError

    accepted = materialize(tmp_path, fetched_at="2026-09-03T07:30:00Z")
    assert accepted.manifest["identity_payload"]["finalization"]["status"] == "FINALIZED_EOD"
    with pytest.raises(DailyCloseSnapshotError, match="earlier than observed"):
        materialize(tmp_path / "future", fetched_at="2026-09-02T15:59:00Z")


def test_snapshot_rejects_unrecorded_finalization_authority(tmp_path: Path) -> None:
    from app.pipeline.daily_close_snapshot import DailyCloseSnapshotError

    source = {**SOURCE, "endpoint_contract": {"method": "GET", "path": "/daily-close"}}
    with pytest.raises(DailyCloseSnapshotError, match="authority"):
        materialize(tmp_path, source=source)


def test_manifest_records_explicit_observation_and_finalization_authority(tmp_path: Path) -> None:
    finalization = materialize(tmp_path).manifest["identity_payload"]["finalization"]

    assert finalization == {
        "contract_version": "daily-close-finalization.v2",
        "status": "FINALIZED_EOD",
        "authority": "OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1",
        "observation_policy_version": "daily-close-observation.v1",
        "observed_at_policy": "TRADING_DATE_DAY_PRECISION",
        "timezone": "Asia/Taipei",
        "official_daily_close_cutoff": "15:30:00",
        "cutoff_policy_version": "twse-tpex-daily-close-cutoff.v1",
        "observed_through_date": "2026-09-03",
    }

    from app.pipeline.daily_close_snapshot import validate_daily_close_manifest
    from app.research.contracts import content_hash

    tampered = json.loads(json.dumps(materialize(tmp_path).manifest))
    tampered["identity_payload"]["fetched_at"] = "2026-09-03T06:00:00Z"
    tampered["snapshot_id"] = content_hash(tampered["identity_payload"])
    assert "same-day observation is before official Daily Close cutoff" in validate_daily_close_manifest(tampered).errors


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda frame: frame.assign(close=None), "required value"),
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "duplicate"),
        (lambda frame: frame.assign(market="NYSE"), "market"),
        (lambda frame: frame.assign(high=1), "OHLC"),
        (lambda frame: frame.assign(volume=-1), "volume"),
        (lambda frame: frame.assign(value=-1), "value"),
        (lambda frame: frame.assign(price_basis="ADJUSTED"), "price basis drift"),
        (lambda frame: frame.assign(finalization_status="PRELIMINARY"), "finalization drift"),
    ],
)
def test_snapshot_rejects_invalid_input(tmp_path: Path, mutate, message: str) -> None:
    from app.pipeline.daily_close_snapshot import DailyCloseSnapshotError

    with pytest.raises(DailyCloseSnapshotError, match=message):
        materialize(tmp_path, mutate(quotes()))


def test_empty_window_is_unresolved_no_observation_not_a_guessed_closure(tmp_path: Path) -> None:
    empty = quotes().iloc[0:0]
    snapshot = materialize(tmp_path, empty)
    identity = snapshot.manifest["identity_payload"]

    assert identity["resolution_status"] == "UNRESOLVED_NO_OBSERVATION"
    assert identity["coverage"]["status"] == "EMPTY"
    assert all(
        item["status"] == "UNRESOLVED_NO_OBSERVATION"
        for item in identity["observation_evidence"]["no_observation_dates"]
    )


def test_existing_content_address_collision_fails_closed(tmp_path: Path) -> None:
    snapshot = materialize(tmp_path)
    snapshot.records_path.write_text(json.dumps({"corrupt": True}), encoding="utf-8")

    with pytest.raises(ImmutableCollisionError):
        materialize(tmp_path)


def test_records_use_deterministic_streaming_gzip_format_at_moderate_scale(tmp_path: Path) -> None:
    row_count = 10_000
    frame = pd.DataFrame(
        {
            "date": ["2026-09-01"] * row_count,
            "stock_id": [f"S{index:05d}" for index in range(row_count)],
            "stock_name": [f"樣本{index}" for index in range(row_count)],
            "market": ["TWSE"] * row_count,
            "open": [100] * row_count,
            "high": [102] * row_count,
            "low": [99] * row_count,
            "close": [101] * row_count,
            "volume": [1000] * row_count,
            "value": [101000] * row_count,
        }
    )

    first = materialize(
        tmp_path,
        frame,
        requested_start="2026-09-01",
        requested_end="2026-09-01",
    )
    second = materialize(
        tmp_path,
        frame.iloc[::-1].reset_index(drop=True),
        requested_start="2026-09-01",
        requested_end="2026-09-01",
    )

    assert first.records_path.suffixes == [".jsonl", ".gz"]
    assert first.records_path.read_bytes() == second.records_path.read_bytes()
    assert first.records_path.stat().st_size < 500_000
    with gzip.open(first.records_path, "rt", encoding="utf-8") as handle:
        metadata = json.loads(next(handle))
        observed_rows = sum(1 for _ in handle)
    assert metadata["record_count"] == row_count
    assert "records" not in metadata
    assert observed_rows == row_count
    assert len(first.frame) == row_count
