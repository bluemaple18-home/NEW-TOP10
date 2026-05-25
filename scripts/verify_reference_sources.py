#!/usr/bin/env python3
"""驗證 reference source crawler 的關鍵契約。

這支腳本不打外部網路；它鎖住 Yahoo API 參數、HTML fallback 解析，
以及單一來源匯入時不得洗掉其他來源資料。
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.reference_sources.collectors import (  # noqa: E402
    extract_yahoo_result_stock_ids,
    yahoo_api_params,
    yahoo_concept_type,
    yahoo_quotes_api_url,
)
from scripts.import_reference_sources import (  # noqa: E402
    CONCEPT_MEMBERSHIP_FIELDS,
    load_existing_memberships,
    write_csv,
)


def main() -> int:
    failed = False
    failed = verify_yahoo_api_contract() or failed
    failed = verify_yahoo_html_fallback() or failed
    failed = verify_source_scoped_preserve() or failed
    if failed:
        return 1
    print("REFERENCE_SOURCES_OK")
    return 0


def verify_yahoo_api_contract() -> bool:
    url = (
        "https://tw.stock.yahoo.com/class-quote?"
        "category=%E8%A2%AB%E5%8B%95%E5%85%83%E4%BB%B6&categoryLabel=%E9%9B%BB%E5%AD%90%E7%94%A2%E6%A5%AD"
    )
    params = yahoo_api_params("電子產業 / 被動元件", url, offset=30)
    api_url = yahoo_quotes_api_url("https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.getClassQuotes", params)
    ok = True
    ok = ok and params["category"] == "被動元件"
    ok = ok and params["categoryLabel"] == "電子產業"
    ok = ok and params["categoryName"] == "被動元件"
    ok = ok and params["offset"] == "30"
    ok = ok and ";category=%E8%A2%AB%E5%8B%95%E5%85%83%E4%BB%B6" in api_url
    ok = ok and yahoo_concept_type("電子產業 / 被動元件") == "industry"
    ok = ok and yahoo_concept_type("概念股 / 衛星/低軌衛星") == "theme"
    ok = ok and yahoo_concept_type("上市類股 / ETF") == "asset_class"
    print(f"yahoo_api_contract: ok={ok}")
    return not ok


def verify_yahoo_html_fallback() -> bool:
    html = """
    <main>
      <h1>電子產業 / 被動元件</h1>
      <div>頁首熱門 2330.TW 2454.TW 0050.TW</div>
      <section>
        <span>股票名稱/代號</span>
        <a href="/quote/2327.TW">國巨*</a>
        <a href="/quote/2375.TW">凱美</a>
        <a href="/quote/2428.TW">興勤</a>
      </section>
      <aside>最多人瀏覽 2330.TW</aside>
    </main>
    """
    ids = extract_yahoo_result_stock_ids(html)
    ok = ids == {"2327", "2375", "2428"}
    print(f"yahoo_html_fallback: ok={ok} ids={sorted(ids)}")
    return not ok


def verify_source_scoped_preserve() -> bool:
    tmp_dir = Path(tempfile.mkdtemp(prefix="NEW-TOP10-reference-verify-"))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / "stock_concept_membership.csv"
    write_csv(
        path,
        CONCEPT_MEMBERSHIP_FIELDS,
        [
            {
                "stock_id": "2327",
                "canonical_concept_id": "yahoo_passive",
                "canonical_name": "電子產業 / 被動元件",
                "parent_concept_id": "",
                "raw_concept_name": "電子產業 / 被動元件",
                "concept_type": "industry",
                "source": "yahoo",
                "source_url": "https://tw.stock.yahoo.com/class-quote?category=x",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "confidence": "0.65",
                "match_method": "normalized_text",
            },
            {
                "stock_id": "2330",
                "canonical_concept_id": "moneydj_apple",
                "canonical_name": "Apple",
                "parent_concept_id": "",
                "raw_concept_name": "Apple",
                "concept_type": "theme",
                "source": "moneydj",
                "source_url": "https://www.moneydj.com/example",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "confidence": "0.65",
                "match_method": "normalized_text",
            },
        ],
    )
    preserved = load_existing_memberships(path, excluded_sources={"yahoo"})
    ok = len(preserved) == 1 and preserved[0].source == "moneydj" and preserved[0].stock_id == "2330"
    print(f"source_scoped_preserve: ok={ok} preserved={[(row.source, row.stock_id) for row in preserved]}")
    return not ok


if __name__ == "__main__":
    raise SystemExit(main())
