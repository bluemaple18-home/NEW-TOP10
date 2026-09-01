# 工作名稱：BC-CP2 R12 Ranking Provenance Authority 薄裁決

任務簡介：依 R11 固定 blocker，唯讀判斷既有 first-party ranking provenance seam 是否足以支援未來 forward capture，或應維持 non-admission 等待自然累積；不得回填歷史 provenance、建立新 subsystem 或執行 capture。

來源與依賴：slice_id=`BC-CP2-R12-PROVENANCE-DECISION-01`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；fixed parent／R11=`498b76c9282974a38cc43ecc9302c2ac12dcfa28`；R11 evidence=`docs/evidence/BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY/01-feasibility-decision.md`；V2 contract=`docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`；current canonical backlog 仍優先。

執行規範：你是 GPT-5.5 high strict/core-bounded 唯讀證據 Worker；Sol Mainline 保留最終 authority 裁決。只盤點既有 `ranking_provenance_receipt`／`ranking_provenance_admission` seam、正式 producer 入口、必要 input binding、current tests 與 current configured ranking root；不得把程式存在、測試通過或 filename coverage 當 runtime capture 證據。

交付：只新增 `docs/evidence/BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION/01-forward-capture-or-defer.md`。Verdict 只能是 `GO_FOR_MINIMAL_FORWARD_CAPTURE_CARD`、`DEFER_UNTIL_NATURAL_AUTHORITY_ACCUMULATES` 或 `NO_GO_NEW_SUBSYSTEM_REQUIRED`。必須固定 historical corpus 永久 `NON_ADMISSION`、列出現有 seam 的 exact capability／missing runtime evidence、why_not_less／why_not_more／do_not_absorb，以及唯一最小下一卡或明確停止點。

硬邊界：不得修改 code、tests、config、workflow、ranking、manifest、receipt、registry、data、runner、queue、scheduler、backtest或 production；不得產生／回填 ranking provenance，不得建立 ledger／database／canonical writer／第二套 runtime；不得執行 capture、replay、benchmark、outcome、sealed access；不得准入 R13、Entry-Regime capacity、Phase 2、B1、C1或 production；不得 merge、push、改 Issue、deploy或 external write。

驗收：evidence 必須區分 static capability、test evidence 與 runtime session evidence；沒有 create→capture→verify 的 session evidence不得宣稱已可用。changed-files allowlist 僅指定 evidence；`git diff --check` 通過、worktree clean、獨立 fixed-SHA Review 無 P0/P1。若現有 seam 不足且補足需新 subsystem，必須 `NO_GO_NEW_SUBSYSTEM_REQUIRED`，不得提出擴建設計。

現在狀態：`ADMITTED / READ_ONLY_AUTHORITY_DECISION / HISTORICAL_NON_ADMISSION / NO_IMPLEMENTATION`
