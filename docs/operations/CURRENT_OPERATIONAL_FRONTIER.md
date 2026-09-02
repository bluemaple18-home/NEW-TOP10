# NEW-TOP10 Current Operational Frontier

更新：2026-09-02

👉 [假設與目標確認] 目標：只以目前主線與可重跑證據界定唯一前線；邊界：不重啟歷史卡、不碰 TimesFM、push、deploy、production 或外部 write；驗收：已整合鏈、等待條件與未 admission 候選可被明確區分。

## Current state

- Research Spine A0–A6：`COMPLETE / MAINLINE_ACCEPTED / INTEGRATED`。A5 已合併於 `bb617e9`；A6 已合併於 `2b9eccd`。A5/A6 task card 原本的 `MAINLINE_ACCEPTANCE_PENDING` 是落後狀態，現已校正。
- Research Spine B0/C0/BC：B0-P1、C0-P1、BC-CP2 current-tip baseline 與 C0-P2 已接受；BC-CP1 已決定並結案；B0-P2=`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`；B1–D1 未 admission；R14=`NO_GO_R14_INSUFFICIENT_DECISION_VALUE`。目前沒有可執行的 Research Spine implementation frontier。
- Forecast：FM0、FC1、FC2 vendor-neutral baseline 已分別合併於 `ff3d30b`、`9abc159`、`02730a7`。TimesFM 3 僅完成 restricted-shadow preflight，狀態固定為 `DEFERRED / LAST / HOLD`；未下載模型、未安裝 runtime、未執行 inference，且不是目前前線。
- TPEx TSKG：`INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO`。實作、review、repair 與狀態 reconciliation 均已存在；舊 dossier 的 `IMPLEMENTED_PENDING_REVIEW` 已校正，不得重派。
- Daily recovery：記憶體壓力 fail-closed 修復與 2026-09-01 recovery receipt 已在主線。另一路「報牌沒動」調查由獨立 Codex task 處理，本線不重複介入。

## Operational frontier

目前本線沒有已 admission、可立即實作的非 TimesFM 卡。剩餘項目分成三類：

1. `CHIP-OVERLAY-SHADOW-01`、`EVENT-OVERLAY-SHADOW-01`：`WAITING_FOR_NEW_OOS_DATES`，只能等新的樣本日期，不可用舊資料偽造進度。
2. `RESEARCH-FUNDAMENTAL-READINESS-01`：`COMPLETED_BLOCKED_DATA`；`VOLUME-CLIMAX-WARNING-SHADOW-01`：`COMPLETED_MONITORING`。兩者都不是待實作卡。
3. 2026-06／2026-07 文件中的 `READY_FOR_RESEARCH`、`READY_FOR_SHADOW_RERANK_GUARD`、`READY_FOR_FIRST_WAVE_RESEARCH` 是歷史狀態；後續結果已存在，未經新的 measured-gap admission 不得當成目前前線。

因此下一個狀態變化只能來自：獨立 incident task 的可驗收結論、新 OOS 日期、或 Owner 明示 admission 新 measured-gap 卡。TimesFM 仍排最後，不因其他 lane 暫無 executable card 而自動提前。

## Authority baseline

- Local `main` 包含 A0–A6、Forecast FM0–FC2、R13/R14、B0/C0/BC 決策與本次狀態校正。
- 本機 `origin/main` tracking ref 目前停在 `5d7c529`；未執行 fetch、push、merge、deploy 或 production mutation，因此不對遠端即時狀態作額外宣稱。
- `docs/RESEARCH_SPINE_BACKLOG.md` 是 Research Spine 當前 canonical backlog；dated backlog、舊 task status 與 `.work` 只作 historical evidence。
- projection receipt 不等於 runtime load；缺 session evidence 的 runtime claim 一律維持 `UNKNOWN`。

## Operational boundary

- 本線可做 read-only 查核、狀態 reconciliation 與已 admission 卡的本機驗證。
- 不得以「沒有其他 executable card」作為 TimesFM admission、模型下載、runtime 安裝或外部存取授權。
- scheduler、provider、ranking、publish、production、deploy、push 與外部 write 仍須各自的明確 authority boundary。
