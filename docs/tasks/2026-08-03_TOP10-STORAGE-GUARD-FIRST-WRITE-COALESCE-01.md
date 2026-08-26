---
id: TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01
chain_id: TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE
parent_chain_id: TOP10-STORAGE-RUNAWAY
predecessor_candidate: 65b00fc7870aff5f8337c2cf235465c9166568ad
predecessor_status: REVIEW_NO_GO / FORK_REQUIRED_FIRST_WRITE_COALESCE
blocking_review_thread: 019fc7d8-5c75-74d3-91b5-aedad829fef4
blocking_finding: FIRST-WRITE-SCHEDULED-DOUBLE-SAMPLE-P1-003
status: ready_for_review
type: implementation
priority: P0
defect_severity: P1
owner: Codex visible isolated worktree
role: implementation
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: P1 位於控制八條工作入口的P0共用容量守門，涉及threading event、scheduled/first-write observation ownership、cadence與persistent denial；使用Sol high。缺陷與race重現已清楚，無需xhigh。
frontier: true
source_parent: 65b00fc7870aff5f8337c2cf235465c9166568ad
traces_to:
  - TOP10-STORAGE-RUNAWAY-01#AC-3
  - TOP10-STORAGE-RUNAWAY-01#AC-4
  - TOP10-STORAGE-RUNAWAY-01#AC-5
  - TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01
  - FIRST-WRITE-SCHEDULED-DOUBLE-SAMPLE-P1-003
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01.md
  - docs/evidence/TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01/**
forbidden_scope:
  - 修改storage policy ceiling、19/20 target、fog business logic、runner、其他七個job或launch定義
  - 執行FOG、代表性workload、cycle、retry、reclaim drill或stop-loss drill
  - 讀寫、清除、修改、複製或復用任何fresh／前代sandbox、receipt、log、marker、contract或restart denial
  - production data、artifacts、models、主checkout既有dirty檔、其他專案或使用者文件
  - 瀏覽器、cookie、外部provider、connector或控制面
  - launchd load、enable、kickstart、restart、reload或任何live排程
  - merge、push、deploy、發布報牌或傳送外部訊息
evidence_path: docs/evidence/TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01/
---

# TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01｜First-write observation合併

## Root question

當first-write event在process waiter阻塞期間先發生、而absolute target也同時到期時，如何讓scheduled
observation原子承接並消耗該pending event，使同一時間窗只取樣一次，且不破壞runtime-preemption與
first-write live evidence？

## 為何另開root

- Candidate `65b00fc7870aff5f8337c2cf235465c9166568ad` 已修正runtime deadline被sample跨過的
  precedence缺陷，但獨立Reviewer判定`REVIEW_NO_GO`，finding
  `FIRST-WRITE-SCHEDULED-DOUBLE-SAMPLE-P1-003`。
- Reviewer repro：hard `10s`、target `9.5s`；child在首次waiter期間輸出`65536` bytes；sampler
  durations `[0.1,0.1,10.1]`。immediate completion `0.1s`，wait `9.4s`；到target後scheduled
  completion `9.6s`，但`sampled_first_write`仍為false，下一輪立即再執行first-write sample並於
  `19.7s`錯誤得到`LIVE_SAMPLE_CADENCE_EXCEEDED`與persistent denial。
- Expected：scheduled observation開始前已pending的first-write必須由該次observation同時滿足並消耗；
  completions只留`[0.1,9.6]`，下一wait `9.4s > 0`，child可`0 / OK`，不得建立denial。
- 不得在已完成implementation／review task直接修碼，也不得進FOG。

## 固定契約

1. 每個live observation必須有唯一owner；同一時間窗的scheduled target與pending first-write只能呼叫
   sampler一次，禁止scheduled完成後因stale event立即再取樣。
2. Scheduled observation開始前已set且尚未消耗的first-write event，必須在同一狀態轉移中標為
   consumed；該observation完成後只重算一次`SAMPLE / WAIT_RUNTIME / SCHEDULE_OVERRUN` action。
3. First-write若在scheduled observation完成後才發生，不得被先前observation錯誤冒領；它可維持pending，
   但下一次live observation仍須經absolute target／runtime action取得嚴格正wait，禁止back-to-back
   no-wait sample。
4. 若first-write在scheduled sampler執行期間發生，實作必須有明確、deterministic ownership boundary；
   可在sample開始前鎖定generation/window，或安全延後至下一positive-wait observation，不得以競態式
   `is_set()`事後猜測造成重複或漏取樣。
5. `WAIT_RUNTIME`期間first-write不得繞過preemption；runtime deadline到達前禁止啟動已知會跨期sample，
   最終仍為`HARD_RUNTIME_EXCEEDED`。
6. Actual completion gap `> hard maximum`仍為`LIVE_SAMPLE_CADENCE_EXCEEDED`；未發生actual overrun的
   double-sample race不得製造cadence reason或persistent denial。
7. Hard maximum、`19/20` target、O(1) stale-target reconcile、policy/schema與receipt基本語義不變；
   禁止epsilon、tolerance、ceiling提高、magic seconds或第二套流程引擎。
8. Fail-closed仍須verified PGID quiescent、persistent denial、`automatic_clear_allowed=false`與第二次`75`；
   健康coalesced案例必須`0 / OK`且無denial。

## Checkpoint 0｜身分與context

- 正式task先以bootstrap-only驗證project、獨立clean worktree、HEAD exact、HEAD第一親代精確為
  `65b00fc7870aff5f8337c2cf235465c9166568ad`、card實體與index lock；activation前禁止動作。
- Source decision前查CodeGraph；未初始化／無結果才保存`CONTEXT_DEGRADED`，限域讀
  `run_guarded_job()` first-write/cadence/runtime loop與`tests/test_storage_safety.py`。
- 主checkout三個既有dirty檔雜湊必須維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

## Checkpoint 1｜Deterministic RED

先新增Reviewer最小重現並在parent candidate證明RED：

- hard `10s`、target `9.5s`、child在首個waiter內first-write、durations `[0.1,0.1,10.1]`。
- RED必須記錄event set/consume window、completions `[0.1,9.6,19.7]`、waits `[9.4]`、sample
  count、exit/reason、denial與PGID；不可用人工終止第三筆sample冒充症狀。
- GREEN必須是completions `[0.1,9.6]`、所有wait嚴格正值且下一wait約`9.4s`、sample count `2`、
  child正常`0 / OK`、無denial。

## Checkpoint 2｜最小GREEN

- Scheduled branch在呼叫sampler前，原子snapshot「此observation是否同時owner pending first-write」；完成後
  一次更新`sampled_first_write`／generation與scheduled action，禁止下一輪重新解讀舊event。
- 不得只在sample完成後無條件`if first_write.is_set(): sampled=True`，避免冒領完成後才發生的event。
- Event若落在sample執行期間，必須由測試鎖定選定語義：由本次observation承接，或保留pending但下一次
  必須先正等待；兩者皆不可立即no-wait sample。
- 改動保持薄、集中於observation ownership，不重寫整個guard loop。

## Checkpoint 3｜回歸矩陣

至少驗證：

1. First-write在waiter中、scheduled sample開始前、sampler執行期間、sampler完成後四種窗口。
2. Scheduled target與first-write同時成立時sample count只增加一次、action只重算一次。
3. `WAIT_RUNTIME`期間first-write不啟動sample；runtime `19.2s` exact case仍
   `HARD_RUNTIME_EXCEEDED`、PGID／denial／第二次`75`。
4. 前代stale-target schedule-overrun、first-write跨target正wait、healthy60s、true60.005 cadence
   overrun、absolute schedule、sampler overrun、late/on-time normal return、child during sample與
   process-group regressions全數通過。
5. `tests/test_storage_safety.py tests/test_fog_storage_validation.py` affected suite；再跑full suite或記錄
   精確既有research-ledger `evidence_exists` gap，不得宣稱全綠。

## Acceptance

### AC-1｜同窗只取樣一次

Given first-write在waiter期間已pending且scheduled target到期
When scheduled observation執行
Then該observation同時消耗event，下一輪不會零等待再取樣。

### AC-2｜Event ownership不冒領

Given first-write發生在observation前、期間或完成後
When guard判定owner
Then每個event只被一筆足以涵蓋它的observation消耗；其餘pending路徑仍有正wait。

### AC-3｜Runtime與cadence不退化

Given runtime preemption、actual cadence overrun與健康job
Whenregressions執行
Thenruntime/cadence reason、PGID／denial與健康OK語義全部維持。

### AC-4｜Scope與上線邊界

Given本卡只修shared guard source
When收卡
Thenchanged files嚴格符合allowlist、八份policy仍`launch_verified=false`、所有live labels維持
disabled／not-loaded，且沒有FOG／workload／cycle／retry、merge、push、deploy或live啟用。

## Deliverables

- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- 本卡
- `docs/evidence/TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01/verification.md`
- 單一candidate commit；第一親代必須是本卡overlay，worktree clean。

## 收卡

Implementation只可回`READY_FOR_REVIEW / CANDIDATE`或reason-coded`BLOCKED`，不得自審、不得直接進
FOG。主線須另開全新獨立Reviewer；只有`REVIEW_GO`才可建立fresh FOG root卡。

## Implementation history

- Activation preflight：formal thread `019fc7e4-51b7-71f3-b3b1-95396dcc05a5`、projectId、獨立 detached
  worktree、`HEAD=cb9a6aedc348c494d984fa168d9c3fb7e089da80`、
  `HEAD^=65b00fc7870aff5f8337c2cf235465c9166568ad`、初始 clean、card 實體與 index lock 均符合。
- CodeGraph：此 worktree 未初始化，保存 `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`；未建立 index，
  fallback 限於 `run_guarded_job()` first-write／scheduled／runtime loop 與
  `tests/test_storage_safety.py`。
- 可證偽假說：
  1. 若根因是 waiter 內已 set 的 first-write event 在同輪 scheduled branch 開始前未被 claim，則
     scheduled sample 完成後下一輪會把舊 event 當成新 observation，形成 back-to-back sample；在
     scheduled sampler 前原子 claim 後，Reviewer exact case 應由三筆 completion 收斂為兩筆。
  2. 若 ownership boundary 固定在 observation start，則 start 前 pending event 可由該 scheduled
     observation consume；start 後才發生的 event 不會被事後 `is_set()` 冒領，且必須延後到下一個
     positive-wait scheduled observation。
  3. 若 first-write claim 仍服從既有 `WAIT_RUNTIME` 與 `next_sample_action()`，則 runtime `19.2s`
     exact case、actual cadence overrun 與 O(1) target reconcile 不會退化。
- Deterministic RED：未改 source 時，Reviewer exact test 自然完成三筆 sampler
  `[0.1, 9.6, 19.7]`，waits `[9.4]`，得到
  `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED` 與 persistent denial；第三筆 `10.1s` sampler 自然
  返回，未由測試人工終止。
- 最小 GREEN：scheduled observation 在 sampler 前以 lock-protected claim 承接 start 前 pending 的
  first-write event；同一 exact test 得到 completions `[0.1, 9.6]`、waits `[9.4, 9.4]`、sample count
  `2`、`0 / OK`、無 denial，target PGID quiescent。
- Ownership boundary 固定為 observation start；四窗口 matrix 中，waiter／scheduled start 前 event
  由當次 scheduled sample consume，sampler 期間／完成後 event 保持 pending，先正等待 `9.4s` 再由
  下一 scheduled observation consume，無 back-to-back sample。
- Runtime／回歸：first-write pending 不可繞過 `WAIT_RUNTIME`；`19.2s` exact case仍為
  `70 / HARD_RUNTIME_EXCEEDED`、persistent denial、PGID quiescent、第二次 `75`。Focused
  `21 passed, 36 deselected, 15 subtests passed`；affected `65 passed, 31 subtests passed`。
- Full suite：`698 passed, 1 failed, 285 subtests passed`；唯一 failure 仍是既有 research-ledger
  `evidence_exists` gap，本卡未修改或放寬該契約，未宣稱 full green。
- Scope：八份 policy `launch_verified=false`、protected hashes 維持、`git diff --check` 通過；
  `candidate_commit: reported_in_final_receipt`。未執行任何禁止邊界。
- 收卡：`READY_FOR_REVIEW / CANDIDATE`；implementation 不自審、不進 FOG。

## 五行派工卡

- 任務ID：`TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01`
- 卡片類型｜派工對象：`strict implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、前代runtime implementation卡與verification、Reviewer finding，以及全域
  `rules/24-storage-capacity-safety.md`
- 任務目的：合併scheduled與pending first-write observation，消除stale-event double sample；不跑FOG。
- 證據路徑：`docs/evidence/TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01/`
