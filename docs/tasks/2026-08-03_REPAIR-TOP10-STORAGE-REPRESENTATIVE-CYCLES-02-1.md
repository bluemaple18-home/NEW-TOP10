---
id: REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-1
chain_id: TOP10-STORAGE-RUNAWAY
status: ready_to_dispatch
type: repair
priority: P0
role: repair
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修復涉及 OS 寫入隔離、process-group 生命週期與 fail-closed 資源量測；錯誤可能寫回主 checkout 或留下逃逸程序。
reviewed_candidate: 4cd5458367284b8904c424ec9955275c7bfe9a34
review_thread: 019fc62f-1bcb-7492-ad0d-e7b1c073db2d
repair_generation: 1
allowlist:
  - app/storage_safety.py
  - scripts/storage_safety.py
  - tests/test_storage_safety.py
  - docs/operations/top10-storage-safety.md
  - docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/repair-1-verification.md
  - docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-1.md
forbidden_scope:
  - 任何 production data、artifacts、models 或 main checkout 未提交檔案
  - 重新執行八 job 代表性 workload、reclaim drill 或 stop-loss evidence drill
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - merge、push、deploy 或發布外部訊息
---

# REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-1｜P1 安全缺口修復

## Root question

能否只修正獨立 Review 的三個 P1，使 validation-only child 無法寫出 sandbox、任何必要 live RSS／swap 量測缺失都 fail closed，且 process-group leader 先退出時不會留下逃逸 descendant？

## 固定 findings

本輪只處理下列三項，不得把 P2 residual 擴成阻擋，也不得重跑代表性八 job：

### TOP10-REV-P1-001｜source／main checkout 寫入隔離不足

- Review evidence：`scripts/storage_safety.py:171` 的 `source_input_root` 只 `resolve()` 並寫 receipt；任意 child command 可用絕對路徑寫回 source 或其他 scope，而 guard 只監控 sandbox。
- 修復契約：validation-only child 必須具 OS／process 級寫入邊界，僅可寫本次 sandbox allowlist。若平台無法提供可信 confinement，validation 必須在 spawn 前 fail closed，不得降級為只靠事後檢查。
- `source_input_root` 必須存在、是目錄，且 lexical path 任一 component 為 symlink 都拒絕。
- source/main protected roots 在執行前後保留 bounded snapshot；發現 scope 外 mutation 必須 STOP、留下 persistent restart denial，且 receipt 不得為 OK。snapshot 是偵測層，不得取代 spawn 前的寫入隔離。
- 不得用字串掃描 shell command 冒充隔離。

Acceptance：

1. temp fixture child 嘗試寫 source root 或另一個 protected root 時，寫入本身被拒絕、原 hash 不變、結果非 OK。
2. 合法 child 可讀 source、只寫 sandbox output 並正常完成。
3. source root 不存在、非目錄、lexical symlink 或 output 指向 scope 外時一律 spawn 前拒絕。
4. confinement capability 不存在或 probe 失敗時 fail closed。

### TOP10-REV-P1-002｜中途 metric gap 被 final sample 掩蓋

- Review evidence：`app/storage_safety.py:461` 只檢查最後一筆 RSS／swap；`[valid, missing, valid-final]` 可得到 `triggered=false`，快速 child 的 final `rss=0` 也可掩蓋沒有有效 live sample。
- 修復契約：sample 必須可區分 `preflight`、`live`、`final`；任一必要 `live` sample 的 RSS 或 swap 缺失立即 STOP。成功 receipt 至少要有一筆 child 存活時取得的有效 live RSS，且 swap 契約也完整。
- final `process_pid=null`／RSS 0 只能描述收尾，不能補足 live evidence。

Acceptance：

1. 中途 live RSS 或 swap 為 null 時觸發原因碼、marker 與 restart denial，不得回 OK。
2. 快速 child 若未取得任何有效 live sample必須 fail closed。
3. preflight/final 的無 child RSS 不得誤判，但也不能滿足 live evidence。

### TOP10-REV-P1-003｜leader-first exit 留下 background descendant

- Review evidence：`app/storage_safety.py:621` 在 leader 已退出時直接 return；background descendant 可留在同一 group 繼續寫入。
- 修復契約：guard 必須保有已驗證的 process-group identity，直到 group quiescent。leader 退出但仍有 descendant 時不得回 OK；必須停止該 target group、留下 restart denial，並避免 PID／PGID reuse 誤殺其他程序。
- 正常結束與停損後都要證明 target group 無成員；不得只看 leader `poll()`。

Acceptance：

1. temp fixture `background child + leader exit 0` 結束後無殘留程序，receipt 非 OK 且有明確原因碼。
2. timeout／metric stop 只終止 target group，獨立 unrelated process 存活。
3. leader 已退出時 `terminate_process_group()` 仍能終止已驗證 group；identity 不符或無法驗證則 fail closed、不得盲目 kill reused PGID。

## 實作與驗證順序

1. 先查 CodeGraph；失敗才限域讀上述三個位置、caller、tests 與 CLI validation seam。
2. 先新增能捕捉三個 P1 的 RED tests，再做最小修復。
3. 所有動態測試只能在 test temp roots 與短命 child process 執行；不得讀寫 production output 或啟動任何 TOP10new job。
4. 跑 affected storage tests、必要的 pure unit／isolated subprocess tests、full pytest（若環境 gap，精確記錄）、`git diff --check`。
5. 建立單一 candidate commit，寫入 `repair-1-verification.md`：reviewed candidate、changed files、RED／GREEN、測試、candidate SHA、已知 residual。
6. 收卡狀態只能是 `READY_FOR_RE_REVIEW` 或精確 `BLOCKED`；不得自審為 GO。

## 禁止移動球門

- 不處理三個 P2 residual，除非某一行是完成上述 P1 最小修復不可分割的一部分；若發生須在 evidence 說明。
- 不修改 production `launch_verified=false`，不提出排程啟用。
- 不重寫既有代表性 cycle receipts 來掩蓋舊 candidate；repair 後仍由獨立 Reviewer 判定原 evidence 的可用範圍。
- 不碰 MDreport、其他專案、browser、provider 或主 checkout 的既有未提交檔案。

## 收卡格式

- `status: READY_FOR_RE_REVIEW | BLOCKED`
- `base_commit: 4cd5458367284b8904c424ec9955275c7bfe9a34`
- `candidate_commit: <40-char SHA>`
- `findings_addressed: TOP10-REV-P1-001, TOP10-REV-P1-002, TOP10-REV-P1-003`
- affected/full tests、`git diff --check`、changed-file allowlist、residual risks
- 明示 live launchd 仍 disabled，沒有 merge／push／deploy
