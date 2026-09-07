# NEW-TOP10 Current Operational Frontier

更新：2026-09-07

👉 [假設與目標確認] 目標：只以目前主線與可重跑證據界定唯一前線；邊界：不重啟歷史卡、不碰 TimesFM、push、額外 production mutation 或外部 write；驗收：已整合鏈、等待條件與未 admission 候選可被明確區分。

## Current state

- Research Spine A0–A6：`COMPLETE / MAINLINE_ACCEPTED / INTEGRATED`。A5 已合併於 `bb617e9`；A6 已合併於 `2b9eccd`。A5/A6 task card 原本的 `MAINLINE_ACCEPTANCE_PENDING` 是落後狀態，現已校正。
- Research Spine B0/C0/BC：B0-P1、C0-P1、BC-CP2 current-tip baseline 與 C0-P2 已接受；BC-CP1 已決定並結案；B0-P2=`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`；B1–D1 未 admission；R14=`NO_GO_R14_INSUFFICIENT_DECISION_VALUE`。目前沒有可執行的 Research Spine implementation frontier。
- Forecast：FM0、FC1、FC2 vendor-neutral baseline 已分別合併於 `ff3d30b`、`9abc159`、`02730a7`。TimesFM 3 僅完成 restricted-shadow preflight，狀態固定為 `DEFERRED / LAST / HOLD`；未下載模型、未安裝 runtime、未執行 inference，且不是目前前線。
- TPEx TSKG：`INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO`。實作、review、repair 與狀態 reconciliation 均已存在；舊 dossier 的 `IMPLEMENTED_PENDING_REVIEW` 已校正，不得重派。
- ME-D1：第一個 bounded finalized Daily Close snapshot slice 已在本機完成 `MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / NON_PRODUCTION`，整合 commit 為 `40fea63`；未 push、provider rollout、deploy 或 runtime activation，因此不成為 operational frontier，也不影響 Fog 的獨立自然週期觀察。ME-D1 仍為 `NOT_ADMITTED`，不得自行擴成 implementation。
- RADAR-01：P1-A 與 P1-B finalized-Daily read-only scanner 已完成 `MAINLINE_ACCEPTED_LOCAL / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`。P1-B targeted 90 tests 與 516,169-row validation replay 通過；目前四個 SignalSpec 仍全為 `CONTRACT_ONLY`、default Radar eligible count=0。P1-C 至 P1-E 未准入。
- Automation runtime：Fog invocation-bound terminal evidence 與 cross-job shared meter 修復已整合至固定 commit `bb55fc4c1b316c43398774133d9f6b73ecb53dbe`。2026-09-07 19:03 的 bounded activation 已將 daily、external-review-preflight、fog-research-worker 三條 installed launchd job 切到 detached runtime `/Users/mattkuo/TOP10-runtime-automation-bb55fc4`；receipt 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`、CLI exit `0`。Fog 自然週期驗收仍為 `NATURAL_ACCEPTANCE_PENDING`；這不是已完成的 Research Spine Card A5。

## Operational frontier

Fog runtime natural-cycle acceptance 仍由既有另一 task 唯讀觀察。Research Spine 目前沒有 active implementation frontier；RADAR-01 P1-B 已在本機接受且沒有 runtime authority。TimesFM 仍 `DEFERRED / LAST / HOLD`。

Automation P0 已收斂狀態：

1. A0 checkout isolation 已落到 installed scheduler path，development checkout 與 runtime 分離。
2. A1–A3 bounded repairs、regression evidence與雙盲 review 均完成；原 lock cleanup P1 已由 established identity fail-closed boundary 關閉。
3. 固定 SHA R4 兩輪代表性 validation 均為 `OK`；每輪 144/144 replay cases、child exit `0`、最終 process group quiescent，peak RSS 約 `669 MiB`／`614 MiB`。
4. 最新 activation 已保存 prestate 與原始 denial hash，三條 plist 已切到 `bb55fc4` runtime；舊 `26c8834` Fog marker 原檔與 hash 保留，新 runtime marker absent。
5. Fog 等待 receipt 達成兩次連續 accepted natural cycles；不得由 fire 次數推定。既有唯讀 watcher `top10-fog` 已原地更新到新 runtime，未建立第二個；狀態無變化時保持安靜，出現啟動、完成、失敗或需要 Owner 動作才回報。
6. A6 五個 disabled job intent reconciliation 尚未開始，維持 `pending`。

不得用 manual run、kickstart、單次 plist/launchctl 狀態或舊 artifact 代替 Fog natural-cycle acceptance。詳細 acceptance 與 hard stops 以 P0 recovery card 為準；該卡歷史內部分段標籤不得與 canonical Research Spine Card A5 混用。

其餘非 automation 狀態分成兩類：

1. `RESEARCH-FUNDAMENTAL-READINESS-01`：`COMPLETED_BLOCKED_DATA`；`VOLUME-CLIMAX-WARNING-SHADOW-01`：`COMPLETED_MONITORING`。兩者都不是待實作卡。
2. 2026-06／2026-07 文件中的 `READY_FOR_RESEARCH`、`READY_FOR_SHADOW_RERANK_GUARD`、`READY_FOR_FIRST_WAVE_RESEARCH` 是歷史狀態；後續結果已存在，未經新的 measured-gap admission 不得當成目前前線。

因此 automation 下一個動作仍只是由既有 watcher 讀取自然週期證據；不得用 `kickstart` 冒充 natural acceptance。新 runtime 的 Fog marker 目前不存在；若復生即 fail closed 並停止驗收。Research Spine 的 RADAR-01 P1-B 已完成並停止，不自動進 P1-C。TimesFM 仍排最後。

## Background monitors（不屬於 operational frontier）

- `CHIP-OVERLAY-SHADOW-01`、`EVENT-OVERLAY-SHADOW-01`：歷史效果應由 frozen walk-forward backtest 先行判斷；daily shadow 只保留作未來 promotion 前的額外 OOS 證據。
- Frozen backtest verdict：Chip 10%=`HISTORICAL_SUPPORT_UNCERTAIN`（114 日、mean delta `+0.002740`、95% CI `[-0.001251, +0.006371]`），目前不得 promotion；Event constrained 10%=`ROBUST_HISTORICAL_SUPPORT`（55 日、mean delta `+0.005819`、95% CI `[+0.002715, +0.008958]`），但重用 parent OOS，只能保留為 future promotion candidate。
- 2026-09-02 receipt：Chip=`22/60`、Event=`9/60`，均為 `ACCUMULATING`，且 `changes_production_ranking=false`。
- 不需等待兩者完成才能開始其他工作；未有 promotion admission 時，即使累積滿 60 筆也不會自動成為 Mainline frontier。

## Authority baseline

- local `main` 已包含 activation evidence、Fog natural acceptance evidence 與 shared-meter 修復，production runtime 固定在 `bb55fc4c1b316c43398774133d9f6b73ecb53dbe`；`origin/main` 尚未收到這批 local commits，未取得 push 授權。
- `docs/RESEARCH_SPINE_BACKLOG.md` 是 Research Spine 當前 canonical backlog；dated backlog、舊 task status 與 `.work` 只作 historical evidence。
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md` 是目前 automation/operations 的 P0 recovery authority；它不屬於 Research Spine，因此不得塞回 `docs/RESEARCH_SPINE_BACKLOG.md`。
- projection receipt 不等於 runtime load；缺 session evidence 的 runtime claim 一律維持 `UNKNOWN`。

## Operational boundary

- 本線可做 read-only 查核、狀態 reconciliation 與已 admission 卡的本機驗證。
- RADAR-01 P1-B 已完成 finalized-Daily read-only scanner；未獲新 admission 前不得修改既有 signal 計算、持久化 SignalOccurrence、建立統計／Radar projection，或沿用既有 scoring weights 作 confluence authority。
- 不得以「沒有其他 executable card」作為 TimesFM admission、模型下載、runtime 安裝或外部存取授權。
- scheduler、provider、ranking、publish、production、deploy、push 與外部 write 仍須各自的明確 authority boundary。
- 本次 production activation 授權已使用完畢；後續不得自行 `kickstart`、補跑、改 plist、clear 新 marker、切換 runtime SHA、登出／重開機或送外部 write。Fog natural-cycle acceptance 僅做唯讀驗收；既有 watcher 已續用。
