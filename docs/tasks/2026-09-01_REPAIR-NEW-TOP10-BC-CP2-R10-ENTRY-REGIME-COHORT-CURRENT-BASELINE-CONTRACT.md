# 工作名稱：BC-CP2 R10 Entry-Regime Cohort Current-Baseline 契約修補

任務簡介：依 R9 固定裁決，將仍相容的 Entry-Regime Cohort invariants 重寫成 current-baseline feasibility 任務契約草案；只修契約，不執行 feasibility、replay 或 outcome 計算，也不准入後續實作。

來源與依賴：slice_id=`BC-CP2-R10-ENTRY-REGIME-CONTRACT-01`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；fixed parent／R9=`ba2c5310ae4a8e89ec81e8ec347433123dbcbb49`；R6=`b7ba1fc6065d6221353f7362db92ac7638bb8017`；R7=`e1a30830d0ab2ee24af0f81d703cbf350be4819e`；R8=`27327b670142e22c4c4cdd5bda7cae03ac2eb1e4`；canonical backlog=`docs/RESEARCH_SPINE_BACKLOG.md`；prior art 僅供取材，不具現行准入 authority。

執行規範：你是 GPT-5.5 high strict/core-bounded 契約 Worker；Sol 只做 Mainline 裁決、監工與驗收。只新增 `docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`，狀態固定為 `CONTRACT_DRAFT / NOT_ADMITTED`。契約必須保留 h20、D+1、ranking-date as-of identity、future path diagnostic-only、outcome-free、global chronological split、雙邊界 purge／embargo、overlap component grain 與 research-only 邊界。

必要 fail-closed 契約：明確 supersede 舊 feasibility JSON 的 runtime hashes、non-authoritative split 與 blocked capacity output；固定 current configured history／features 與 R6–R9 authority refs；ranking corpus 若缺 model、config、universe、top-N、per-ranking receipt 或 contemporaneous provenance，只能回 `BLOCKED_RANKING_PROVENANCE_AUTHORITY`，不得以舊 manifest、fog root、historical rebuild 或 `REPLAY_GENERATED` 補洞。驗收結果只允許 `CONTRACT_DRAFT_READY_FOR_OWNER_ADMISSION` 或 `BLOCKED_CURRENT_AUTHORITY_CONFLICT`。

邊界：不得修改既有 task／architecture／evidence、code、tests、config、data、history、features、ranking、taxonomy、split、episode、horizon、workflow、runner、queue、scheduler、backtest或 production；不得執行 feasibility、replay、benchmark、訓練、outcome、sealed access；不得准入 R11、B0 Phase 2、B1、C0 Phase 2、C1、preregistration、promotion或 production；不得 merge、push、改 Issue、deploy或 external write。

驗收與停損：新 V2 卡必須只含 objective、authority、scope、constraints、acceptance、verification、status、handoff 與 evidence refs，不偷渡實作；使用相對路徑、繁中、完整 SHA／hash；changed-files allowlist 僅新 V2 卡，`git diff --check` 通過且 worktree clean。若 current authority 無法一致固定，立即 `BLOCKED_CURRENT_AUTHORITY_CONFLICT`，不得自行改研究語義。完成後只回 fixed SHA、結果、驗證與唯一 frontier。

現在狀態：`ADMITTED / CONTRACT_REPAIR_ONLY / FEASIBILITY_NOT_ADMITTED`
