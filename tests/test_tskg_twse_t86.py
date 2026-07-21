"""TSKG-MFO-T86-01 official-shaped snapshot contract tests。"""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.tskg.twse_t86 import (
    T86SnapshotContractError,
    build_t86_snapshot,
    fetch_t86_snapshot,
    load_t86_snapshot,
    market_aggregate,
    write_t86_snapshot,
)


FIELDS = [
    "證券代號",
    "證券名稱",
    "外陸資買進股數(不含外資自營商)",
    "外陸資賣出股數(不含外資自營商)",
    "外陸資買賣超股數(不含外資自營商)",
    "外資自營商買進股數",
    "外資自營商賣出股數",
    "外資自營商買賣超股數",
    "投信買進股數",
    "投信賣出股數",
    "投信買賣超股數",
    "自營商買賣超股數",
    "自營商買進股數(自行買賣)",
    "自營商賣出股數(自行買賣)",
    "自營商買賣超股數(自行買賣)",
    "自營商買進股數(避險)",
    "自營商賣出股數(避險)",
    "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
]


def payload() -> dict[str, Any]:
    return {
        "stat": "OK",
        "date": "20260717",
        "title": "115年07月17日 三大法人買賣超日報",
        "hints": "單位：股",
        "fields": FIELDS,
        "data": [
            [
                "00632R", "元大台灣50反1   ", "4,057,000", "3,577,000", "480,000",
                "0", "0", "0", "0", "0", "0", "169,705,427",
                "300,000", "1,631,000", "-1,331,000", "182,404,427",
                "11,368,000", "171,036,427", "170,185,427",
            ],
            [
                "2330", "台積電", "17,479,318", "61,663,282", "-44,183,964",
                "10", "0", "10", "2,004,037", "515,517", "1,488,520", "2,759,348",
                "1,605,082", "1,888,215", "-283,133", "9,325,835",
                "6,283,354", "3,042,481", "-39,936,086",
            ],
        ],
        "selectType": "ALLBUT0999",
        "notes": ["synthetic official-shaped fixture"],
        "total": 2,
    }


class TskgTwseT86Tests(unittest.TestCase):
    def build(self, value: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_t86_snapshot(
            value or payload(),
            requested_trade_date="2026-07-17",
            retrieved_at="2026-07-20T10:00:00Z",
        )

    def test_maps_all_official_fields_and_validates_totals(self) -> None:
        snapshot = self.build()
        self.assertEqual(snapshot["schema_version"], "tskg-twse-t86-snapshot-v1")
        self.assertEqual(snapshot["unit"], "SHARE")
        self.assertEqual(snapshot["integrity"]["row_count"], 2)
        self.assertEqual(snapshot["integrity"]["field_count"], 19)
        self.assertEqual(len(snapshot["integrity"]["canonical_sha256"]), 64)
        row = snapshot["records"][0]
        self.assertEqual(row["stock_id"], "00632R")
        self.assertEqual(row["stock_name"], "元大台灣50反1")
        self.assertEqual(row["foreign_ex_dealer_net_shares"], 480000)
        self.assertEqual(row["dealer_total_net_shares"], 169705427)
        self.assertEqual(row["all_institutional_net_shares"], 170185427)

    def test_checksum_is_independent_of_source_row_order(self) -> None:
        original = self.build()
        reordered_payload = payload()
        reordered_payload["data"].reverse()
        reordered = self.build(reordered_payload)
        self.assertEqual(original["records"], reordered["records"])
        self.assertEqual(
            original["integrity"]["canonical_sha256"],
            reordered["integrity"]["canonical_sha256"],
        )

    def test_atomic_roundtrip_and_market_aggregate(self) -> None:
        snapshot = self.build()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "snapshot.json"
            written = write_t86_snapshot(snapshot, path)
            loaded = load_t86_snapshot(written)
        self.assertEqual(snapshot, loaded)
        aggregate = market_aggregate(loaded)
        # 既有 market-context 的 foreign_net 明確排除外資自營商；snapshot 仍完整保存該欄。
        self.assertEqual(loaded["records"][1]["foreign_dealer_net_shares"], 10)
        self.assertEqual(aggregate["foreign_net"], -43703964)
        self.assertEqual(aggregate["trust_net"], 1488520)
        self.assertEqual(aggregate["dealer_net"], 172464775)

    def test_fetch_uses_exactly_one_get_with_bounded_request(self) -> None:
        calls: list[dict[str, Any]] = []

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return payload()

        def fake_get(url: str, **kwargs: Any) -> Response:
            calls.append({"url": url, **kwargs})
            return Response()

        snapshot = fetch_t86_snapshot(
            "2026-07-17",
            http_get=fake_get,
            retrieved_at="2026-07-20T10:00:00Z",
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["params"]["date"], "20260717")
        self.assertEqual(calls[0]["params"]["selectType"], "ALLBUT0999")
        self.assertEqual(calls[0]["params"]["response"], "json")
        self.assertEqual(calls[0]["timeout"], 20)
        self.assertEqual(snapshot["integrity"]["row_count"], 2)

    def test_schema_and_integrity_fail_loud(self) -> None:
        mutations = {
            "non-ok": lambda value: value.update({"stat": "很抱歉，沒有符合條件的資料!"}),
            "date mismatch": lambda value: value.update({"date": "20260716"}),
            "wrong unit": lambda value: value.update({"hints": "單位：元"}),
            "missing field": lambda value: value["fields"].pop(),
            "count mismatch": lambda value: value.update({"total": 3}),
            "duplicate stock": lambda value: value["data"].append(deepcopy(value["data"][0])),
            "non-string stock id": lambda value: value["data"][0].__setitem__(0, None),
            "non-string stock name": lambda value: value["data"][0].__setitem__(1, None),
            "bad integer": lambda value: value["data"][0].__setitem__(2, "1.5"),
            "bad row width": lambda value: value["data"][0].pop(),
            "bad foreign net": lambda value: value["data"][0].__setitem__(4, "1"),
            "bad dealer total": lambda value: value["data"][0].__setitem__(11, "1"),
            "bad overall total": lambda value: value["data"][0].__setitem__(18, "1"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                malformed = payload()
                mutate(malformed)
                with self.assertRaises(T86SnapshotContractError):
                    self.build(malformed)

    def test_corrupted_saved_snapshot_is_rejected(self) -> None:
        snapshot = self.build()
        snapshot["records"][0]["foreign_ex_dealer_net_shares"] = 0
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(T86SnapshotContractError):
                load_t86_snapshot(path)

    def test_corrupted_saved_stock_id_type_uses_contract_error(self) -> None:
        snapshot = self.build()
        snapshot["records"][0]["stock_id"] = 632  # type: ignore[assignment]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(T86SnapshotContractError):
                load_t86_snapshot(path)


if __name__ == "__main__":
    unittest.main()
