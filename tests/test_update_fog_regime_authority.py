from __future__ import annotations

import copy

import pytest

from scripts.update_fog_regime_authority import merge_append_only


def row(date: str, label: str) -> dict[str, object]:
    return {"trade_date": date, "as_of_date": date, "regime_label": label}


def payload(schema: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": schema, "contract": {}, "inputs": {}, "rows": rows}


def test_merge_appends_new_dates_and_preserves_history_exactly() -> None:
    base = payload("market-regime-history.v2", [row("2026-08-31", "RISK_OFF")])
    original = copy.deepcopy(base["rows"])
    extension = payload(
        "market-regime-history-append-only.v1",
        [row("2026-08-31", "BROAD_RISK_ON"), row("2026-09-01", "RISK_OFF")],
    )

    merged, receipt = merge_append_only(base, extension, ["2026-08-31", "2026-09-01"])

    assert merged["rows"][:1] == original
    assert [item["trade_date"] for item in merged["rows"]] == ["2026-08-31", "2026-09-01"]
    assert receipt["status"] == "APPENDED"
    assert receipt["appended_days"] == 1


def test_merge_rejects_gap_against_feature_trade_dates() -> None:
    base = payload("market-regime-history.v2", [row("2026-08-29", "RISK_OFF")])
    extension = payload(
        "market-regime-history-append-only.v1",
        [row("2026-08-29", "RISK_OFF"), row("2026-09-01", "RISK_OFF")],
    )

    with pytest.raises(ValueError, match="未完整覆蓋"):
        merge_append_only(base, extension, ["2026-08-29", "2026-08-31", "2026-09-01"])
