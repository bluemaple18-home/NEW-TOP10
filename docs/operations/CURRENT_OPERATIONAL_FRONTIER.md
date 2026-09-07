# NEW-TOP10 Current Operational Frontier

更新：2026-09-07

👉 [假設與目標確認] 目標：只以目前主線與可重跑證據界定唯一前線；邊界：不重啟歷史卡、不碰 TimesFM、push、額外 production mutation 或外部 write；驗收：已整合鏈、等待條件與未 admission 候選可被明確區分。

## Current state

- Research Spine A0–A6：`COMPLETE / MAINLINE_ACCEPTED / INTEGRATED`。A5 已合併於 `bb617e9`；A6 已合併於 `2b9eccd`。A5/A6 task card 原本的 `MAINLINE_ACCEPTANCE_PENDING` 是落後狀態，現已校正。
- Research Spine B0/C0/BC：B0-P1、C0-P1、BC-CP2 current-tip baseline 與 C0-P2 已接受；BC-CP1 已決定並結案；B0-P2=`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`；B1–D1 未 admission；R14=`NO_GO_R14_INSUFFICIENT_DECISION_VALUE`。目前沒有可執行的 Research Spine implementation frontier。
- Forecast：FM0、FC1、FC2 vendor-neutral baseline 已分別合併於 `ff3d30b`、`9abc159`、`02730a7`。TimesFM 3 僅完成 restricted-shadow preflight，狀態固定為 `DEFERRED / LAST / HOLD`；未下載模型、未安裝 runtime、未執行 inference，且不是目前前線。
- TPEx TSKG：`INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO`。實作、review、repair 與狀態 reconciliation 均已存在；舊 dossier 的 `IMPLEMENTED_PENDING_REVIEW` 已校正，不得重派。
- Automation runtime：resource-budget、validation confinement 與 lock identity 修復已整合至固定 commit `26c88343ccac08ce4701b785bfa2c2c82bfa446d`，並完成兩位盲審與兩輪固定 SHA 代表性 validation。2026-09-07 的 A4 bounded activation 已將 daily、external-review-preflight、fog-research-worker 三條 installed launchd job 切到 detached runtime `/Users/mattkuo/TOP10-runtime-automation-26c8834`；receipt 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`、CLI exit `0`。A5 目前為 `NATURAL_ACCEPTANCE_PENDING`。

## Operational frontier

目前唯一 active operational frontier 是 P0 的 A5 natural scheduler acceptance。Research Spine 仍無新的 executable implementation frontier；TimesFM 仍 `DEFERRED / LAST / HOLD`。

Automation P0 已收斂狀態：

1. A0 checkout isolation 已落到 installed scheduler path，development checkout 與 runtime 分離。
2. A1–A3 bounded repairs、regression evidence與雙盲 review 均完成；原 lock cleanup P1 已由 established identity fail-closed boundary 關閉。
3. 固定 SHA R4 兩輪代表性 validation 均為 `OK`；每輪 144/144 replay cases、child exit `0`、最終 process group quiescent，peak RSS 約 `669 MiB`／`614 MiB`。
4. A4 已保存 prestate 與原始 denial hash，三條 plist 已切到 `26c8834` runtime；新 runtime marker clear，舊 runtime marker僅保留作歷史證據。
5. A5 只等待兩次連續自然 Fog 週期。已設定唯讀 watcher；狀態無變化時保持安靜，出現啟動、完成、失敗或需要 Owner 動作才回報。
6. A6 五個 disabled job intent reconciliation 尚未開始，維持 `pending`。

不得用 manual run、kickstart、單次 plist/launchctl 狀態或舊 artifact 代替 A5 自然週期。詳細 acceptance 與 hard stops 以 P0 card 為準。

其餘非 automation 狀態分成兩類：

1. `RESEARCH-FUNDAMENTAL-READINESS-01`：`COMPLETED_BLOCKED_DATA`；`VOLUME-CLIMAX-WARNING-SHADOW-01`：`COMPLETED_MONITORING`。兩者都不是待實作卡。
2. 2026-06／2026-07 文件中的 `READY_FOR_RESEARCH`、`READY_FOR_SHADOW_RERANK_GUARD`、`READY_FOR_FIRST_WAVE_RESEARCH` 是歷史狀態；後續結果已存在，未經新的 measured-gap admission 不得當成目前前線。

因此下一個 Mainline 動作只是讀取自然週期證據；不得用 `kickstart` 冒充 natural acceptance。新 runtime 的 Fog marker 目前不存在；若復生即 fail closed 並停止驗收。TimesFM 仍排最後。

## Background monitors（不屬於 operational frontier）

- `CHIP-OVERLAY-SHADOW-01`、`EVENT-OVERLAY-SHADOW-01`：歷史效果應由 frozen walk-forward backtest 先行判斷；daily shadow 只保留作未來 promotion 前的額外 OOS 證據。
- Frozen backtest verdict：Chip 10%=`HISTORICAL_SUPPORT_UNCERTAIN`（114 日、mean delta `+0.002740`、95% CI `[-0.001251, +0.006371]`），目前不得 promotion；Event constrained 10%=`ROBUST_HISTORICAL_SUPPORT`（55 日、mean delta `+0.005819`、95% CI `[+0.002715, +0.008958]`），但重用 parent OOS，只能保留為 future promotion candidate。
- 2026-09-02 receipt：Chip=`22/60`、Event=`9/60`，均為 `ACCUMULATING`，且 `changes_production_ranking=false`。
- 不需等待兩者完成才能開始其他工作；未有 promotion admission 時，即使累積滿 60 筆也不會自動成為 Mainline frontier。

## Authority baseline

- `main` 與 `origin/main` 均已包含 activation repair、Fog resource budget、validation confinement 與 lock identity 修復，固定啟用 commit 為 `26c88343ccac08ce4701b785bfa2c2c82bfa446d`；production runtime 固定在相同 SHA。
- `docs/RESEARCH_SPINE_BACKLOG.md` 是 Research Spine 當前 canonical backlog；dated backlog、舊 task status 與 `.work` 只作 historical evidence。
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md` 是目前 automation/operations 的 P0 recovery authority；它不屬於 Research Spine，因此不得塞回 `docs/RESEARCH_SPINE_BACKLOG.md`。
- projection receipt 不等於 runtime load；缺 session evidence 的 runtime claim 一律維持 `UNKNOWN`。

## Operational boundary

- 本線可做 read-only 查核、狀態 reconciliation 與已 admission 卡的本機驗證。
- 不得以「沒有其他 executable card」作為 TimesFM admission、模型下載、runtime 安裝或外部存取授權。
- scheduler、provider、ranking、publish、production、deploy、push 與外部 write 仍須各自的明確 authority boundary。
- 本次 A4 production activation 授權已使用完畢；後續不得自行 `kickstart`、補跑、改 plist、clear 新 marker、切換 runtime SHA、登出／重開機或送外部 write。A5 僅做自然週期唯讀驗收。
