# 工作名稱：BC-CP2 R9 Entry-Regime Cohort 可行性對帳

任務簡介：以 current canonical baseline 唯讀核對 2026-08-16 Entry-Regime Cohort 舊卡與 R7／R8、canonical backlog、ranking provenance 是否相容，只裁決是否可另行准入新版 feasibility audit；不得直接實作或 replay。

來源與依賴：slice_id=`BC-CP2-R9-ENTRY-REGIME-RECONCILIATION-01`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；R6=`b7ba1fc6065d6221353f7362db92ac7638bb8017`；R7=`e1a30830d0ab2ee24af0f81d703cbf350be4819e`；R8=`27327b670142e22c4c4cdd5bda7cae03ac2eb1e4`；舊 architecture／feasibility cards=`docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1.md`、`docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1.md`；canonical backlog=`docs/RESEARCH_SPINE_BACKLOG.md`。

執行規範：你是 GPT-5.5 high strict/core-bounded 唯讀證據 Worker；Sol 只做 Mainline 裁決、監工與驗收。逐項對帳 current authority precedence、entry-time attribution、future-path diagnostics、h20／D+1、split／embargo、ranking provenance 與 R7 的 `28 / 16 / 2 / 0` census；不得把舊卡的 `ready`、架構選擇或 feasibility 設計視為現行准入。

交付：只新增 `docs/evidence/BC-CP2-R9-ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION/01-current-baseline-reconciliation.md`。Verdict 只能是 `GO_FOR_NEW_CURRENT_BASELINE_FEASIBILITY_CARD`、`PARTIAL_CONTRACT_REPAIR_REQUIRED` 或 `NO_GO_SUCCESSOR_AUTHORITY_CONFLICT`；必須列出 compatible／superseded／unproven claims、固定 authority refs、ranking provenance 邊界、why_not_less／why_not_more／do_not_absorb，以及唯一最小下一卡。

邊界：只讀 repo 內既有 code、config、data metadata、task cards 與 evidence；只可新增上述單一 evidence。不得修改 code、tests、config、data、history、features、ranking、taxonomy、split、episode、horizon、workflow、runner、queue、scheduler、backtest、production或既有 evidence；不得執行 replay、benchmark、訓練或 outcome 計算；不得准入 B0 Phase 2、B1、C0 Phase 2、C1 或 successor implementation；不得 merge、push、改 Issue、deploy或 external write。

驗收與停損：證據須 outcome-free，引用完整 SHA／路徑並區分 current authority、prior art 與 inference；`git diff --check` 通過、changed-files allowlist 僅一份新 evidence、worktree clean。若 canonical backlog、R7/R8 或 ranking provenance 存在 material conflict，立即 fail closed，不得自行修契約或改研究語義。完成後只用繁中回報 fixed SHA、verdict、驗證與唯一 frontier。

現在狀態：`ADMITTED / READ_ONLY_RECONCILIATION / SUCCESSOR_IMPLEMENTATION_NOT_ADMITTED`
