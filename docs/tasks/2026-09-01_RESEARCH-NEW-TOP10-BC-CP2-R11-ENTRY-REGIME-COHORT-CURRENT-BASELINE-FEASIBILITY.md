# 工作名稱：BC-CP2 R11 Entry-Regime Cohort Current-Baseline Feasibility

任務簡介：依 V2 固定契約，先唯讀驗證 current authority 與 ranking provenance；前置條件全部通過後，才可做 outcome-free cohort capacity／split feasibility。缺任一 authority 即 fail closed，不得用 prior art 或重建結果補洞。

來源與依賴：slice_id=`BC-CP2-R11-ENTRY-REGIME-FEASIBILITY-01`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；fixed parent／V2=`e4c6690c6720406cb287ef19bcc000d7352a1f77`；contract=`docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`；R6–R10 與 `docs/RESEARCH_SPINE_BACKLOG.md` 依 V2 authority table 固定。

執行規範：你是 GPT-5.5 high strict/core-bounded 唯讀證據 Worker；Sol Mainline 只做裁決、監工與驗收。第一 gate 必須逐項驗 model、config、universe、top-N、per-ranking receipt、contemporaneous provenance 與 current configured bytes；任一缺失即回 `BLOCKED_RANKING_PROVENANCE_AUTHORITY` 並停止，不得進入 capacity/split 計算。若 authority refs 或 bytes 衝突，回 `BLOCKED_CURRENT_AUTHORITY_CONFLICT`。

允許後段：只有第一 gate 全通過，才可在隔離 temporary path 使用既有 first-party seam 做 outcome-free inventory，維持 h20、D+1、ranking-date as-of identity、future path diagnostic-only、單一 global chronological split、雙邊界 purge／至少 20 trade-day embargo、overlap component grain；結果只能是 `FEASIBLE_FOR_PREREGISTRATION` 或 `NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY`。不得新增或修改 verifier、fixture、contract或 authority。

交付：只新增 `docs/evidence/BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY/01-feasibility-decision.md`。必須記錄 fixed refs／hashes、逐 gate PASS／FAIL／NOT_RUN、完整可重現唯讀命令、是否 outcome-free、verdict、why_not_less／why_not_more／do_not_absorb、temporary cleanup 與唯一 frontier；不得把 coverage、filename、old manifest、fog root、historical rebuild 或 `REPLAY_GENERATED` 當 provenance。

邊界：不得修改既有 docs/evidence、code、tests、config、data、history、features、ranking、taxonomy、split、episode、horizon、workflow、runner、queue、scheduler、backtest或 production；不得產生 ranking、執行 replay／benchmark／訓練、讀取或衍生 return、PnL、win rate、Sharpe、alpha、target、promotion score或 sealed outcome；不得准入 preregistration、R12、Phase 2、B1、C1或 production；不得 merge、push、改 Issue、deploy或 external write。

驗收與停損：changed-files allowlist 僅指定 evidence；`git diff --check` 通過、worktree clean、獨立 fixed-SHA Review 無 P0/P1。第一 gate 失敗後仍執行 capacity/split、或任何 outcome access，均為 P0 並立即 NO-GO。完成後只用繁中回 fixed SHA、四選一 verdict、驗證、NOT_RUN gates 與唯一 frontier。

現在狀態：`ADMITTED / READ_ONLY_FEASIBILITY / OUTCOME_FORBIDDEN / NO_DOWNSTREAM_ADMISSION`
