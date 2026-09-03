---
id: MONITOR-NEW-TOP10-FOG-LIVE-REVALIDATION
status: IN_PROGRESS
type: operations-monitor
risk: low
model_lane: gpt-5.6-luna-medium
---

# 監督 Fog Research Worker live 重驗證

👉 [假設與目標確認] 目標：以低成本唯讀監督目前 Fog live 重驗證直到新 receipt 結案；邊界：不得修改檔案、清除 marker、重啟／停用／kickstart launchd、調整門檻、push、deploy 或操作其他 job；驗收：向 Mainline 回傳可重現的 PASS／NO-GO 證據。

## 五行派工卡

- 目標：監看 `com.new-top10.fog-research-worker` 當前 live 週期，直到產生本輪新 receipt 或 stop-loss marker。
- 範圍：唯讀檢查 launchd 狀態、`logs/storage_safety/fog-research-worker_latest.json`、`logs/storage_safety/restart_denied/fog-research-worker.json` 與本輪 worker log。
- 禁區：不得寫 repo 或 runtime、不得清 marker、不得重新啟停／kickstart、不得修改安全政策、不得 push／deploy，也不得操作其他排程。
- 驗收：結案時擷取 status／reasons、cadence、project bytes／files、host free、peak RSS、swap、unknown writes、child exit 與 process-group quiescence；未結案只回報最新實質進度。
- 交付：Mainline 可重現的最終監督摘要與 evidence 路徑；最終 GO／NO-GO 仍由 Mainline裁決。

## 固定事實

- 本輪於 2026-09-03 09:13:50 CST 啟動，worker 單輪 `max_seconds=7200`。
- 啟動時 launchd PID 為 `62523`，label enabled／running，restart-denied marker 不存在。
- 上一輪 receipt 是舊證據，不得誤判為本輪結案；必須以 mtime／本輪 run id 辨識新 receipt。
- 本輪 run id：`fog-research-2026-09-03-20260903011349818578`。

## 停止條件

- 新 receipt 結案或新 restart-denied marker 出現後停止監督並回報 Mainline。
- 若唯讀觀測能力失敗，不得改 runtime；回報 BLOCKED 與缺失證據。
