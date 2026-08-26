---
id: TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01
chain_id: TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET
parent_chain_id: TOP10-STORAGE-RUNAWAY
predecessor_candidate: 8b01eb7f9479c8a4d0e104f4a56edd574ee5d150
predecessor_status: REVIEW_NO_GO / FORK_REQUIRED_STALE_TARGET
blocking_review_thread: 019fc799-2c93-7a72-9340-f541094340e1
blocking_finding: CADENCE-HEADROOM-P1-001
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
model_reason: P1 位於控制八條工作入口的 P0 共用容量守門；修復同時牽涉 cadence hard maximum、取樣頻率、程序終止與 persistent denial，需 strict Sol high。缺陷與驗收已具體，無需 xhigh。
frontier: true
source_parent: 8b01eb7f9479c8a4d0e104f4a56edd574ee5d150
traces_to:
  - TOP10-STORAGE-RUNAWAY-01#AC-3
  - TOP10-STORAGE-RUNAWAY-01#AC-4
  - TOP10-STORAGE-RUNAWAY-01#AC-5
  - TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01
  - CADENCE-HEADROOM-P1-001
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01.md
  - docs/evidence/TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01/**
forbidden_scope:
  - 修改 storage policy ceiling、fog business logic、runner、其他七個 job 或 launch 定義
  - 執行 FOG、代表性 workload、cycle、retry、reclaim drill 或 stop-loss drill
  - 讀寫、清除、修改、複製或復用任何 fresh／前代 sandbox、receipt、log、marker、contract 或 restart denial
  - production data、artifacts、models、主 checkout 既有 dirty 檔、其他專案或使用者文件
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart、reload 或任何 live 排程
  - merge、push、deploy、發布報牌或傳送外部訊息
evidence_path: docs/evidence/TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01/
---

# TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01｜過期 target 有界收斂

## Root question

在不放寬 `sample_interval_seconds` completion-to-completion hard maximum、也不改變 95% target
headroom 的前提下，如何讓 sampler duration 落在 `(schedule interval, hard maximum]` 時不形成無限
連續取樣，並以有界 catch-up 或語義精確的 fail-closed 結果收斂？

## 為何必須另開 root

- Candidate `8b01eb7f9479c8a4d0e104f4a56edd574ee5d150` 已由獨立 Reviewer 判定
  `REVIEW_NO_GO`，finding `CADENCE-HEADROOM-P1-001`；不得在已完成的 implementation／review task
  直接改檔，也不得進入 FOG 重驗。
- Reviewer deterministic repro：hard maximum `10s`、target interval `9.5s`、每次 sampler
  duration `9.6s`。completion 為 `[9.6, 19.2, 28.8, 38.4, 48.0]`，每個 gap約
  `9.6s <= 10s`，但 target 落後由 `0.1s`增至`0.4s`、`wait_timeout_count=0`；harness只因第五次
  主動終止 child才離開，證明 `next_sample_target += interval` 未有界收斂。
- 本卡是新 source root，只修 stale-target invariant；前代 FOG鏈與 persistent denial狀態維持不變。

## 固定契約

1. `sample_interval_seconds` 仍是完成到完成的完整 hard maximum；禁止提高 ceiling、加入
   epsilon／tolerance、改 policy／schema或重新解釋 receipt。
2. 95% target（`19/20`）與 5% bounded headroom 保持由 hard maximum推導；不得改成實測 magic
   seconds，亦不得假設 sampler overhead 永遠小於 headroom。
3. target仍須基於 monotonic absolute schedule；機會性 first-write sample與 scheduled sample交錯時，
   必須顯式 reconcile已過期 target，不能累積無界 drift。
4. 任何傳給 process waiter的 timeout必須嚴格大於0；target已在過去時不得反覆直接取樣。
5. 若無法在保留正等待且不跨 hard deadline的條件下安全排出下一次 sample，必須 fail closed、終止
   verified PGID並留下 persistent denial；不得靠 busy loop維持表面上的 completion gap。
6. 若新增 distinct scheduler-overrun reason，必須使用穩定、語義精確的
   `LIVE_SAMPLE_SCHEDULE_OVERRUN`（或等價明確名稱）並補齊 receipt／denial regression；當實際
   completion gap `<= hard maximum` 時不得冒稱 `LIVE_SAMPLE_CADENCE_EXCEEDED`。
7. 真正 completion gap `> hard maximum` 仍必須是
   `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`；child exit `0`不得覆蓋，PGID quiescence、
   persistent denial與第二次執行`75`不得退化。
8. hard runtime早於 sample hard deadline時仍優先；late normal return、first-write、child during
   sample與 final sample語義不得退化。

## Checkpoint 0｜身分與 context

- 正式 task先以 bootstrap-only驗證 project、獨立 clean worktree、HEAD exact、HEAD第一親代精確為
  `8b01eb7f9479c8a4d0e104f4a56edd574ee5d150`、card實體與 index lock；activation前禁止動作。
- Source decision前查 CodeGraph；未初始化／無結果才保存 `CONTEXT_DEGRADED` 並限域讀
  `run_guarded_job()` cadence loop及`tests/test_storage_safety.py`。
- 主 checkout三個既有 dirty檔雜湊必須維持：
  - `scripts/build_weekend_universe_inventory.py`：
    `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
  - `tests/test_weekend_universe_inventory_snapshot.py`：
    `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
  - `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
    `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

## Checkpoint 1｜Deterministic RED

先新增 reviewer repro的 regression，並在 parent candidate上證明 RED：

- hard maximum `10s`、derived schedule `9.5s`、sampler duration `9.6s`。
- child保持存活；harness須有明確 iteration cap，不能讓測試本身掛死。
- RED必須記錄 completion times／gaps、target lag、wait timeout count、sample count與 process結果，精確
  證明 parent會連續無等待取樣。
- 測試不得以放寬 ceiling、人工讓 gap超過10秒或第五次手動終止當成 GREEN acceptance。

## Checkpoint 2｜最小 GREEN

- 對 immediate、first-write與 scheduled sample分別處理 target ownership；機會性 sample若跨過 target，
  應以 bounded arithmetic reconciliation移到可判定的未來 absolute target，不可用無界 while loop。
- Scheduled sample完成後若下一 target仍不在未來，必須在固定步數內得到安全的 future target或明確
  fail-closed；禁止一輪只加一個仍在過去的 target。
- GREEN必須證明 reviewer repro在有限 sample／有限 loop內收斂：若選 fail-closed，需有正確 reason、
  exit `70`、PGID quiescent、persistent denial、第二次`75`；若選 bounded catch-up，需證明後續 waiter
  timeout為正、completion gap仍不超過 hard maximum且 target lag不成長。
- 不得把受測 child的人工 SIGTERM／非零 exit當作 guard收斂證據。

## Checkpoint 3｜回歸矩陣

至少獨立驗證：

1. `60s` hard max、`0.2s` overhead、`0.005s`正常 lateness、兩次 scheduled samples仍
   `0 / OK`，gaps都`<=60`、waits全為正、無 denial。
2. completion gap `60.005s`仍
   `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`、PGID quiescent、denial persistent、第二次`75`。
3. first-write剛好跨 target的 deterministic案例沒有 back-to-back no-wait sample；reconciled target仍在
   hard deadline前，下一 wait嚴格為正。
4. absolute schedule drift、sampler真正 overrun、hard runtime precedence、late／on-time normal return、
   child during sample與 process-group regression全數通過。
5. `tests/test_storage_safety.py tests/test_fog_storage_validation.py` affected suite；再跑 full suite或記錄
   精確既有 research-ledger `evidence_exists` gap，不得宣稱全綠。

## Acceptance

### AC-1｜無無界 no-wait loop

Given sampler duration大於target interval但不大於hard maximum
When target在sample完成後已過期
Then guard在固定步數內得到正wait或語義精確的fail-closed結果，不會無限直接取樣。

### AC-2｜Hard maximum不變

Given completion gap未超過或真正超過hard maximum
When guard判定結果
Then schedule-overrun與cadence-overrun理由不混淆；真正overrun仍使用既有cadence reason與全部停損證據。

### AC-3｜健康與runtime契約不退化

Given正常overhead／lateness、first-write與hard runtime競態
When deterministic regressions執行
Then健康案例保持OK，runtime precedence、late-normal-return與positive waiter契約全部成立。

### AC-4｜Scope與上線邊界

Given本卡只修shared guard source
When收卡
Then changed files嚴格符合allowlist、八份policy仍`launch_verified=false`、所有live labels維持
disabled／not-loaded，且沒有FOG／workload／cycle／retry、merge、push、deploy或live啟用。

## Deliverables

- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- 本卡
- `docs/evidence/TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01/verification.md`
- 單一 candidate commit；第一親代必須是本卡 overlay，worktree clean。

## 收卡

Implementation只可回 `READY_FOR_REVIEW / CANDIDATE` 或 reason-coded `BLOCKED`，不得自審、不得直接
進FOG重驗。主線須另開全新獨立 Reviewer；只有 `REVIEW_GO` 才能再建立新的 fresh FOG root卡。

## Implementation receipt

- `candidate_commit: reported_in_final_receipt`；candidate parent 固定為
  `7b43531dbae8d7231a3f333023cbcdab1d61ecd0`。
- Activation：formal thread `019fc7a6-8a96-7e70-b7f7-66771c624933`；projectId、獨立 detached
  worktree、HEAD／parent exact、初始 clean、card 與 index lock 均通過。
- CodeGraph：此 worktree 未初始化，保存 `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`；未建立 index，
  fallback 限於指定 cadence loop 與 storage safety tests。
- RED：`10s` hard maximum、`9.5s` target、`9.6s` sampler 得到 completions
  `[9.6, 19.2, 28.8, 38.4, 48.0]`、gaps 全部 `<=10s`、target lag 由 `0.1s` 增至
  `0.5s`、waits `[]`；iteration cap 才終止，精確重現無界 no-wait sampling。
- GREEN：過期 target 以 O(1) arithmetic reconcile，並以剛完成 sampler duration 與既有 completion
  hard deadline判定下一 absolute target 是否可安全排程；重現案例在首筆 `9.6s` completion 後以
  `70 / STOPPED / LIVE_SAMPLE_SCHEDULE_OVERRUN` fail closed，persistent denial、PGID quiescence與第二次
  `75` 成立，未冒稱 cadence overrun。
- First-write：`9.49s` immediate completion 後，`0.02s` first-write sample 在 `9.51s` 跨 target；只保留
  兩筆 live completion，reconciled target `19.0s`，下一 waiter timeout `9.49s > 0`，結果 `0 / OK`。
- 回歸：healthy `60s`、true `60.005s` overrun、absolute schedule、runtime precedence、late／on-time
  normal return、sampler overrun、child during sample均通過；focused `12 passed`，affected
  `57 passed, 16 subtests passed`。Full suite `690 passed, 1 failed, 270 subtests passed`，唯一 failure
  仍是既有 research ledger `evidence_exists` gap。
- Scope：八份 policy 保持 `launch_verified=false`；protected hashes維持；`git diff --check`通過；未執行
  FOG／workload／cycle／retry、未碰前代 sandbox／denial、未操作 launchd、未 merge／push／deploy／自審。
- 收卡：`READY_FOR_REVIEW / CANDIDATE`；完整證據見本卡 evidence path。

## 五行派工卡

- 任務ID：`TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01`
- 卡片類型｜派工對象：`strict implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、前代 cadence implementation卡與verification、Reviewer finding，以及全域
  `rules/24-storage-capacity-safety.md`
- 任務目的：修正 stale absolute target造成的無界 no-wait sampling；不放寬 hard maximum，不跑FOG。
- 證據路徑：`docs/evidence/TOP10-STORAGE-GUARD-CADENCE-STALE-TARGET-01/`
