# MARKET-CONTEXT-02-TW：台灣國內市場情境 Fetcher

日期：2026-05-29
狀態：implementation ready for review

## 任務卡

任務ID：MARKET-CONTEXT-02-TW
卡片類型｜派工對象：Market Context / Data Contract｜Codex
請讀：docs/tasks/2026-05-28_MARKET-CONTEXT-02_tw_context_handoff.md、app/market_context_fetcher.py、scripts/verify_market_context_fetcher.py
任務目的：建立台灣國內 market context artifact，輸出大盤、廣度、三大法人、台指期、期貨 OI 與選擇權背景；不接 ranking 權重、不改模型。
證據路徑：artifacts/market_context_fetcher_verification_latest.json、artifacts/market_context_YYYY-MM-DD.json

## 實作範圍

- 新增 `app/market_context_fetcher.py`。
- 新增 `scripts/verify_market_context_fetcher.py`。
- 輸出 schema：`market-context.tw.v1`。
- 外部資料源失敗時，該來源 `source_status.status=warn`，欄位保留 `null`，不整體 crash。

## 明確不做

- 不修改 `risk_adjusted_score`。
- 不修改 `RankingPolicy`。
- 不加入 LightGBM feature list。
- 不重跑 ETL、ranking、training。
- 不接 Clawd 或 daily report 文案。

## 驗收

```bash
uv run --with-requirements requirements.txt python -m py_compile app/market_context_fetcher.py scripts/verify_market_context_fetcher.py
uv run --with-requirements requirements.txt python scripts/verify_market_context_fetcher.py
git diff --check -- app/market_context_fetcher.py scripts/verify_market_context_fetcher.py docs/tasks/2026-05-29_MARKET-CONTEXT-02-TW_fetcher.md
```

## Review 重點

- `source_status` 是否能區分成功、部分缺資料、單源失敗。
- synthetic verifier 是否覆蓋完整資料與單源失敗。
- 是否有任何 production ranking/model 權重改動。
- JSON 是否禁止 NaN。
