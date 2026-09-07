# ME-D1 Daily Close Snapshot Implementation Evidence

狀態：`MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / NON_PRODUCTION`

基線：`79596a11ee7803313784ff7306b772dc0b38ca1e`

## Admission 與邊界

Owner 於 2026-09-07 本對話指示 Fog 留在原對話觀察，並對其他工作明確下達「開工」。本次只 admission ME-D1 第一個 bounded Daily Close slice；Fog、完整 Market Evidence Plane、intraday、多 provider resolver/fallback/repair、scheduler、publish、deploy 與 production runtime 均不在 scope。

## 已交付 seam

1. `app/pipeline/daily_close_snapshot.py` 提供 provider-neutral Daily Close canonicalization、deterministic immutable records/manifest、loader 與 DatasetBundle component reload。
2. `app/pipeline/fetch_stage.py` 在 filter、FinMind 與 indicator enrichment 前物化並重新載入 fixed snapshot。
3. `app/research/dataset_bundle.py` 新增 versioned `STRATEGY_MATRIX_FEATURES_V2` Daily Close component；舊 v1 consumer 保持相容。
4. `app/research/run_receipts.py` 使用既有 `source_corpus/sha256` 保存 manifest/records，讓 requested/executed receipt 可定位 exact snapshot，不新增 registry 或 ledger。
5. `scripts/run_autonomous_research.py` 新增 optional `--daily-close-manifest`；未指定時維持既有 v1 行為。

## Contract evidence

- identity：canonical record content ID 與 snapshot ID 均為 SHA-256 content address。
- data：date、instrument、market、OHLCV、value 與 nullable `transactions`；required null、duplicate key、invalid market/OHLC、負 volume/value、invalid transactions 均 fail closed。
- temporal：UTC `fetched_at`、`Asia/Taipei`、versioned `15:30` Daily Close cutoff、official finalized endpoint authority；同日收盤前、未來 observation 或缺 authority 均拒絕。
- price：`UNADJUSTED / NONE` 明示且 identity-bearing。
- gaps：weekday candidates、no-observation 與 partial-market evidence 結構化保存，不把缺值推測成休市或成功。
- lineage：manifest/records 使用 corpus-relative refs；原 snapshot root 搬移後，可由 persisted receipt → DatasetBundle → refs 重建相同 snapshot。

## 驗證結果

```text
focused Daily Close / FetchStage / DatasetBundle / receipts = 74 passed
adjacent Research Spine / daily cutover / Forecast regressions = 68 passed
CLI --help = PASS
git diff --check = PASS
original Reviewer findings ME-D1-REV-001..004 = RESOLVED
original Reviewer final verdict = RE-REVIEW_GO
```

代表性 `data/clean/features.parquet` 唯讀 probe：

```text
rows = 516,169
transactions nulls before / after reload = 218,516 / 218,516
records artifact = 18,601,120 bytes
manifest = 9,814 bytes
materialize = 12.49s
reload = 7.28s
resolution_status = RESOLVED_WITH_GAPS
```

原 NO-GO payload 為 88,882,274 bytes；修復後 records 約減少 79%。

另做非門檻探索性全套測試：`1,312 passed / 82 failed / 275 subtests passed`。失敗集中在本卡未修改的 automation/storage safety，以及依賴 committed-clean-worktree 的歷史 authority 測試；首個 automation failure 單獨重跑為 `1 passed`。因此不把全套序列／環境耦合失敗冒充本卡綠燈，也不把它擴為 ME-D1 Repair Generation 2。

## Review closure

第一輪 Reviewer 退件四項：成交筆數 schema regression、finalization authority、可搬移 lineage、代表性規模 payload。第一代 bounded Repair 完成後，由同一 Reviewer 僅複核原 findings 與直接回歸，四項均判 `RESOLVED`，最終 `RE-REVIEW_GO`。

## Acceptance boundary

本卡只完成本機、非 production 的 bounded implementation acceptance。沒有 commit、push、deploy、provider rollout、runtime activation 或外部 write；後續任何此類動作仍需 Owner 另行明確授權。
