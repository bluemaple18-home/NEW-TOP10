# MARKET-CONTEXT-02-TW：國內 Market Context 交接

日期：2026-05-28
狀態：研究收斂完成，尚未實作
任務類型：handoff / development planning

## Root Question

TOP10new 要不要建立「台灣國內市場情境層」，用來補足 daily ranking 之外的大盤、籌碼、期貨與選擇權背景？

## 結論

要做，但第一版只做國內資料，不做國際資料。

這一層應輸出獨立 artifact：

- `artifacts/market_context_YYYY-MM-DD.json`

它的用途是：

- 幫 daily report 解釋今天市場環境。
- 幫 Clawd publish payload 產生更好的「今日大盤與資金」文字。
- 之後可做 shadow regime 研究。

它暫時不應做：

- 不改 `RankingPolicy`。
- 不改 `risk_adjusted_score`。
- 不進 LightGBM feature list。
- 不因單一外部資料源失敗阻塞 daily ranking。

## 適合 TOP10new 吸收的內容

外部 dashboard 真正值得參考的是「每日市場情境 artifact」概念，不是 UI，也不是權重公式。

第一版適合只做台灣本地資料：

- 大盤：TAIEX 收盤、漲跌、漲跌幅、成交金額、成交金額變化。
- 市場廣度：上市 / 上櫃上漲家數、下跌家數、平盤家數、上漲比例。
- 三大法人現貨：外資、投信、自營商買賣超。
- 台指期：TX 收盤、漲跌、漲跌幅、成交量、期現貨價差。
- 法人期貨 OI：外資、投信、自營台指期未平倉與變化。
- 選擇權：Put/Call Ratio、Put OI、Call OI。

第一版先不要做：

- VIX。
- US10Y。
- DXY。
- USD/JPY。
- ON RRP。
- CNN Fear & Greed。
- Crypto Fear & Greed。
- 小台 / 微台多空比。

## 資料可得性判斷

| 資料 | 可得性 | 穩定度 | 建議 |
|---|---:|---:|---|
| TAIEX 收盤 / 漲跌 / 成交金額 | 可抓 | 高 | 第一版必做 |
| 上市市場廣度 | 可抓 | 高 | 第一版必做 |
| 上櫃市場廣度 | 可抓 | 中高 | 第一版做，但允許 warn |
| 三大法人現貨 | 可抓 | 中高 | 第一版做，先以 TWSE 為主 |
| 台指期 TX 行情 | 可抓 | 高 | 第一版必做 |
| 法人期貨 OI | 可抓 | 中高 | 第一版做，清洗要保守 |
| Put/Call Ratio | 可抓 | 中 | 第一版做，失敗不擋 ranking |
| Put OI / Call OI | 可抓 | 中 | 第一版做，失敗可為 null |
| 小台 / 微台多空比 | 可推導 | 中低 | 延後 |

## 建議 Schema

```json
{
  "schema_version": "market-context.tw.v1",
  "trade_date": "YYYY-MM-DD",
  "generated_at": "ISO-8601",
  "scope": "taiwan_only",
  "source_status": {
    "twse": {"status": "ok", "data_date": "YYYY-MM-DD", "fallback_used": false, "warnings": []},
    "tpex": {"status": "warn", "data_date": null, "fallback_used": false, "warnings": []},
    "taifex": {"status": "ok", "data_date": "YYYY-MM-DD", "fallback_used": false, "warnings": []}
  },
  "taiex": {
    "close": null,
    "change": null,
    "change_pct": null,
    "trade_value": null,
    "trade_value_change_pct": null
  },
  "breadth": {
    "twse_up": null,
    "twse_down": null,
    "twse_flat": null,
    "tpex_up": null,
    "tpex_down": null,
    "tpex_flat": null,
    "advance_ratio": null
  },
  "institutional": {
    "foreign_net": null,
    "trust_net": null,
    "dealer_net": null
  },
  "futures": {
    "tx_close": null,
    "tx_change": null,
    "tx_change_pct": null,
    "tx_volume": null,
    "basis": null
  },
  "futures_oi": {
    "foreign_oi": null,
    "foreign_change": null,
    "trust_oi": null,
    "trust_change": null,
    "dealer_oi": null,
    "dealer_change": null
  },
  "options": {
    "pcr": null,
    "put_oi": null,
    "call_oi": null
  },
  "summary": {
    "domestic_context_label": "UNKNOWN",
    "notes": []
  }
}
```

## 建議落點

新增：

- `app/market_context_fetcher.py`
- `scripts/verify_market_context_fetcher.py`

可選後續：

- `scripts/generate_daily_report.py` 讀取 `market_context_YYYY-MM-DD.json`，新增市場背景摘要。
- `scripts/build_clawd_publish_payload.py` 從 daily report 取得更完整的大盤文字。

暫時不要改：

- `app/trading/ranking_policy.py`
- `app/trading/market_regime.py`
- `app/agent_b_ranking.py`
- 模型 feature contract

## Daily Pipeline 接法

建議放在 ranking 之後、daily report 之前：

```text
etl
data.validate
ranking
market.context
candidate.persistence
weekly.snapshot
daily.report
clawd.payload
daily.postcheck
```

理由：

- ranking 可獨立完成，不被 market context 資料源拖住。
- daily report 之後可以讀 market context。
- market context 若失敗，第一版只記 status warning，不應讓 daily ranking 失敗。

## 驗收條件

MARKET-CONTEXT-02-TW 完成標準：

- CLI 可執行：

```bash
cd <repo-root>
uv run --with-requirements requirements.txt python -m app.market_context_fetcher --date YYYY-MM-DD
```

- 會輸出 `artifacts/market_context_YYYY-MM-DD.json`。
- JSON 有 `schema_version = market-context.tw.v1`。
- 每個資料源都有 `status / data_date / fallback_used / warnings`。
- 單一資料源失敗時，該段欄位為 `null` 並記 warning，不整體 crash。
- 不修改 `ranking_YYYY-MM-DD.csv`。
- 不修改 `risk_adjusted_score`。
- 有驗證腳本：

```bash
cd <repo-root>
uv run --with-requirements requirements.txt python scripts/verify_market_context_fetcher.py
```

## 建議第一張實作卡

任務ID：`MARKET-CONTEXT-02-TW`

卡片類型｜派工對象：implementation｜Codex

請讀：

- `docs/tasks/2026-05-28_MARKET-CONTEXT-02_tw_context_handoff.md`
- `docs/tasks/2026-05-28_MARKET-CONTEXT-01_external_dashboard_research.md`
- `scripts/run_automation.py`
- `scripts/generate_daily_report.py`
- `app/data_fetcher.py`

任務目的：

- 建立台灣國內 market context fetcher，輸出獨立 artifact，暫不接 ranking 權重。

證據路徑：

- `artifacts/market_context_YYYY-MM-DD.json`
- `artifacts/market_context_fetcher_verification_latest.json`

## Limits

- 國際資料暫不做。
- 小台 / 微台多空比暫不做。
- 不照抄外部 dashboard UI。
- 不照抄外部戰略溫度計權重。
- 不直接改 production ranking。
- 不讓非核心資料源失敗阻塞 daily ranking。
- 文件與可複製指令只使用 repo-relative path。

## Open Questions

- 三大法人現貨第一版是否只做 TWSE，還是同步補 TPEx？
- Market context CLI 失敗時，daily pipeline 要記 `WARN` 還是完全獨立手動跑？
- Daily report 接入要放 `MARKET-CONTEXT-03`，還是和 `MARKET-CONTEXT-02-TW` 同卡完成？

## Verification

本交接只整理研究與開發邊界，未修改 production code，未跑 TOP10new tests。

已驗證：

- TWSE / TPEx / TAIFEX 都有官方 OpenAPI 入口。
- 外部 dashboard 最新公開 `latest_data.json` 仍停在 `2026-05-25 21:31:59`，不應當成 2026-05-28 即時市場資料。
- TOP10new 現有 `RankingPolicy` 會直接影響 `risk_adjusted_score`，第一版不得接入。
