---
id: TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01
chain_id: TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE
parent_chain_id: TOP10-STORAGE-RUNAWAY
predecessor_candidate: d4597c3950e4635f32c03519ff8715c580176160
predecessor_status: REVIEW_NO_GO / FORK_REQUIRED_RUNTIME_PRECEDENCE
blocking_review_thread: 019fc7b5-9e2e-7541-98a6-eee58bdb9089
blocking_finding: CADENCE-RUNTIME-PRECEDENCE-P1-002
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
model_reason: P1 位於控制八條工作入口的 P0 共用容量守門，牽涉 runtime deadline、sample cadence、reason precedence、PGID 終止與 persistent denial；使用 Sol high。缺陷與 deterministic 驗收已清楚，無需 xhigh。
frontier: true
source_parent: d4597c3950e4635f32c03519ff8715c580176160
traces_to:
  - TOP10-STORAGE-RUNAWAY-01#AC-3
  - TOP10-STORAGE-RUNAWAY-01#AC-4
  - TOP10-STORAGE-RUNAWAY-01#AC-5
  - TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01
  - CADENCE-RUNTIME-PRECEDENCE-P1-002
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01.md
  - docs/evidence/TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01/**
forbidden_scope:
  - 修改 storage policy ceiling、19/20 target、fog business logic、runner、其他七個 job 或 launch 定義
  - 執行 FOG、代表性 workload、cycle、retry、reclaim drill 或 stop-loss drill
  - 讀寫、清除、修改、複製或復用任何 fresh／前代 sandbox、receipt、log、marker、contract 或 restart denial
  - production data、artifacts、models、主 checkout 既有 dirty 檔、其他專案或使用者文件
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart、reload 或任何 live 排程
  - merge、push、deploy、發布報牌或傳送外部訊息
evidence_path: docs/evidence/TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01/
---

# TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01｜Runtime-aware sample 排程

## Root question

當 hard runtime deadline 早於 sample completion hard deadline，且落在下一 absolute target 與依最近
sampler duration 預估的 completion 之間時，如何避免啟動已知會跨 runtime 的 sample，並在不放寬 cadence
hard maximum／`19/20` target 的前提下準時以 `HARD_RUNTIME_EXCEEDED` 收斂？

## 為何必須另開 root

- Candidate `d4597c3950e4635f32c03519ff8715c580176160` 已修掉 stale target 無界 no-wait loop，但獨立
  Reviewer 以 `REVIEW_NO_GO` 擋下，finding `CADENCE-RUNTIME-PRECEDENCE-P1-002`。
- Reviewer deterministic repro：hard maximum `10s`、schedule `9.5s`、runtime `19.2s`、sampler
  durations `[9.6, 9.6]`。第一筆 completion `9.6s` 後 target reconcile 至 `19.0s`；既有 helper 因
  runtime `19.2s <= sample hard deadline 19.6s` 直接 `True`，在 `19.0s` 啟動第二筆已知會跨 runtime
  的 sample，直到 `28.6s` 才以 `LIVE_SAMPLE_CADENCE_EXCEEDED` 停止。
- Expected 是不啟動第二筆 sample，waiter 先到 target後再以正 timeout等待 runtime `19.2s`，於
  deadline 以 `HARD_RUNTIME_EXCEEDED` 收斂。不得在已完成 implementation／review task 直接修碼。

## 固定契約

1. `sample_interval_seconds` 仍是 completion-to-completion hard maximum；`19/20` absolute target、
   policy/schema、receipt基本語義完全不變。禁止 epsilon、tolerance、ceiling提高或 magic seconds。
2. 最近一次已完成 sampler duration 只作「下一 sample是否可在 deadline前完成」的保守排程依據；
   actual completion gap仍由實測值判定，不得把預估當成 cadence overrun。
3. Runtime deadline與下一 target／預估 completion必須顯式區分：
   - `runtime_deadline <= next_target`：不得啟動 sample；以正 timeout等待 runtime。
   - `next_target < runtime_deadline < next_target + observed_duration`：target到達時不得啟動已知會跨
     runtime的 sample；以正 timeout等待 runtime。
   - `next_target + observed_duration <= runtime_deadline`：可依既有 cadence契約啟動 sample；完成後
     重新判定下一事件。
4. Equality不得靠epsilon隱藏：預估 completion等於runtime deadline時可完成 sample，但 sample實際完成
   後必須依既有實測 runtime／cadence ordering收斂；runtime等於target時不得啟動新 sample。
5. Runtime earlier than or equal to sample hard deadline時，若沒有 actual cadence overrun，最終 reason
   必須是 `HARD_RUNTIME_EXCEEDED`；不得延遲到 sampler返回後錯報 cadence reason。
6. 真正 completion gap `> sample_interval_seconds` 且在 runtime deadline前已發生時，仍使用
   `LIVE_SAMPLE_CADENCE_EXCEEDED`；reason precedence不得反向吞掉已發生的 actual cadence violation。
7. 任一傳給 process waiter的 timeout必須嚴格大於0；禁止 busy loop、back-to-back no-wait sample或
   用人工 child退出冒充 guard收斂。
8. 所有 fail-closed結果須終止 verified PGID、留下 persistent denial、
   `automatic_clear_allowed=false`，同 job第二次執行`75`；child exit `0`不得覆蓋已鎖定 stop reason。

## Checkpoint 0｜身分與 context

- 正式 task先以 bootstrap-only驗證 project、獨立 clean worktree、HEAD exact、HEAD第一親代精確為
  `d4597c3950e4635f32c03519ff8715c580176160`、card實體與index lock；activation前禁止任何動作。
- Source decision前查 CodeGraph；未初始化／無結果才保存 `CONTEXT_DEGRADED`，限域讀
  `run_guarded_job()` cadence/runtime loop與`tests/test_storage_safety.py`。
- 主 checkout三個既有 dirty檔雜湊必須維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

## Checkpoint 1｜Deterministic RED

先新增 Reviewer最小重現並在 parent candidate上證明RED：

- hard maximum `10s`、schedule `9.5s`、runtime `19.2s`、sampler durations `[9.6, 9.6]`。
- RED記錄 target、runtime deadline、completions `[9.6, 28.6]`、waits `[9.4]`、exit/reason、denial與
  PGID；第二筆 sampler不得由測試人工中止。
- Expected GREEN：只完成第一筆 live sample，所有wait嚴格為正，第二次 sample不啟動；clock抵達
  `19.2s`後 `70 / STOPPED / HARD_RUNTIME_EXCEEDED`、PGID quiescent、persistent denial、第二次`75`。

## Checkpoint 2｜最小 GREEN

- 將 helper從「runtime earlier即無條件 safe」改為顯式的 next-event／deadline判定；可回傳結構化決策，
  但 gate不可長成第二套流程引擎。
- O(1) reconcile仍須保留；每輪最多一次 arithmetic target catch-up與一次明確 next-event決策，不得
  逐interval while或反覆no-wait sample。
- Runtime在target與預估completion之間時，loop可以先正等待到target再正等待到runtime，或直接正等待
  runtime；兩者皆不得啟動 sample，且最終reason必須正確。
- Sampler實際耗時若超出預估，返回後須先用actual completion gap與runtime crossing的固定ordering判定；
  補測試鎖定，不得留下模糊優先序。

## Checkpoint 3｜回歸矩陣

至少獨立驗證：

1. Runtime just before target、equal target、just after target但before predicted completion、equal predicted
   completion、just after predicted completion五個排列；無epsilon/tolerance。
2. Runtime與sample hard deadline just before／equal／just after；若actual cadence violation已先發生，
   cadence reason仍正確，否則runtime reason正確。
3. 前代 stale-target repro仍在首筆 `9.6s` completion後以
   `LIVE_SAMPLE_SCHEDULE_OVERRUN` bounded fail-closed，不依賴iteration cap。
4. First-write跨target仍得到正wait與`0 / OK`；healthy `60s`、`0.2s` overhead、`0.005s` lateness仍OK。
5. 真 `60.005s` completion overrun、absolute schedule、late/on-time normal return、child during sample、
   sampler overrun與process-group regressions全數通過。
6. `tests/test_storage_safety.py tests/test_fog_storage_validation.py` affected suite；再跑full suite或記錄精確
   既有 research-ledger `evidence_exists` gap，不得宣稱全綠。

## Acceptance

### AC-1｜Runtime deadline不被sample跨過

Given runtime deadline落在next target與預估sample completion之間
When scheduler選擇下一事件
Then不啟動該sample，使用正timeout到runtime並以`HARD_RUNTIME_EXCEEDED`收斂。

### AC-2｜Cadence語義不退化

Given actual completion gap未超過或已超過hard maximum
When runtime與cadence競態
Then未發生actual overrun時不冒稱cadence；已發生overrun時保留cadence reason與全部停損證據。

### AC-3｜Stale target與健康路徑不退化

Given stale target、first-write與健康scheduled samples
When deterministic regressions執行
Thenbounded reconciliation、正wait、19/20 absolute schedule與OK／schedule-overrun語義全部維持。

### AC-4｜Scope與上線邊界

Given本卡只修shared guard source
When收卡
Then changed files嚴格符合allowlist、八份policy仍`launch_verified=false`、所有live labels維持
disabled／not-loaded，且沒有FOG／workload／cycle／retry、merge、push、deploy或live啟用。

## Deliverables

- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- 本卡
- `docs/evidence/TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01/verification.md`
- 單一candidate commit；第一親代必須是本卡overlay，worktree clean。

## 收卡

Implementation只可回`READY_FOR_REVIEW / CANDIDATE`或reason-coded`BLOCKED`，不得自審、不得直接進
FOG。主線須另開全新獨立Reviewer；只有`REVIEW_GO`才可建立fresh FOG root卡。

## Implementation history

- Activation preflight：formal thread `019fc7c2-dd03-73e1-8059-4fbae7be1298`、projectId、獨立 detached
  worktree、`HEAD=6902618ddf4fabfd9002fbe758de077f9f2be44a`、
  `HEAD^=d4597c3950e4635f32c03519ff8715c580176160`、初始 clean、card 實體與 index lock 均符合。
- CodeGraph：此 worktree 未初始化，保存 `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`；未建立 index，
  fallback 限於 `run_guarded_job()` cadence/runtime loop 與 `tests/test_storage_safety.py`。
- 可證偽假說：
  1. 若根因是 `next_sample_target_is_safe()` 在 runtime deadline 不晚於 sample hard deadline 時無條件
     回傳 safe，則 reviewer exact case 會在 target `19.0s` 啟動第二筆 `9.6s` sample，於 `28.6s` 才以
     cadence reason 收斂；移除這個 bypass 後症狀應消失。
  2. 若 scheduler 顯式區分 `runtime <= target`、`target < runtime < predicted completion` 與
     `predicted completion <= runtime`，並讓前兩者把下一 wake deadline 指向 runtime，則所有 waiter
     timeout 會保持正值，且中間排列不會啟動第二筆 sample。
  3. 若 actual completion-gap 判定仍先於下一排程決策，則真正 cadence overrun 仍會保留
     `LIVE_SAMPLE_CADENCE_EXCEEDED`，而未發生 actual overrun 的 runtime preemption 只會得到
     `HARD_RUNTIME_EXCEEDED`。
- `candidate_commit: reported_in_final_receipt`；candidate parent 固定為
  `6902618ddf4fabfd9002fbe758de077f9f2be44a`。
- RED：hard `10s`、schedule `9.5s`、runtime `19.2s`、durations `[9.6, 9.6]` 在未修 source 得到
  completions `[9.6, 28.6]`、waits `[9.4]`、`70 / LIVE_SAMPLE_CADENCE_EXCEEDED`。
- GREEN：target `19.0s`、predicted completion `28.6s`、sample hard deadline `19.6s`；只完成
  `[9.6]`、waits `[9.6]`，於 `19.2s` 得到 `70 / STOPPED / HARD_RUNTIME_EXCEEDED`，persistent
  denial、PGID quiescent、`automatic_clear_allowed=false`、第二次 `75`。
- Deadline matrices：target／predicted completion 五個排列、sample hard deadline 三個排列、actual
  sampler completion 三個排列全部通過；runtime前已發生 actual cadence violation 時保留
  `LIVE_SAMPLE_CADENCE_EXCEEDED`，未發生時不誤報 cadence。
- 回歸：focused `20 passed, 34 deselected, 11 subtests passed`；affected
  `62 passed, 27 subtests passed`；full `695 passed, 1 failed, 281 subtests passed`，唯一 failure 仍是既有
  research-ledger `evidence_exists` gap。
- Scope：八份 policy `launch_verified=false`、protected hashes維持、`git diff --check`通過；未執行任何
  禁止邊界。完整 RED／GREEN／matrix／actual checks 見本卡 evidence path。
- 收卡：`READY_FOR_REVIEW / CANDIDATE`；implementation 不自審、不進 FOG。

## 五行派工卡

- 任務ID：`TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01`
- 卡片類型｜派工對象：`strict implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、前代implementation卡與verification、Reviewer finding，以及全域
  `rules/24-storage-capacity-safety.md`
- 任務目的：修正runtime deadline被已知會跨期sample越過的precedence缺陷；不跑FOG。
- 證據路徑：`docs/evidence/TOP10-STORAGE-GUARD-RUNTIME-PRECEDENCE-01/`
