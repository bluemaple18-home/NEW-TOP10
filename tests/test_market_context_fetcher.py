"""固定官方回應的市場解析契約；所有輸出使用測試暫存目錄。"""
import copy
import gzip
import hashlib
import json
import random
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import market_context_fetcher as market

FIXTURES = Path(__file__).parent / "fixtures/market_context_official"
DATE = "2026-10-22"
ENDPOINTS = {
    "MI_INDEX": "twse-mi-index", "T86": "twse-t86",
    "stk_wn1430_result.php": "tpex-quotes", "DailyMarketReportFut": "taifex-futures",
    "PutCallRatio": "taifex-pcr",
    "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate": "taifex-oi",
}


def official(name):
    return json.loads(gzip.decompress((FIXTURES / f"{name}.json.gz").read_bytes()))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("解析測試禁止實際網路")
    monkeypatch.setattr(socket.socket, "connect", deny)


def replay(monkeypatch, overrides=None):
    values = {name: official(name) for name in ENDPOINTS.values()}
    values.update(overrides or {})

    def get(url, **kwargs):
        result = values[ENDPOINTS[url.rsplit("/", 1)[-1]]]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: copy.deepcopy(result),
                               status_code=200, headers={"Content-Type": "application/octet-stream"},
                               content=json.dumps(result).encode(), text=json.dumps(result))
    monkeypatch.setattr(market.requests, "get", get)


def taifex(**overrides):
    values = {key: official("taifex-" + key) for key in ("futures", "pcr", "oi")}
    values.update(overrides)
    return market.parse_taifex_payloads(values["futures"], values["pcr"], values["oi"], DATE)


def table(payload, field):
    return next(t for t in payload["tables"] if field in t["fields"])


def set_cell(t, row, field, value):
    t["data"][row][t["fields"].index(field)] = value


def test_official_twse_sign_priority():
    _, breadth, errors = market.parse_twse_quotes(official("twse-mi-index"), DATE)
    assert (breadth["twse_up"], breadth["twse_down"]) == (303, 959)
    assert not errors


def test_official_values_and_overall_schema(monkeypatch):
    replay(monkeypatch)
    p = market.build_market_context(DATE)
    assert p["status"] == "ok" and p["errors"] == {}
    assert all(s["status"] == "ok" and s["data_date"] == DATE for s in p["source_status"].values())
    assert p["taiex"] == {"close": 46041.43, "change": -846.34, "change_pct": -1.81,
                          "trade_value": 930107883593, "trade_value_change_pct": None}
    assert p["institutional"] == {"foreign_net": -284113812, "trust_net": -14647281, "dealer_net": -1553936358}
    b = p["breadth"]
    assert (b["twse_up"], b["twse_down"], b["twse_flat"]) == (303, 959, 99)
    assert b["twse_metadata"]["excluded_counts"] == {"no_trade": 9, "no_closing_price": 6, "X": 7}
    assert (b["tpex_up"], b["tpex_down"], b["tpex_flat"]) == (1180, 4667, 332)
    assert b["tpex_metadata"]["excluded_counts"] == {"---": 6843, "除息": 10, "除權": 0, "除權息": 0}
    for prefix, count in (("twse", 1383), ("tpex", 13032)):
        meta = b[f"{prefix}_metadata"]
        assert meta["source_rows"] == count
        assert "非純股票" in meta["scope"]
        assert sum(b[f"{prefix}_{x}"] for x in ("up", "down", "flat")) + sum(meta["excluded_counts"].values()) == count
    assert b["advance_ratio"] == 0.196684
    assert p["futures"] == {"tx_close": 46272, "tx_change": -741, "tx_change_pct": -1.58,
                            "tx_volume": 55226, "basis": 230.57, "contract_month": "202611", "trading_session": "一般", "selection_basis": "source-listed"}
    assert p["options"] == {"pcr": 66.18, "put_oi": 64809, "call_oi": 97930}
    assert p["futures_oi"] == {"foreign_oi": -87297, "trust_oi": 83601, "dealer_oi": 3260,
                               "foreign_change": None, "trust_change": None, "dealer_change": None}
    assert set(p["unavailable_fields"]) == {"taiex.trade_value_change_pct", "futures_oi.foreign_change",
                                           "futures_oi.trust_change", "futures_oi.dealer_change"}
    for path, reason in p["unavailable_fields"].items():
        section, key = path.split(".")
        assert p[section][key] is None and reason["reason"] == "source_not_provided" and reason["detail"]
    assert p["units"]["institutional"] == "shares"
    assert p["units"]["futures_oi"] == "contracts"
    assert p["units"]["options.pcr"] == "percent"


def test_fixture_provenance():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert len(manifest["sources"]) == 6
    for name, info in manifest["sources"].items():
        assert len(info["source_sha256"]) == 64
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == info["fixture_sha256"]


@pytest.mark.parametrize("name,parser", [("twse-mi-index", market.parse_twse_quotes),
                                        ("twse-t86", market.parse_twse_institutional),
                                        ("tpex-quotes", market.parse_tpex_quotes)])
@pytest.mark.parametrize("date", [None, "", "20261021", "20260230", "115/10/22", "2026-1-22", "garbage"])
def test_source_dates_fail(name, parser, date):
    data = official(name)
    data["date"] = date
    with pytest.raises(ValueError):
        parser(data, DATE)


@pytest.mark.parametrize("value", [None, "", "---", "garbage", "NaN", "Infinity", "1,23", "1+2", True])
def test_unknown_numeric_is_not_zero(value):
    data = official("tpex-quotes")
    t = table(data, "漲跌")
    set_cell(t, 0, "漲跌", value)
    if value == "---":
        b, errors = market.parse_tpex_quotes(data, DATE)
        assert not errors and b["tpex_flat"] == 332 and b["tpex_metadata"]["excluded_counts"]["---"] == 6844
    else:
        with pytest.raises(ValueError):
            market.parse_tpex_quotes(data, DATE)


@pytest.mark.parametrize("name,parser,field", [("twse-mi-index", market.parse_twse_quotes, "漲跌價差"),
                                              ("tpex-quotes", market.parse_tpex_quotes, "漲跌")])
@pytest.mark.parametrize("damage", ["empty", "unknown_field", "short_row", "duplicate", "duplicate_field"])
def test_incomplete_tables_fail(name, parser, field, damage):
    data = official(name)
    t = table(data, field)
    if damage == "empty":
        t["data"] = []
    elif damage == "unknown_field":
        t["fields"][t["fields"].index(field)] = "未知欄"
    elif damage == "short_row":
        t["data"][0].pop()
    elif damage == "duplicate":
        t["data"].append(copy.deepcopy(t["data"][0]))
    else:
        t["fields"][0] = t["fields"][1]
    with pytest.raises(ValueError):
        parser(data, DATE)


@pytest.mark.parametrize("prefix,parser,name,field", [("twse", market.parse_twse_quotes, "twse-mi-index", "漲跌價差"),
                                                     ("tpex", market.parse_tpex_quotes, "tpex-quotes", "漲跌")])
@pytest.mark.parametrize("direction", ["+", "-", "flat"])
def test_actual_zero_up_or_down_is_valid(prefix, parser, name, field, direction):
    data = official(name)
    t = table(data, field)
    t["data"] = [t["data"][0]]
    if "totalCount" in t:
        t["totalCount"] = 1
    set_cell(t, 0, field, "0.00" if direction == "flat" else "0.43" if direction == "+" else "-0.43")
    if prefix == "twse":
        set_cell(t, 0, "漲跌(+/-)", "<p> </p>" if direction == "flat" else f"<p>{direction}</p>")
    parsed = parser(data, DATE)
    b = parsed[1] if prefix == "twse" else parsed[0]
    assert not parsed[-1]
    assert (b[prefix + "_up"], b[prefix + "_down"], b[prefix + "_flat"]) == {
        "+": (1, 0, 0), "-": (0, 1, 0), "flat": (0, 0, 1)}[direction]


@pytest.mark.parametrize("field,value", [("漲跌(+/-)", "?"), ("漲跌價差", ""), ("收盤價", "unknown"),
                                        ("成交股數", None), ("成交筆數", "0.5"), ("成交金額", "---")])
def test_twse_bad_quote_fields_fail(field, value):
    data = official("twse-mi-index")
    set_cell(table(data, "證券代號"), 0, field, value)
    with pytest.raises(ValueError):
        market.parse_twse_quotes(data, DATE)


def test_index_uses_fields_and_exact_name():
    data = official("twse-mi-index")
    for t in data["tables"]:
        t["title"] = "測試標題不含收盤指數"
    data["tables"].reverse()
    result, _, errors = market.parse_twse_quotes(data, DATE)
    assert not errors and result["close"] == 46041.43 and result["change"] == -846.34


def test_t86_partial_numeric_missing_is_error():
    data = official("twse-t86")
    set_cell(data, 3, "投信買賣超股數", "")
    with pytest.raises(ValueError):
        market.parse_twse_institutional(data, DATE)


def test_future_selection_shuffled_spread_weekly_expired_and_other_contracts():
    rows = official("taifex-futures")
    template = next(r for r in rows if r["Contract"] == "TX" and r["TradingSession"] == "一般")
    for month in ("202609", "202608", "202611W1", "202610/202611"):
        rows.append(dict(template, **{"ContractMonth(Week)": month, "Last": "1", "Volume": "1"}))
    rows.append(dict(template, Contract="TXO", Last="2"))
    random.Random(17).shuffle(rows)
    f, _, _, errors = taifex(futures=rows)
    assert not errors and f["contract_month"] == "202611" and f["tx_close"] == 46272 and f["tx_volume"] == 55226


@pytest.mark.parametrize("source", ["futures", "pcr", "oi"])
@pytest.mark.parametrize("damage", ["empty", "wrong_date", "missing_date", "malformed_date", "duplicate", "bad_number", "missing_field"])
def test_taifex_missing_stale_or_conflicting_sources(source, damage):
    rows = official("taifex-" + source)
    if source == "futures":
        row = next(r for r in rows if r["Contract"] == "TX" and r["TradingSession"] == "一般")
        field = "Last"
    else:
        row = rows[0]
        field = "PutCallOIRatio%" if source == "pcr" else "OpenInterest(Net)"
    if damage == "empty":
        rows = []
    elif damage == "wrong_date":
        for r in rows:
            r["Date"] = "20261021"
    elif damage == "missing_date":
        row.pop("Date")
    elif damage == "malformed_date":
        row["Date"] = "today"
    elif damage == "duplicate":
        rows.append(dict(row, **{field: "99999"}))
    elif damage == "bad_number":
        row[field] = ""
    else:
        row.pop(field)
    assert taifex(**{source: rows})[-1]


def test_oi_requires_each_institution_and_exact_contract():
    rows = official("taifex-oi")
    rows = [r for r in rows if not (r["ContractCode"] == "臺股期貨" and r["Item"] == "投信")]
    assert taifex(oi=rows)[-1]


def test_pcr_history_does_not_override_target_day():
    rows = list(reversed(official("taifex-pcr")))
    _, _, options, errors = taifex(pcr=rows)
    assert not errors and options["pcr"] == 66.18


@pytest.mark.parametrize("source", list(ENDPOINTS.values()))
@pytest.mark.parametrize("failure", [None, [], RuntimeError("固定來源下載失敗")])
def test_main_failure_persists_diagnostic_and_nonzero(monkeypatch, tmp_path, capsys, source, failure):
    replay(monkeypatch, {source: failure})
    output = tmp_path / "diagnostic.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, output=str(output), twse_t86_input=None))
    assert market.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"
    p = json.loads(output.read_text())
    assert p["status"] == "error" and p["errors"]
    assert p["summary"]["domestic_context_label"] == "UNKNOWN"
    source_key = "twse" if source.startswith("twse") else "tpex" if source.startswith("tpex") else "taifex"
    assert p["source_status"][source_key]["status"] == "error"
    if source in {"twse-mi-index", "tpex-quotes"}:
        assert p["breadth"]["advance_ratio"] is None
    if source in {"twse-mi-index", "taifex-futures"}:
        assert p["futures"]["basis"] is None


def test_main_success_writes_to_tmp_path(monkeypatch, tmp_path, capsys):
    replay(monkeypatch)
    output = tmp_path / "market.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(date=DATE, output=str(output), twse_t86_input=None))
    assert market.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "OK"
    assert json.loads(output.read_text())["status"] == "ok"


@pytest.mark.parametrize("bad_input", ["date", "snapshot"])
def test_main_input_failure_keeps_diagnostic(monkeypatch, tmp_path, capsys, bad_input):
    output = tmp_path / "error.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(
        date="not-a-date" if bad_input == "date" else DATE, output=str(output),
        twse_t86_input=str(tmp_path / "missing.json") if bad_input == "snapshot" else None))
    assert market.main() == 1
    p = json.loads(output.read_text())
    assert p["status"] == "error" and p["errors"]
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"


@pytest.mark.parametrize("name,parser,key", [("tpex-quotes", market.parse_tpex_quotes, "totalCount"),
                                            ("twse-t86", market.parse_twse_institutional, "total")])
def test_declared_row_count_rejects_partial_source(name, parser, key):
    data = official(name)
    t = data if key == "total" else table(data, "漲跌")
    t["data"].pop()
    with pytest.raises(ValueError, match="宣告筆數"):
        parser(data, DATE)


def test_tpex_nested_date_conflict():
    data = official("tpex-quotes")
    table(data, "漲跌")["date"] = "115/10/21"
    with pytest.raises(ValueError, match="日期"):
        market.parse_tpex_quotes(data, DATE)


def test_t86_snapshot_reuse_with_official_response(monkeypatch):
    from app.tskg.twse_t86 import build_t86_snapshot
    snapshot = build_t86_snapshot(official("twse-t86"), requested_trade_date=DATE,
                                  retrieved_at="2026-10-22T10:00:00Z")
    replay(monkeypatch, {"twse-t86": AssertionError("重用 snapshot 不應下載 T86")})
    p = market.build_market_context(DATE, twse_t86_snapshot=snapshot)
    assert p["status"] == "ok"
    assert p["institutional"] == {"foreign_net": -284113812, "trust_net": -14647281, "dealer_net": -1553936358}


def test_t86_snapshot_wrong_date_is_error(monkeypatch):
    replay(monkeypatch)
    p = market.build_market_context(DATE, twse_t86_snapshot={"trade_date": "2026-10-21"})
    assert p["status"] == "error" and "twse" in p["errors"]


@pytest.mark.parametrize("source", ["futures", "pcr", "oi"])
def test_identical_duplicate_is_not_silently_accepted(source):
    rows = official("taifex-" + source)
    row = next(r for r in rows if r.get("Contract") == "TX" and r["TradingSession"] == "一般") if source == "futures" else rows[0]
    rows.append(copy.deepcopy(row))
    assert taifex(**{source: rows})[-1]


def test_unknown_session_is_error():
    rows = official("taifex-futures")
    row = next(r for r in rows if r["Contract"] == "TX" and r["TradingSession"] == "一般")
    row.pop("TradingSession")
    assert taifex(futures=rows)[-1]


def test_index_duplicate_and_missing_numeric():
    data = official("twse-mi-index")
    t = table(data, "指數")
    row = next(r for r in t["data"] if r[0] == "發行量加權股價指數")
    t["data"].append(copy.deepcopy(row))
    with pytest.raises(ValueError, match="重複"):
        market.parse_twse_quotes(data, DATE)
    t["data"].pop()
    row[t["fields"].index("漲跌點數")] = ""
    with pytest.raises(ValueError):
        market.parse_twse_quotes(data, DATE)


def test_source_listed_current_month_survives_third_wednesday_postponement():
    """順延場景為契約邊界測試，不宣稱 10/22 真實來源有此契約。"""
    rows = official("taifex-futures")
    row = next(r for r in rows if r["Contract"] == "TX" and r["TradingSession"] == "一般")
    rows.append(dict(row, **{"ContractMonth(Week)": "202610", "Last": "46000", "Volume": "123"}))
    f, _, _, errors = taifex(futures=list(reversed(rows)))
    assert not errors
    assert f["contract_month"] == "202610" and f["tx_close"] == 46000
    assert f["selection_basis"] == "source-listed"


def test_standalone_verifier_uses_error_contract_and_isolated_output(tmp_path):
    from scripts import verify_market_context_fetcher as verifier
    output = tmp_path / "verifier.json"
    assert verifier.main(["--output", str(output)]) == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "OK"
    assert payload["checks"]["source_failure_is_error"] is True
    assert not payload["failed"]
