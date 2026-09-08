# NEW-TOP10 Current Operational Frontier

更新：2026-09-08

👉 [假設與目標確認] 目標：只以目前主線與可重跑證據界定唯一前線；邊界：不重啟歷史卡、不碰 TimesFM、push、額外 production mutation 或外部 write；驗收：已整合鏈、等待條件與未 admission 候選可被明確區分。

## Current state

- Research Spine A0–A6：`COMPLETE / MAINLINE_ACCEPTED / INTEGRATED`。A5 已合併於 `bb617e9`；A6 已合併於 `2b9eccd`。A5/A6 task card 原本的 `MAINLINE_ACCEPTANCE_PENDING` 是落後狀態，現已校正。
- Research Spine B0/C0/BC：B0-P1、C0-P1、BC-CP2 current-tip baseline 與 C0-P2 已接受；BC-CP1 已決定並結案；B0-P2=`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`；B1–D1 未 admission；R14=`NO_GO_R14_INSUFFICIENT_DECISION_VALUE`。目前沒有可執行的 Research Spine implementation frontier。
- Forecast：FM0、FC1、FC2 vendor-neutral baseline 已分別合併於 `ff3d30b`、`9abc159`、`02730a7`。TimesFM 3 僅完成 restricted-shadow preflight，狀態固定為 `DEFERRED / LAST / HOLD`；未下載模型、未安裝 runtime、未執行 inference，且不是目前前線。
- TPEx TSKG：`INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO`。實作、review、repair 與狀態 reconciliation 均已存在；舊 dossier 的 `IMPLEMENTED_PENDING_REVIEW` 已校正，不得重派。
- ME-D1：第一個 bounded finalized Daily Close snapshot slice 已完成 `MAINLINE_ACCEPTED / RE-REVIEW_GO / INTEGRATED / PUSHED / NON_PRODUCTION`，整合 commit 為 `40fea63`；provider rollout、deploy 與 runtime activation仍未准入，因此不成為 operational frontier，也不影響 Fog 的獨立自然週期觀察。ME-D1 不得自行擴成完整 Market Evidence implementation。
- RADAR-01：P1-A～P1-D 已完成 `MAINLINE_ACCEPTED / RE-REVIEW_GO / VALIDATION_REPLAY_VERIFIED / INTEGRATED / PUSHED / NON_RUNTIME`。P1-C 的 516,169-row replay 產生 220 個 validation-only occurrences／217 items；P1-D 的同規模 replay 驗證 historical statistics、same-window relevant base rate、effective-N 與 deterministic content ID。四個 SignalSpec 仍全為 `CONTRACT_ONLY`，default eligible/statistics 均為 0；P1-D 是 `NOT_OOS / NOT_SEALED / NO_ELIGIBILITY_OR_RANKING_AUTHORITY`。P1-E 未准入。
- Automation runtime：Fog cadence／取樣修補與 Fog-only activation selector 已整合並推送；production Fog runtime 固定在 `c69834ae85f7cdc57761f35ce29eca129b420e98`，deployment evidence commit 為 `ea0ea5b`。2026-09-08 11:15 的 bounded activation 只將 `fog-research-worker` 切到 detached runtime `/Users/mattkuo/TOP10-runtime-automation-c69834a`；daily 與 external-review-preflight 仍指向 `bb55fc4`。Receipt 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`、CLI exit `0`；Fog 自然週期驗收仍為 `NATURAL_ACCEPTANCE_PENDING`，accepted cycles=`0`。這不是已完成的 Research Spine Card A5。
- Retrain monitor：A6 admission 後的 bounded repair、容量閘門與三輪 review／repair 已完成；production `com.new-top10.retrain` 已只以 `monitor --trigger scheduled` 接到 detached runtime `/Users/mattkuo/TOP10-runtime-automation-8fe9366`。目前 enabled、loaded、not running、runs=`0`，receipt=`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；等待下一個每日 02:00 自然週期，不得 manual run 或 `kickstart`。

## Operational frontier

Fog runtime natural-cycle acceptance 仍由既有另一 task 唯讀觀察。Research Spine 目前沒有 active implementation frontier；RADAR-01 P1-D 已在本機接受且沒有 eligibility/ranking/runtime authority。TimesFM 仍 `DEFERRED / LAST / HOLD`。

Automation P0 已收斂狀態：

1. A0 checkout isolation 已落到 installed scheduler path，development checkout 與 runtime 分離。
2. A1–A3 bounded repairs、regression evidence與雙盲 review 均完成；原 lock cleanup P1 已由 established identity fail-closed boundary 關閉。
3. 固定 SHA `c757cf2` 的兩輪代表性 Fog validation 均為 `OK`；child exit `0`、最終 process group quiescent，peak RSS 約 `659 MiB`／`594 MiB`，unknown writes 均為空；`c757cf2..c69834a` 未修改 Fog workload。
4. 最新 activation 已保存 exact Fog prestate 與原始 denial hash，只將 Fog plist 切到 `c69834a` runtime；previous `bb55fc4` Fog marker 原檔與 hash 保留，新 runtime marker absent，daily／external-review-preflight 未變。
5. Fog 等待 receipt 達成兩次連續 accepted natural cycles；不得由 fire 次數推定。既有 `top10-fog` heartbeat 維持 paused，未建立第二個 watcher；自然週期由原 `TOP10 自動化恢復主線` 對話唯讀觀察。
6. A6 五個 disabled job intent reconciliation 已完成：02:00 monitor-only `retrain` 已取得單獨 authority 並完成 bounded activation；`reference`、`external-review`、research-only `baseline-harness` 仍是未 activation 的 `SHOULD_BE_PRODUCTION` candidates；`pm-research-harness`=`SUPERSEDED`。禁止 bulk enable。

不得用 manual run、kickstart、單次 plist/launchctl 狀態或舊 artifact 代替 Fog natural-cycle acceptance。詳細 acceptance 與 hard stops 以 P0 recovery card 為準；該卡歷史內部分段標籤不得與 canonical Research Spine Card A5 混用。

其餘非 automation 狀態分成兩類：

1. `RESEARCH-FUNDAMENTAL-READINESS-01`：`COMPLETED_BLOCKED_DATA`；`VOLUME-CLIMAX-WARNING-SHADOW-01`：`COMPLETED_MONITORING`。兩者都不是待實作卡。
2. 2026-06／2026-07 文件中的 `READY_FOR_RESEARCH`、`READY_FOR_SHADOW_RERANK_GUARD`、`READY_FOR_FIRST_WAVE_RESEARCH` 是歷史狀態；後續結果已存在，未經新的 measured-gap admission 不得當成目前前線。

因此 automation 下一個動作只剩唯讀自然週期驗收：Fog 由既有 watcher 持續觀察，retrain monitor 等待下一個 02:00 排程後查核 receipt；兩者都不得用 `kickstart` 冒充 natural acceptance。新 runtime 的 Fog marker 目前不存在；若復生即 fail closed 並停止驗收。Research Spine 的 RADAR-01 P1-D 已完成並停止，不自動進 P1-E。TimesFM 仍排最後。

## Background monitors（不屬於 operational frontier）

- `CHIP-OVERLAY-SHADOW-01`、`EVENT-OVERLAY-SHADOW-01`：歷史效果應由 frozen walk-forward backtest 先行判斷；daily shadow 只保留作未來 promotion 前的額外 OOS 證據。
- Frozen backtest verdict：Chip 10%=`HISTORICAL_SUPPORT_UNCERTAIN`（114 日、mean delta `+0.002740`、95% CI `[-0.001251, +0.006371]`），目前不得 promotion；Event constrained 10%=`ROBUST_HISTORICAL_SUPPORT`（55 日、mean delta `+0.005819`、95% CI `[+0.002715, +0.008958]`），但重用 parent OOS，只能保留為 future promotion candidate。
- 2026-09-02 receipt：Chip=`22/60`、Event=`9/60`，均為 `ACCUMULATING`，且 `changes_production_ranking=false`。
- 不需等待兩者完成才能開始其他工作；未有 promotion admission 時，即使累積滿 60 筆也不會自動成為 Mainline frontier。

## Authority baseline

- local `main` 包含尚未 push 的 retrain-monitor activation commits；`origin/main` 仍為 `ea0ea5b`。production Fog runtime 固定在 `c69834ae85f7cdc57761f35ce29eca129b420e98`，daily／external-review-preflight 仍固定在 `bb55fc4c1b316c43398774133d9f6b73ecb53dbe`；retrain monitor runtime 固定在 `8fe93667e2673a366239aa84b36f481fba79d89e`。
- `docs/RESEARCH_SPINE_BACKLOG.md` 是 Research Spine 當前 canonical backlog；dated backlog、舊 task status 與 `.work` 只作 historical evidence。
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md` 是目前 automation/operations 的 P0 recovery authority；它不屬於 Research Spine，因此不得塞回 `docs/RESEARCH_SPINE_BACKLOG.md`。
- projection receipt 不等於 runtime load；缺 session evidence 的 runtime claim 一律維持 `UNKNOWN`。

## Operational boundary

- 本線可做 read-only 查核、狀態 reconciliation 與已 admission 卡的本機驗證。
- RADAR-01 P1-D 已完成 in-memory rebuildable historical statistics 與 relevant-base-rate projection；未獲新 admission 前不得修改既有 signal eligibility、持久化 statistics/occurrence，或沿用既有 scoring weights 建立 confluence authority。
- 不得以「沒有其他 executable card」作為 TimesFM admission、模型下載、runtime 安裝或外部存取授權。
- scheduler、provider、ranking、publish、production、deploy、push 與外部 write 仍須各自的明確 authority boundary。
- 本次 retrain-monitor production activation 授權已使用完畢；後續不得自行 `kickstart`、補跑、改 plist、clear marker、切換 runtime SHA、登出／重開機或送外部 write。Fog natural-cycle acceptance 仍由原對話唯讀觀察；retrain monitor 只等待 02:00 自然排程證據。
