# A5 Fog marker clear 後未獲自然派發

日期：2026-09-05

狀態：`NO-GO / BLOCKED_BY_GUI_LAUNCHD_DOMAIN`

## 已授權動作

Owner 明確授權只清除 Fog 的單一 restart-denied marker，等待下一個自然 15 分鐘週期並立即取證；不允許 manual run、kickstart、launchd reload 或其他 marker mutation。

清除前確認：

- Runtime fixed SHA：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`，detached checkout clean。
- Marker 是一般檔案、不是 symlink；SHA-256 為 `f5f99e687dd87bbe89212bb399aee0392ef709628c0c4e626220438f0cb40a2f`，與已保存原始證據一致。
- Marker job 為 `fog-research-worker`，唯一 reason 為 `LIVE_SAMPLE_CADENCE_EXCEEDED`，`automatic_clear_allowed=false`。
- Production storage measure=`PASS`；host free bytes=`35836211200`，memory pressure=`1`，swap bytes=`1476720066`。
- Fog 沒有執行中 supervisor/child，lock 未被持有。

2026-09-05 02:21–02:22 +0800 只刪除：

`/Users/mattkuo/TOP10-runtime-automation/logs/storage_safety/restart_denied/fog-research-worker.json`

刪除後已驗證路徑不存在；未修改其他 marker、plist、runtime SHA 或 launchd state。

## 自然週期結果

- 2026-09-05 02:22:17 +0800 的監看基準：`runs=7`、`state=not running`。
- 連續監看超過一個完整 900 秒 interval，`runs` 未增加。
- 2026-09-05 10:40:41 +0800 再查仍為 `runs=7`、`state=not running`、`pended nondemand spawn=interval`、last exit `75`。
- Marker 持續不存在；latest receipt 仍停在 2026-09-04 21:42:26，worker log 仍停在 2026-09-04 20:12:14。
- 因 scheduler 沒建立第 8 次 invocation，本輪沒有新 Fog receipt，也沒有再次 cadence failure 可供判決。

## Root cause evidence

macOS unified log 顯示：

1. 2026-09-04 21:54:20 +0800，`osascript` 啟動 System Events；loginwindow 收到 `kAERestart`，以無確認 UI 模式開始 Restart。
2. 2026-09-04 21:54:39 起，多個 GUI LaunchAgent 開始出現 `pending spawn, domain in on-demand-only mode`。
3. 2026-09-04 21:55:05 +0800，Restart 因 `cmux` 無法結束而被中斷。
4. 2026-09-04 21:57:26 +0800，Fog interval event 明確回 `domain response: 36`，同時記錄 `pending spawn, domain in on-demand-only mode: com.new-top10.fog-research-worker`。
5. 到 2026-09-05 10:40，GUI domain 仍未恢復 interval dispatch。

同一時間窗的 `project-memory-sweep`、Pantheon capacity guard、memory sync、Pantheon 主程序與 104check interval job 也得到相同 response，證明是 GUI launchd domain 共通狀態，不是 Fog wrapper、storage guard 或 plist 單點故障。

## Verdict

Marker clear 本身成功且沒有復生，但 A5 retry **未執行**。目前不能宣稱 Fog 已恢復，也不能用 kickstart 補成自然週期。

下一個最小控制面動作是以新的完整 GUI login session 解除失敗 Restart 留下的 on-demand-only domain，之後繼續等待自然 900 秒 interval。登出／重開機屬新的外部控制面變更，需 Owner 另行明確授權；本輪沒有執行。
