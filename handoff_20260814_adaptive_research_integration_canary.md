# NEW-TOP10 Adaptive Research｜Integration Canary Handoff

## Root question

完成 Card A 的最後 operational proof：將已審核 Batch Owner 變更整合成 candidate，並在完全隔離 root 驗證：

```text
Batch Intent → Runner → Receipt → Observation → Eligibility
```

## Current state

- Canonical Batch Owner implementation：完成。
- Scheduler authority Repair：完成。
- Final Reviewer verdict：`GO`。
- Integration / isolated canary task：已建立、綁定、啟動，現在等待使用者授權。
- 尚未 merge、push、deploy、啟用 live daily或 Adaptive Queue。

## Formal tasks

- Integration task：`019fff9a-58c2-7361-9f9f-3e7db2a90e71`
- Reviewer task（必須復用）：`019fff37-cb09-7403-bf98-332c37eeb8c5`
- Repair task（必須復用）：`019fff51-1922-7530-8861-5f0b7c55cbbd`

## Cards

- `docs/tasks/2026-08-14_CARD-NEW-TOP10-CANONICAL-RESEARCH-BATCH-OWNER-CONTRACT-V1.md`
- `docs/tasks/2026-08-14_CARD-NEW-TOP10-CANONICAL-BATCH-OWNER-SCHEDULER-AUTHORITY-REPAIR-1.md`
- `docs/tasks/2026-08-14_CARD-NEW-TOP10-BATCH-OWNER-INTEGRATION-AND-ISOLATED-CANARY-V1.md`

## Fixed SHAs

- Batch Owner rejected candidate：`5df1fce0ef7426e804a9b0c6cc819b18cf51f3c3`
- Scheduler authority reviewed repair：`d7daea870ff3c2afc737358981b60507b254955d`
- Integration source/card：`8cf905df6613d99566c09d3bf1603a3a43737f88`
- Integration task worktree：`<codex-worktree>/deff/TOP10new`

## Current blocker

不是程式衝突。Integration task 已驗證 7 個目標 functional paths：

- `git status --porcelain`：空
- `git ls-files -m -o`：空
- `git diff --name-only`：空

但 sandbox escalation reviewer 要求使用者對下列動作明確批准：

> 以 reviewed repair `d7daea870ff3c2afc737358981b60507b254955d` 還原／整合 7 個 clean functional paths；排除 `docs/tasks/**`，保留目前 integration card。

## Exact user approval needed

回覆 integration task 或主線：

> 核准以 `d7daea870ff3c2afc737358981b60507b254955d` 整合已確認 clean 的 7 個 functional paths；不得碰其他路徑、production、live daily、push 或 deploy。

## Next step after approval

1. Integration task 套用 reviewed functional diff；若衝突即停。
2. 跑 11 targeted、17 receipt/cutover regression、compile、`bash -n`、`git diff --check`。
3. 在單一 tmp root 跑 isolated native evidence canary。
4. 驗證 canonical spine、正式 ledger、manager/history、production pre/post inventory不變。
5. 建立單一 integration candidate commit。
6. 交回既有 Reviewer task final integration review。

## Waiting conditions

- 目前唯一等待：使用者明確批准上述 7-path restore／integration。
- 若未批准：不得修改 integration worktree。
- 若 Reviewer final integration `NO-GO`：回既有 Repair task，不建立 replacement Repair task。

## Limits

- 不接 Card B Adaptive Shadow Queue。
- 不接 Card C live Runner Integration。
- 不部署、不改 launchd、不啟用 daily scheduler。
- 不改 production ranking、LightGBM model、signals、strategy config或promotion。
- 不覆蓋主 worktree 的使用者 dirty files。
- 不刪 immutable Research Spine／CAS／ledger source facts。

## Known pre-existing issue

`tests/test_native_evidence_activation.py` 在 clean worktree仍有 1 個既有 failure：缺少未追蹤 runtime artifact `artifacts/autonomous_research/next_action_queue.json`。Base、rejected candidate與repair都不存在該檔，本輪不得補造正式 artifact；分類為 `PRE-EXISTING`。

## Main worktree user-owned changes

必須保留：

- `scripts/build_weekend_universe_inventory.py`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`
- `docs/tasks/2026-08-03_TOP10-AICORE-STORAGE-OWNERSHIP-BOUNDARY-01.md`
- `.work/**` evidence
