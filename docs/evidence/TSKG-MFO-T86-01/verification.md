# TSKG-MFO-T86-01 Verification

## Status

```text
status: PARTIAL
technical_access: GO
strict_parser: GO
atomic_local_artifact: GO
daily_schedule_wiring: GO
market_context_single-fetch_reuse: GO
api_llm_redistribution: BLOCKED
formal_rate_retention_approval: BLOCKED
```

`PARTIAL` 只反映治理與下游再利用仍未核准；本機逐日技術功能與既有排程接點已完成。

## Synthetic evidence

- `tests/test_tskg_twse_t86.py`
  - 19 個官方欄位完整映射。
  - 所有數值保持 integer `SHARE`。
  - buy/sell/net、dealer total、all institutional total 皆 fail-loud。
  - duplicate/date/unit/row width/count/checksum corruption 均拒絕。
  - 單次 fetch 測試確認 HTTP GET 次數為 1、timeout=20、query 固定。
  - atomic write/load round-trip 通過。
- `tests/test_tskg_t86_automation.py`
  - daily dry-run 先出現 `tskg.t86`，再把同一 artifact 以 `--twse-t86-input` 傳給 market-context。
  - disabled path 保留既有 market-context 行為。
- `scripts/verify_market_context_fetcher.py`
  - `MARKET_CONTEXT_FETCHER_OK`。
  - 有 T86 snapshot 時，synthetic gate 明確拒絕第二次 T86 endpoint 呼叫。
  - 同時修復既有 parser 遺漏的官方欄位 `外陸資買賣超股數(不含外資自營商)`。

## Live read-only evidence

```text
observed_on: 2026-07-20
trade_date: 2026-07-17
endpoint: https://www.twse.com.tw/rwd/zh/fund/T86
method: GET
request_count: 1
credentials: none
select_type: ALLBUT0999
response_format: json
response_stat: OK
field_count: 19
row_count: 1337
unit: SHARE
canonical_sha256: b8a89322e7e2c4514a562c70fe9fd7d3351d31c54099659294a4b639902dd49a
artifact: artifacts/tskg/t86/twse_t86_2026-07-17.json
artifact_git_status: ignored runtime output
```

真實 1,337 列全部通過欄位、整數、唯一代碼與算術一致性 gate。第一次在 restricted sandbox 執行時遇到 DNS 權限限制；取得網路核准後，同一 command 成功。這是執行環境限制，不是來源或 parser 失敗。

## Regression evidence

```text
unittest discovery: 62/62 PASS
compileall: PASS
market-context verifier: PASS
daily market coverage gate: PASS
daily pipeline window override gate: PASS
resource guard: PASS
git diff --check: PASS
```

## Remaining limits

- 尚未核准正式 rate/concurrency 契約；實作採單次 GET、concurrency=1、無 retry loop。
- 正規化 snapshot 只保存在本機 ignored artifact；長期 retention、API／LLM redistribution 未核准。
- T86 是上市市場；上櫃 TPEx 法人資料需獨立來源卡。
- T86 提供股數，不提供精確 TWD 淨買賣金額，因此不映射到 MFO-01 TWD contract。
