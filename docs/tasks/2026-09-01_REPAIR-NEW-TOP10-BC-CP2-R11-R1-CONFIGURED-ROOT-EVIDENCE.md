# 工作名稱：BC-CP2 R11 Repair-1 Configured Root Evidence 修正

任務簡介：修正 R11 candidate 把隔離 worktree 缺少 ignored artifacts 誤判為 canonical configured checkout 缺失的 P1；保持 provenance fail-closed 與 outcome-free 停損，不改研究結論以外的範圍。

來源與依賴：repair_id=`BC-CP2-R11-REPAIR-1`；R11 candidate=`61ca8314f4b065edaaed7712f26483ff3f68c056`；review finding=`P1-R11-CONFIGURED-ROOT-PROJECTION`；canonical configured checkout=`<repo-root>`；reviewed isolated worktree 僅作 Git candidate，不代表 ignored artifact authority。

執行規範：你是 GPT-5.5 high strict/core-bounded Repair Worker；只可修改 `docs/evidence/BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY/01-feasibility-decision.md`。唯讀核 canonical configured checkout 的 history／features／universe bytes、configured ranking root、ranking file count 與 receipt／provenance／manifest inventory；把 G1.4–G1.7 改成符合實況，將 worktree projection 與 configured authority 分開。

邊界：若 canonical configured bytes 與 V2 hashes 一致，G1.4–G1.6 必須 PASS；ranking root 存在時 G1.7 必須依存在與 corpus inventory 如實判定。只有 G1.8／G1.9 確認缺 per-ranking receipt／contemporaneous provenance 時才維持 `BLOCKED_RANKING_PROVENANCE_AUTHORITY`。Capacity/split 仍 `NOT_RUN`；不得讀 outcome、產 ranking、補 receipt、改 code/config/data/其他 docs/evidence、merge、push、改 Issue或 external write。

驗收：同一 evidence 內更新逐 gate facts、rationale、可重現相對路徑命令與 unique frontier；不得留下本機絕對路徑。changed-files allowlist 僅同一 evidence，`git diff --check` 通過、worktree clean；完成後回 fixed repair SHA，交原 Reviewer 只針對 P1 與 regression re-review。

現在狀態：`REPAIR_1_ADMITTED / P1_ONLY / OUTCOME_FORBIDDEN`
