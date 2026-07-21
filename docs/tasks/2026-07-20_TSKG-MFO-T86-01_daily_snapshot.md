---
card_id: TSKG-MFO-T86-01
chain_id: TSKG-MFO
title: TWSE T86 daily security snapshot
status: DELIVERED_CANDIDATE
type: implementation
owner: Codex 主線
assignee_model: 5.6 Sol
created_on: 2026-07-20
operation_level: local_scheduled_read_only
depends_on: TSKG-MFO-SRC-01
---

# TSKG-MFO-T86-01：TWSE T86 每日逐證券快照

## Goal

沿用既有 daily automation 已經執行的官方 T86 唯讀 GET，把同一次回應保存為逐證券、版本化、可重跑的本機 artifact，再讓 market-context 從 artifact 聚合，避免每日重複呼叫 T86。

```text
TWSE T86 one GET / business date
  → strict source schema parser
  → normalized SHARE snapshot + checksum
  → atomic local artifact
  → market-context aggregate reuse
```

## Source boundary

- Endpoint：`https://www.twse.com.tw/rwd/zh/fund/T86`
- Method：單次 `GET`，concurrency=1，無 retry loop。
- Query：`date=YYYYMMDD&selectType=ALLBUT0999&response=json`。
- Authentication：不送登入或 token。
- Output：`artifacts/tskg/t86/twse_t86_YYYY-MM-DD.json`，runtime artifact 不進 git。
- 單位：官方回應 `單位：股`，所有 normalized metric 明確使用 `_shares`；不得映射成 MFO-01 的 TWD value。
- 下游：只供本機 read-only artifact 與 market-context aggregate；不開 API／LLM redistribution、不改 ranking。

## Acceptance

1. 19 個官方欄位完整映射；欄位漂移、非 `OK`、日期不符、筆數不符、重複代碼或非整數 fail loud。
2. 每列 buy-sell=net、dealer total、all-institutional total 一致性皆驗證。
3. snapshot 具有 schema/source/date/unit/retrieved time/row count/checksum，重排輸入後 checksum 一致。
4. 原子寫入後可 round-trip 驗證；失敗不得留下半份正式 artifact。
5. daily automation 先產生 T86 artifact，再把該 artifact 傳給 market-context；正常路徑每個 business date 只呼叫 T86 一次。
6. T86 ingestion 失敗須留 FAILED evidence，但不得改模型、ranking 或假造資料；market-context 可沿用原 fail-soft fallback。
7. 完成 synthetic tests、automation dry-run wiring、真實單日唯讀 smoke、既有 market-context／TSKG regression。

## Deferred

- TPEx 法人資料、TWD 成交金額換算、Theme aggregation、late-correction policy、API／DB／UI。
- rate、長期 retention 與 redistribution 的正式法務／治理核准仍需 owner 另行決策；本卡只實作與既有 T86 daily call 等量的本機使用。

## Verification

- `tests/test_tskg_twse_t86.py`
- `tests/test_tskg_t86_automation.py`
- `scripts/verify_market_context_fetcher.py`
- 真實交易日 `2026-07-17` 單次 smoke
- `git diff --check`

## Result

`DELIVERED_CANDIDATE / LOCAL SCHEDULED PATH GO`

- 官方 19 欄 strict parser、17 個 share metrics、算術 gate、deterministic checksum 與原子寫入已完成。
- daily automation 先產生逐證券 snapshot，market-context 再從 artifact 聚合，正常路徑不重複呼叫 T86。
- 真實交易日 `2026-07-17` 取得 1,337 列並完整通過 parser。
- 本卡不把 `SHARE` 偽裝成 TWD，也不開 API／LLM redistribution 或 ranking feature。
- Evidence：`docs/evidence/TSKG-MFO-T86-01/verification.md`。
