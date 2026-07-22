from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.tskg.tpex_institutional import (
    ENDPOINT,
    TPExInstitutionalContractError,
    build_tpex_institutional_snapshot,
    fetch_tpex_institutional_snapshot,
    load_tpex_institutional_snapshot,
    market_aggregate,
    write_tpex_institutional_snapshot,
)
from app.tskg.source_policy import (
    SourcePolicyContractError,
    SourcePolicyRegistry,
    preflight_source,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOVERNED_POLICY = PROJECT_ROOT / "config" / "tskg_source_policy_governed_v1.json"


def _row(stock_id: str = "6488") -> dict[str, str]:
    return {
        "Date": "1150722",
        "SecuritiesCompanyCode": stock_id,
        "CompanyName": "環球晶",
        "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy": "1,000",
        " Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell": "400",
        "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference": "600",
        "Foreign Dealers-Total Buy": "100",
        "Foreign Dealers-TotalSell": "50",
        "ForeignDealers-Difference": "50",
        "ForeignInvestorsIncludeMainlandAreaInvestors-TotalBuy": "1,100",
        "ForeignInvestorsIncludeMainlandAreaInvestors-TotalSell": "450",
        "ForeignInvestorsInclude MainlandAreaInvestors-Difference": "650",
        "SecuritiesInvestmentTrustCompanies-TotalBuy": "300",
        "SecuritiesInvestmentTrustCompanies-TotalSell": "100",
        "SecuritiesInvestmentTrustCompanies-Difference": "200",
        "Dealers-TotalBuy": "500",
        "Dealers-TotalSell": "250",
        "Dealers-Difference": "250",
        "Dealers -TotalSell": "125",
        "TotalDifference": "1,050",
    }


def _snapshot(rows: list[dict[str, str]] | None = None) -> dict:
    return build_tpex_institutional_snapshot(
        rows or [_row()],
        retrieved_at="2026-07-22T08:00:00Z",
        expected_trade_date="2026-07-22",
    )


def test_builds_closed_deterministic_snapshot() -> None:
    snapshot = _snapshot([_row("6488"), _row("3105")])
    assert snapshot["trade_date"] == "2026-07-22"
    assert snapshot["source"]["dataset_id"] == "data.gov.tw-dataset-11856"
    assert [row["stock_id"] for row in snapshot["records"]] == ["3105", "6488"]
    assert snapshot["records"][0]["all_institutional_net_shares"] == 1050
    assert market_aggregate(snapshot)["all_institutional_net_shares"] == 2100


def test_rejects_schema_date_arithmetic_and_duplicate_drift() -> None:
    extra = _row()
    extra["unexpected"] = "1"
    with pytest.raises(TPExInstitutionalContractError, match="field set"):
        _snapshot([extra])

    wrong_date = _row()
    wrong_date["Date"] = "1150721"
    with pytest.raises(TPExInstitutionalContractError, match="expected date"):
        _snapshot([wrong_date])

    broken = _row()
    broken["TotalDifference"] = "999"
    with pytest.raises(TPExInstitutionalContractError, match="total arithmetic"):
        _snapshot([broken])

    with pytest.raises(TPExInstitutionalContractError, match="duplicate"):
        _snapshot([_row(), _row()])


def test_fetch_is_one_bounded_get_and_write_reload_round_trip(tmp_path: Path) -> None:
    calls: list[tuple] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, str]]:
            return [_row()]

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    snapshot = fetch_tpex_institutional_snapshot(
        expected_trade_date="2026-07-22",
        retrieved_at="2026-07-22T08:00:00Z",
        http_get=fake_get,
    )
    assert calls[0][0] == (ENDPOINT,)
    assert calls[0][1]["timeout"] == 20
    target = write_tpex_institutional_snapshot(snapshot, tmp_path / "snapshot.json")
    assert load_tpex_institutional_snapshot(target) == snapshot

    tampered = deepcopy(snapshot)
    tampered["records"][0]["all_institutional_net_shares"] += 1
    with pytest.raises(TPExInstitutionalContractError):
        write_tpex_institutional_snapshot(tampered, tmp_path / "bad.json")

    source_tampered = deepcopy(snapshot)
    source_tampered["source"]["dataset_id"] = "unreviewed-source"
    with pytest.raises(TPExInstitutionalContractError, match="source identity"):
        write_tpex_institutional_snapshot(source_tampered, tmp_path / "bad-source.json")

def test_governed_policy_allows_only_the_reviewed_openapi_request() -> None:
    registry = SourcePolicyRegistry.from_governed_file(GOVERNED_POLICY)
    calls: list[str] = []

    result = preflight_source(
        registry,
        source_id="tpex-openapi-3insti-daily",
        method="GET",
        path="/openapi/v1/tpex_3insti_daily_trading",
        media_type="application/json",
        as_of="2026-07-22T08:00:00Z",
        reader=lambda path: calls.append(path) or {"approved": True},
    )

    assert result["ok"] is True
    assert calls == ["/openapi/v1/tpex_3insti_daily_trading"]
    assert registry.summary()["approved_public_count"] == 1

    blocked_calls: list[str] = []
    blocked = preflight_source(
        registry,
        source_id="tpex-openapi-3insti-daily",
        method="GET",
        path="/web/stock/aftertrading/daily_trading_info/st43.php",
        media_type="application/json",
        as_of="2026-07-22T08:00:00Z",
        reader=lambda path: blocked_calls.append(path),
    )
    assert blocked["error"]["code"] == "PATH_NOT_ALLOWED"
    assert blocked_calls == []


def test_public_approval_cannot_be_loaded_from_an_arbitrary_file(tmp_path: Path) -> None:
    untrusted = tmp_path / "self-approved.json"
    untrusted.write_text(GOVERNED_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(SourcePolicyContractError, match="pinned repository path"):
        SourcePolicyRegistry.from_governed_file(untrusted)

    payload = json.loads(GOVERNED_POLICY.read_text(encoding="utf-8"))
    with pytest.raises(SourcePolicyContractError, match="versioned governed registry"):
        SourcePolicyRegistry(payload, _governed_load_token=object())
