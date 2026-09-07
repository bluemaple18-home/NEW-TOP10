# REPAIR-NEW-TOP10-FOG-RESOURCE-BUDGET-01

- **objective**：降低 Fog 對互動電腦的影響；自然週期仍可前進，但 replay drain 預設每輪最多 6 筆、1 batch、1800 秒，LaunchAgent 每 3600 秒才重試，並以 `Nice=10` 保留前景程式優先權。
- **scope**：只准修改 `scripts/run_fog_research_worker.sh`、`scripts/run_representative_replay_drain_worker.py`、`scripts/com.new-top10.fog-research-worker.plist`、`scripts/setup_launchd.sh`、直接相關測試與本卡 evidence；先建立可重現 RED，再做最小 GREEN。
- **constraints**：只動隔離開發 worktree；不得停止 2026-09-07 正在跑的自然週期，不得操作 launchctl、runtime checkout、marker、production、merge、push 或 deploy；不得新增 daemon、使用者活動偵測器或第二套 scheduler；保留 storage guard、單實例、receipt 與既有失敗語意。
- **acceptance**：測試須證明 plist 為 `ProcessType=Background`、`LowPriorityIO=true`、`Nice=10`、`StartInterval=3600`，Fog wrapper 傳入 6/1/1800，環境變數仍可明示覆寫；既有 Fog/replay/storage targeted tests、shell syntax、`git diff --check` 全綠；回報 candidate SHA、diff、測試與 residual risk。
- **status / handoff / evidence**：`MERGED_LOCAL / NOT_PUSHED / NOT_DEPLOYED / NOT_ACTIVATED`；candidate `20857a7c826f97991c5a9d2a3c6cf7253866c128` 已依 Owner 2026-09-07「授權」以 fast-forward 整合至本機 `main`；`extra_generation_approval_ref=Owner interactive 2026-09-07「授權 繼續」`；Mainline 重跑 process-tree 10 tests、Fog/storage 91 tests、resource/wiring/signal/retry/plist/diff checks 全綠，原 deadline 與 PGID containment P1 均關閉；尚未 push、deploy 或 activation；production runtime 仍為舊版，舊 Fog run 已安全停止並由 denial marker 維持 fail-closed。
