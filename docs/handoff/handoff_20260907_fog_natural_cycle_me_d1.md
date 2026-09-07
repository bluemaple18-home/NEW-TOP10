# NEW-TOP10 Fog／ME-D1 主線換手

## Successor status（2026-09-07）

- Owner 已將 Fog natural-cycle observation 留在原對話；本 task 不再擁有或操作 Fog。
- Owner 後續明確指示其他工作「開工」，ME-D1 第一個 bounded Daily Close slice 因而完成 admission、implementation、第一代 Repair 與原 Reviewer 複驗；狀態為 `MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / NON_PRODUCTION`。
- 本 handoff 其餘 `NOT_ADMITTED`／pending 文字保留為換手當時的歷史快照；現況以 `docs/RESEARCH_SPINE_BACKLOG.md` 與 `docs/evidence/ME-D1-DAILY-CLOSE-SNAPSHOT-IMPLEMENTATION-20260907.md` 為準。

## Goal

1. 唯讀等待 Fog runtime activation 後的兩次連續自然週期，取得完整 acceptance evidence。
2. 保持 Research Spine authority 誠實；ME-D1 目前只完成 seam audit，是否准入 bounded implementation 仍由 Owner 明確裁決。

## Root question

- Operational：固定 runtime `26c88343ccac08ce4701b785bfa2c2c82bfa446d` 能否完成兩次連續自然 Fog 週期，而無 denial marker、stale lock 或未收斂 child process group？
- Research candidate：Owner 是否要依 `docs/evidence/ME-D1-DAILY-CLOSE-SEAM-AUDIT-20260907.md` 明確 admission ME-D1 第一個 bounded Daily Close slice？

## Constraints & preferences

- 使用節省模式、繁體中文；不重貼整段歷史。
- Fog observation 不得稱為 Card A5。Canonical Research Spine Card A5=`MATCHED-LEARNING-PROJECTION`，已 closed。
- 不得 manual run、`kickstart`、清 marker、改 plist、改 runtime SHA 或做其他 production mutation來替代自然週期。
- `繼續` 不授權 merge、push、deploy、production 或外部 write。
- ME-D1 仍 `NOT_ADMITTED / NO_RUNTIME_AUTHORITY`；不得先建立 implementation card 或改 code。
- `EXTEND_EXISTING > ADD_SUBSYSTEM`；不得擴成完整 Market Evidence Plane、intraday、多 provider resolver 或第二套 registry／ledger／scheduler。

## Completed actions

- Fog resource-budget、validation confinement 與 lock identity 修復已完成雙盲 review、兩輪固定 SHA 代表性 validation、啟用與 push。
- Production detached runtime 已固定在 `26c88343ccac08ce4701b785bfa2c2c82bfa446d`。
- 啟用 receipt：`docs/evidence/A4-RUNTIME-ACTIVATION-26c8834-20260907/activation.json`；CLI exit `0`，status=`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。
- R4 兩輪 validation：`docs/evidence/REPAIR-NEW-TOP10-FOG-RESOURCE-BUDGET-01-LIVE-REVALIDATION-R4-20260907/summary.json`，兩輪皆 `OK`、child exit `0`、最終 process group quiescent。
- `f787437e2c88a327ad7be210f31d790fa96ee3f7` 已 push，內容為 Fog activation candidate evidence。
- `9a875ae378a2e57b6694b787a57bd7ac2c98ed09` 已建立但未 push：修正 Fog／Card A5 名詞、reconcile backlog baseline、加入 ME-D1 seam audit。
- Heartbeat automation `top10-fog` 已更新為正確名詞，維持每 10 分鐘唯讀監控；不要建立重複 monitor。

## Active state

- Worktree：`<repo-root>`，branch=`main`，working tree 在建立本 handoff 前乾淨，`main` 比 `origin/main` ahead 1（`9a875ae`）。
- Active runtime（local-only，不可跨機照抄）：`/Users/mattkuo/TOP10-runtime-automation-26c8834`，detached at `26c8834`。
- Historical runtime（local-only，先保留）：`/Users/mattkuo/TOP10-runtime-automation`，detached at `ab7c418`。
- 2026-09-07 14:51 CST：Fog launchd `state=not running`、`runs=0`、`last exit code=(never exited)`；新 runtime denial marker absent，未見 Fog／queue lock。
- 新 runtime 的 `fog-research-worker_latest.json` mtime=13:56 CST，早於 activation，內容是搬移過來的舊 `RESTART_DENIED` receipt；不得把它當新 invocation。

## In progress / remaining work

### Fog natural-cycle acceptance

每個成功週期必須同時證明：

- `launchctl runs` 相對 baseline 0 增加；
- `trigger_type=natural`；
- `child_spawned=true`；
- `child_exit_code=0`；
- `final_process_group_quiescent=true`；
- `artifact_run_date` 正確；
- 新 runtime 無 restart-denied marker；
- 無 stale Fog／queue lock。

取得第 1 次只記錄 `1/2`；取得連續第 2 次才可標 `ACCEPTED`。完成後更新 task／frontier／evidence；commit 可本機執行，push 仍須以新對話可驗證的 Owner authority 為準。接受完成前不得刪 historical runtime。

### ME-D1 admission fork

- Audit verdict：`MEASURED_GAP_CONFIRMED / READY_FOR_OWNER_ADMISSION_DECISION / NOT_ADMITTED`。
- 若 Owner 明確 admission，先 materialize bounded implementation card，再依既有 FetchStage、validation snapshot、DatasetBundle seams做最小 slice。
- 若 Owner未 admission，維持 registered candidate，不施工；RADAR-01 仍在 ME-D1 下游。

## Blocked & errors

- Fog 沒有技術 blocker；目前只是尚未到自然 interval，狀態不可行動。
- ME-D1 implementation 唯一 blocker 是缺 Owner explicit admission。
- 現行 clean parquet validator 為 `ok=true / ERROR=0 / WARN=4`；TPEX latest `ma20`／`bb_middle` coverage 只有 0.1%。這是 downstream feature completeness 風險，不是 Daily Close base-field 缺漏，也不能在 ME-D1 audit 裡順手修。

## Key decisions & resolved questions

- 現行 Fog observation 不是 Research Spine Card A5；所有新通知已改名。
- Research Spine 仍 `NO ACTIVE EXECUTION FRONTIER`。
- ME-D1 現有 seam 足以延伸，不需要新 subsystem；measured gap 是 enrichment 前缺 immutable provider-neutral Daily Close snapshot、finalization、price basis、fetch lineage、calendar/gap evidence。
- `features.parquet` 的 hash 只能證明 downstream enriched artifact，不能替代 Daily Close source truth。

## Candidate forks

- `pending`：Owner 是否授權 push 本機 `9a875ae` 與本 handoff commit。
- `pending`：Owner 是否明確 admission ME-D1 bounded implementation。
- `pending`：Fog 兩次自然週期接受後，是否清理 historical runtime／驗證 worktree。

## Evidence references

- `docs/RESEARCH_SPINE_BACKLOG.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`
- `docs/evidence/ME-D1-DAILY-CLOSE-SEAM-AUDIT-20260907.md`
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`
- `docs/tasks/2026-09-07_REPAIR-NEW-TOP10-FOG-RESOURCE-BUDGET-01.md`
- `docs/tasks/2026-09-07_REPAIR-TOP10-FOG-VALIDATION-LOCK-IDENTITY-01.md`
