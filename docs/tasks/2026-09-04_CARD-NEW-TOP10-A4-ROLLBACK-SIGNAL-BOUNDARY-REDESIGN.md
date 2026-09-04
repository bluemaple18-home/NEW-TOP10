---
id: CARD-NEW-TOP10-A4-ROLLBACK-SIGNAL-BOUNDARY-REDESIGN-20260904
chain_id: NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903
parent: P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903
status: BLOCKED_REPAIR_CEILING
type: architecture-decision-proposal
priority: P0
owner: TOP10new operations
role: mainline
attempted_repair_generations: 2
thickness: strict
risk: critical
date: 2026-09-04
implementation_allowed: false
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: false
---

# A4 — Rollback Signal Boundary Redesign

👉 [假設與目標確認] 目標：把 activation failure handling 重整成可證明不被第二訊號中斷、且每個 terminal verdict 都有 durable receipt 的 bounded transaction；邊界：本卡只固定 repair／test／review 契約，不授權修改 code、commit、清 marker、切換 runtime checkout、reload launchd、deploy、push 或 external write；驗收：固定候選 SHA 必須通過兩個互不先讀 verdict 的獨立 Reviewer，才可另行申請 A4 production activation。

## 1. 問題與目前證據

Production automation 維持：

`NO-GO / BLOCKED_BY_ROLLBACK_SIGNAL_BOUNDARY`

目前 production runtime checkout 為 `<runtime-checkout>`，固定在 `60c7677d9e946e6ec702f851a986d0aad925f887`；已安裝 launchd plist 尚未切換，仍指向 development checkout。不得在本卡內搬家或啟用。

本卡建立時的 development HEAD：

`cd518e5ffb6192db6b94ade6acebed83987d09c2`

四個受影響檔案的未 commit diff identity：

`sha256:d0a290d9ca3e4922c9e63da7b9f894e5f61cfd4d9f9e454e6f56171a26beca6e`

這個 diff 只是不被接受的 repair input，不是 fixed candidate、review verdict 或 activation authority。工作區其他 dirty／untracked 檔案不屬於本卡。

已重現的阻塞 failure states：

1. 第一個 SIGTERM／SIGINT 使 transaction 進入 exception handling 後，第二個訊號仍可在 rollback protection 武裝前逸出，造成 `_rollback()` 未執行。
2. terminal receipt 已寫入或已完成最後一次 event-count 比較後，第二個訊號仍可能只加入記憶體 event；durable receipt 不含該事件。
3. receipt 重寫若依事件持續增加而無界重試，連續訊號可延後 lock release／disarm；write failure 也可能沒有可接受的 terminal evidence。
4. Storage Guard 取得 job lock 後，任何 denial marker read／receipt write 失敗都必須釋放 lock；目前工作區 diff 的方向可作 repair input，但尚未形成 accepted fixed-SHA evidence。

口頭或 thread 內的 reviewer 結論不得作為本卡完成證據。正式 verdict 必須依第 7 節落成 repo evidence，並綁定同一 fixed candidate SHA。

## 2. 目標與非目標

### 目標

- 定義四個不重疊的 transaction boundary：evidence capture、rollback critical section、terminal receipt seal、protection release。
- 對每個已知訊號窗口先建立 deterministic RED，再做 minimum sufficient repair。
- 保留既有 exact restore、denial evidence、identity verification 與 fail-closed semantics。
- 讓實作、測試與兩份獨立 review verdict 都可追溯至同一 fixed candidate SHA。

### 範圍外

- 不清除、改寫或搬移任何 live restart-denied marker。
- 不執行 launchctl bootstrap／bootout／kickstart，不 kill live PID。
- 不修改 installed plist，不切換 `<runtime-checkout>`，不做 A5 natural schedule acceptance。
- 不處理 Research Spine、ranking、模型、資料、權重、Discord publish 或 provider login。
- 不新增 daemon、database、authority ledger、通用 FSM、第二套 runtime 或外部 SaaS。
- 不以增加 retry 次數、吞掉所有 exception 或放寬 fail-closed 規則代替邊界修復。

## 3. 四段 transaction boundary

四段必須有清楚的 owner、入口、出口及例外語義；不得以多個旗標的鬆散組合模擬原子性。

### B1 — Evidence capture

用途：在任何清除或 rollback mutation 前，固定 denial marker、原始 reasons／paths、pre-state identity 與 hashes。

Requirements：

- WHEN transaction 取得對應 lock，系統 SHALL 在同一 ownership 下讀取 marker 與保存原始 evidence。
- IF marker read、parse 或 evidence persistence 失敗，THEN 系統 SHALL fail closed，且不得進入 marker clear 或 runtime mutation。
- Evidence capture 與後續 receipt write 必須使用不同 exception boundary；不得因 terminal receipt failure 改寫已觀察到的原始 evidence。

### B2 — Rollback critical section

用途：failure handler 一旦接手 armed transaction，exact restore 成為唯一高優先序控制流。

Requirements：

- WHEN armed transaction 的 failure handler 接手，系統 SHALL 在任何可重入 Python 操作、truth-test 或外部副作用前建立不可被第二 SIGTERM／SIGINT 中斷的 rollback boundary。
- WHILE rollback boundary active，後續 SIGTERM／SIGINT SHALL 不得 raise 到 restore control flow；系統只可記錄 bounded audit fact。
- Marker clear／restore 只能在既有 identity 匹配與 owner lifecycle 驗證通過後發生；未知 identity SHALL fail closed。
- exact restore 必須涵蓋 plist bytes、loaded topology、denial evidence、staging cleanup 與 verification；任何一步失敗 SHALL 產生 `ROLLBACK_VERIFICATION_FAILED`，不得宣稱成功。

### B3 — Terminal receipt seal

用途：為 transaction 產生一次、可稽核且與 terminal state 一致的 durable verdict。

Requirements：

- WHEN restore 與 verification 結束，系統 SHALL 進入明確的 receipt-sealing boundary。
- Terminal receipt SHALL 對同一 invocation 只完成一次 authoritative seal；不得靠無界 `while` 等待事件集合永遠不再變化。
- 在 seal boundary 內到達的重複 signal SHALL 以 bounded、可序列化的 aggregate evidence 表示；不得要求每個 OS signal 都觸發一次 receipt rewrite。
- 系統 SHALL 明確定義 seal 後 signal 的 ownership：交還原 handler、以 terminal state 處理，或由上層 supervisor 接手；不得再修改已封口 receipt 卻聲稱 receipt 完整包含 seal 後事件。
- IF receipt write 失敗，THEN transaction SHALL 保持 NO-GO，保留可重試／可診斷的最小本機 evidence，且不得進入 activation success。

### B4 — Protection release

用途：無論 B1–B3 成功或失敗，都釋放 lock、恢復 signal handler 並結束 staging ownership。

Requirements：

- Protection release SHALL 由最外層 `finally` 保證。
- Job lock、denial locks、signal handlers、staging resources 必須各自有 idempotent release semantics。
- Release failure 不得覆蓋較早的 rollback／receipt terminal failure；兩者都必須可稽核。
- B4 不得包含 marker clear、plist replacement、bootstrap 或其他 activation mutation。

## 4. 允許的實作範圍

本 chain 已用完兩次 Repair，依模型路由規則不得再派 Repair Worker。以下四檔只記錄潛在後續 architecture mission 的最小影響面，不構成 implementation authority：

- `scripts/activate_automation_runtime.py`
- `tests/test_automation_runtime_activation.py`
- `app/storage_safety.py`
- `tests/test_storage_safety.py`

若關閉 failure state 必須修改第五個檔案，Worker SHALL 回報 `CONTRACT_GAP / HOLD`，不得自行擴 scope。

工作區現有 diff可被拆解、重寫或放棄；不得把它視為必須保留的 implementation。其他 dirty／untracked 內容必須原樣保留，不得 stage。

## 5. RED-first reproduction contract

每個 RED 必須能在固定 parent SHA 或隔離基準副本失敗，且失敗原因直接對應外部行為，不得只 assert 私有旗標值。

### RED-1 — Failure-handler entry reentrancy

- Given：armed transaction 已完成至少一個可觀察 mutation，且第一個 signal／exception 已把控制流交給 failure handler。
- When：第二個 SIGTERM 與 SIGINT 分別落在 handler 接手到 rollback boundary 完成武裝之間的每個可重入 seam。
- Then：`_rollback()` 必須執行、exact pre-state 必須恢復，且第二訊號不得逸出 transaction boundary。

### RED-2 — Rollback step matrix

- Given：rollback 已開始。
- When：SIGTERM 與 SIGINT 分別落在 plist restore、bootout/bootstrap、marker restore、staging cleanup、verification 期間。
- Then：exact restore 不得被中斷；terminal status 只能是 verified rollback 或明確的 rollback verification failure。

### RED-3 — Receipt seal late-signal window

- Given：terminal payload 已序列化或已完成最後一次 event comparison。
- When：signal 在 atomic write、write return、seal completion 與 caller return 邊界到達。
- Then：durable receipt 與定義中的 signal ownership 必須一致，不得出現 memory 有 deferred event、receipt 無該 event卻宣稱完整的狀態。

### RED-4 — Signal storm boundedness

- Given：rollback／receipt seal 期間持續收到重複 signals。
- When：注入超過單次 receipt rewrite 可處理的數量。
- Then：transaction 必須在 bounded steps 內結束，不得無界重寫 receipt，且 lock／handler 最終釋放。

### RED-5 — Receipt write failure

- Given：exact restore 已完成。
- When：terminal receipt atomic write 丟出 OSError。
- Then：不得回報 activation success；所有 protection 必須釋放，並留下可診斷的 NO-GO evidence。

### RED-6 — Denial receipt failure releases job lock

- Given：Storage Guard 已取得 job lock 且 persistent denial marker 存在。
- When：marker read／receipt write 任一步驟失敗。
- Then：child 不得 spawn，job lock 必須可由獨立程序重新取得，原 marker 不得被清除或覆寫。

## 6. 驗收與驗證

### Functional acceptance

- AC-1：RED-1 至 RED-6 在 repair 前有可重現失敗證據，在 fixed candidate 全部 GREEN。
- AC-2：SIGTERM 與 SIGINT 都覆蓋 handler entry、rollback steps、receipt seal 與 release boundary。
- AC-3：exact restore 比對實際 bytes／hashes、loaded topology、marker hashes 與 process state，不以內部 flag 代替。
- AC-4：terminal receipt 與 terminal return status 一致；不存在無界 receipt rewrite。
- AC-5：所有 lock／handler／staging resources 在正常、rollback failure、receipt failure 三條路徑都釋放。
- AC-6：未修改 scope 外檔案，未執行 production mutation。

### Required verification

- Targeted RED/GREEN failure-injection tests。
- `tests/test_automation_runtime_activation.py` 全檔。
- `tests/test_storage_safety.py` 全檔。
- 受影響檔案 syntax check。
- `git diff --check`。
- candidate scope 與 worktree status audit。
- 固定 candidate commit SHA；review 不接受浮動 worktree diff。

## 7. Review evidence contract

Repair Worker 不做完成裁決。Mainline 固定 candidate SHA 後，派兩個 clean-context、互不先讀 verdict 的獨立 Reviewer；兩者審查同一 SHA 與同一 acceptance，不得修改候選。

必須新增並 commit 以下 evidence；實際檔名可保留 reviewer A/B，但不得合併成單一口頭摘要：

- `docs/evidence/CARD-NEW-TOP10-A4-ROLLBACK-SIGNAL-BOUNDARY-REDESIGN-20260904/reviewer-a.md`
- `docs/evidence/CARD-NEW-TOP10-A4-ROLLBACK-SIGNAL-BOUNDARY-REDESIGN-20260904/reviewer-b.md`
- `docs/evidence/CARD-NEW-TOP10-A4-ROLLBACK-SIGNAL-BOUNDARY-REDESIGN-20260904/mainline-verdict.md`

每份 reviewer evidence SHALL 包含：

- reviewer identity／model lane／review timestamp；
- fixed candidate SHA、parent SHA、changed files；
- 未讀另一 reviewer verdict 的聲明；
- 實際執行的 failure injection 與驗證命令；
- P0／P1／P2 findings，含檔案、行號、最小重現與影響；
- 明確 `GO` 或 `NO_GO`。

Mainline verdict 只有在兩位 Reviewer 都沒有 P0／P1，且分歧已用可重現證據裁決後才能是 `GO_FOR_OWNER_ACTIVATION_DECISION`。任何 P0／P1、無 fixed SHA、缺任一份 reviewer evidence 或 reviewer 先讀另一 verdict，都必須是 `NO_GO`。

Review GO 只代表 code candidate 可交 Owner 決定是否進 A4 activation；不授權清 marker、切 runtime checkout、修改 installed plist 或啟動自然排程。

## 8. Traceability

- Business requirement：避免未驗收 rollback 邏輯造成 production topology 半切換、marker evidence 遺失或 false recovery。
- Stakeholder requirement：Owner 必須能從 repo 內文件回答「哪個 SHA 被誰審、如何重現、為何 GO／NO-GO」。
- System requirements：B1–B4。
- Test evidence：RED-1 至 RED-6。
- Acceptance：AC-1 至 AC-6。
- Production authority：另行 Owner 決策，不由本卡或 review GO 推導。

## 9. Owner decision required

本卡目前只完成 architecture decision proposal。同一 `chain_id` 的 Repair ceiling 已耗盡；不得以改名、新卡或新 worker 重置代數。

若 Owner 要繼續，必須明示結束目前 repair chain，並授權建立一個新的 architecture mission；新 mission 必須把目前兩輪 NO-GO 當成輸入，不得宣稱既有 findings 已關閉：

`CLOSE NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903 REPAIR CHAIN; AUTHORIZE NEW ROLLBACK BOUNDARY ARCHITECTURE MISSION`

在此之前維持：

`NO-GO / BLOCKED_REPAIR_CEILING / IMPLEMENTATION NOT ADMITTED`
