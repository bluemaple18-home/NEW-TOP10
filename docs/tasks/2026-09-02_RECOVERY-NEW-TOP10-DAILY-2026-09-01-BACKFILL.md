---
id: RECOVERY-NEW-TOP10-DAILY-2026-09-01-BACKFILL
status: completed
type: acceptance
---

# 2026-09-01 daily 正式資料回補

## Root question

在不重送舊 Discord／ops 訊息、不碰 2026-09-02 尚未收盤資料的前提下，補回 2026-09-01 因 storage guard 誤殺而缺少的正式 daily artifacts。

## 已確認缺口

- 2026-08-31：正式 daily、ranking 與 Clawd send receipt 已成功。
- 2026-09-01：排程啟動後被舊 swap-only stop loss 中止，缺 `artifacts/ranking_2026-09-01.csv` 與同日完整 daily artifacts。
- 2026-09-02：本卡開工時間仍在收盤前，不是缺漏日，不得提前補造。
- 2026-08-29、2026-08-30：週末，不是缺漏交易日。

## 執行契約

- 固定 source commit：`2999daa`。
- 唯一 run date：`2026-09-01`。
- 正式入口：`scripts/run_with_storage_guard.sh daily /bin/bash scripts/run_daily.sh`，以 `TOP10_RUN_DATE=2026-09-01` 明確指定日期。
- 允許外部 read：交易所公開行情／既有 daily data providers。
- 禁止 external write：不得執行 `run_daily_publish.sh`、Clawd live send、ops live send、external review、scheduler reload／kickstart。
- 不修改模型、權重、signals config、storage budget 或 launchd。
- 同一 blocker 第三次失敗即停止；不得無限重試。

## 驗收

- guard receipt `status=OK`、child exit `0`、無 stop reasons。
- `automation_status.json` 與 snapshot 均為 `status=OK`、`run_date=2026-09-01`。
- `ranking_2026-09-01.csv` 存在、10 rows、必要欄位非空。
- daily summary、report、Clawd payload/message 均存在，但不存在 `clawd_send_status_2026-09-01.json`。
- data freshness 最新日期至少為 2026-09-01，且不得包含 2026-09-02 未收盤資料。
- 2026-08-31 既有正式 ranking hash 不變。
- 保存 log、artifact hashes、resource receipt 與完整驗收結論。

## Rollback / stop

- 若任何日期穿越、外部 send、非本卡正式路徑異常變更、容量停損或狀態非 OK，立即停止並保留現場，不猜測性刪除正式資料。
- 本卡不授權自動刪除 formal artifacts；需要 rollback 時先依 pre-run manifest 精準列出本輪新增／變更後再決定。

## 完成結果

- 2026-09-02 10:45:59（Asia/Taipei）從 commit `2999daa` 啟動；11:17:08 完成，guard child exit `0`。
- 只回補 `2026-09-01`；未執行 2026-09-02，也未處理週末。
- ranking 共 10 rows；clean features／events／universe 最新日期均為 `2026-09-01`。
- 未產生 `artifacts/clawd_send_status_2026-09-01.json`，因此沒有重送舊訊息。
- 2026-08-31 ranking SHA-256 維持 `afbf3d916a00555afcb4b762683658b4ac9bf0a47ad8f5c4e920af3d6e8a22e2`。
- 原 2026-09-01 restart denial marker 已原樣保存於 evidence，讓修正後的正式補跑可以進行；未刪除。
- 驗收證據：`docs/evidence/RECOVERY-NEW-TOP10-DAILY-2026-09-01-BACKFILL/acceptance.md`。
