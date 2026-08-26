---
id: TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01
chain_id: TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM
parent_chain_id: TOP10-STORAGE-RUNAWAY
predecessor_chain_id: TOP10-STORAGE-FOG-POST-GUARD-REVALIDATION
predecessor_status: BLOCKED / FORK_REQUIRED_LIVE_SAMPLE_CADENCE_CONTRACT
status: ready_for_review
type: implementation
priority: P0
defect_severity: P1
owner: Codex visible isolated worktree
role: implementation
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 共用 storage guard 的取樣節奏契約會影響所有長工作業，且是 P0 儲存停損根線的 P1 blocker；需同時維持 fail-closed、process-group 與 runtime precedence，不適合降模型。根因與驗收 seam 已精確，無需 xhigh。
source_base: 73a1d17dee7a2f42b54d944db57f2d4656377447
source_base_review_status: REVIEW_GO
review_finding: FOG-CADENCE-P1-001
review_thread: 019fc77c-81d8-7ac2-8e74-5fb2e6bae3e7
frontier: true
cycle_2_authorized: false
retry_authorized: false
live_authorized: false
traces_to:
  - TOP10-STORAGE-RUNAWAY-01#AC-3
  - TOP10-STORAGE-RUNAWAY-01#AC-5
  - TOP10-STORAGE-FOG-POST-GUARD-REVALIDATION-01#AC-2
  - FOG-CADENCE-P1-001
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01.md
  - docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/**
forbidden_scope:
  - 提高、放寬、容忍或重新解釋 sample_interval_seconds 與任何 storage／RSS／swap／runtime ceiling
  - 修改 storage policy、fog business logic、runner、其他 job 或 launchd 設定
  - 執行 fog、代表性 workload、cycle、retry 或任何 production／live 程序
  - 修改、清除、複製或復用 fresh／前代 sandbox、raw receipt、log、marker、contract 或 restart denial
  - production data、artifacts、models、主 checkout 既有 dirty 檔、其他專案或使用者文件
  - 瀏覽器、provider、connector、外部服務、merge、push、deploy 或啟用排程
evidence_path: docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/
verification:
  - deterministic fake-clock RED／GREEN：60 秒 ceiling、固定正 sampler overhead 與正常 scheduler lateness
  - 真正 completion gap 超過 hard maximum 時仍 fail closed、PGID quiescent、persistent denial
  - late normal return、sampler overrun、hard runtime precedence 與 absolute-deadline regression
  - affected storage safety tests、full pytest 或精確既有 gap、git diff --check、worktree clean
---

# TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01｜修正 Guard 取樣排程與硬上限零餘裕

## Root question

在不改變 `sample_interval_seconds=60` 硬上限、不加入 tolerance、也不重跑 FOG 的條件下，
shared storage guard 能否把「目標取樣排程」與「完成到完成的最大安全間距」分開，使健康長工作業在
固定正 sampler overhead 與正常 scheduler lateness 下持續受監控，而真正超過硬上限時仍立即 fail closed？

## 已確認根因

獨立 Reviewer 對候選 `5d780b236c95e5f64ee425482e0e9e87af856862` 判定
`REVIEW_NO_GO / FOG-CADENCE-P1-001`：

- `run_guarded_job()` 以 `started_at + sample_interval_seconds` 作下一次 wake deadline；取樣完成後又以
  `sample_completed_at - last_safe_observation_at > sample_interval_seconds` 判定 cadence。
- 因此排程目標本身就在硬上限上，沒有可達成的 timing margin。deterministic fake-clock 以 ceiling
  `60s`、sampler overhead `0.2s`、正常 lateness `0.005s` 重現 completion gap `60.005s`，健康 child
  被錯誤收成 `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`。
- 真實 FOG cycle 1 的兩筆 live completion gap 為 `60.20504283905029s > 60s`；同次 receipt 的 RSS、
  swap、bytes、files、free space、growth 與 write scope 均未超限，故不是 workload 容量超標。
- 前一 `TOP10-STORAGE-FOG-REVALIDATION-FRESH` 仍永久保持 `BLOCKED / REVIEW_REPAIR_LIMIT`；
  `TOP10-STORAGE-FOG-POST-GUARD-REVALIDATION` 改判 `BLOCKED / FORK_REQUIRED_LIVE_SAMPLE_CADENCE_CONTRACT`。
  本卡是全新 root fork，不得改寫或重啟任一前代 chain。

## 固定契約

1. `sample_interval_seconds` 仍是 completion-to-completion 的 hard maximum；`60` 必須仍代表最多 `60s`，
   不得變成 `60 + epsilon`、`<= 60.x` 或由 receipt 文案重新解釋。
2. 目標 wake／sample-start 必須在 hard maximum 前有明確、可推導、bounded 的正 headroom。不得把
   真實觀測的 `0.205s` 或任意 magic tolerance 寫成例外；若引入 lead，須由既有 ceiling 契約導出、
   有上下界並由測試鎖定。
3. 使用 monotonic absolute schedule，避免每輪 sampler duration 累積成無界 drift；同時不得因趕進度
   形成 busy loop、零 timeout 或無界取樣頻率。
4. sampler 本身耗時太久、scheduler 真正晚到、first-write／scheduled／final sample 的完成間距真的
   超過 hard maximum時，必須保留 `LIVE_SAMPLE_CADENCE_EXCEEDED`、終止同一 verified PGID、寫入
   persistent restart denial，且 child exit `0` 不得覆蓋 stop。
5. `HARD_RUNTIME_EXCEEDED` deadline precedence、late-normal-return 修復與既有 receipt／denial schema
   不得退化。

## Requirements

### FR-001｜排程與硬上限分離

修改 shared guard 的 scheduled live-sampling seam，使 target wake 在 hard maximum 前發生；headroom 必須
由 policy ceiling 與明確 bounded 規則推導。不得提高 ceiling、加入比較 tolerance 或修改 policy 值。

### FR-002｜健康長工作業可持續監控

以 deterministic fake-clock 建立先失敗後通過的測試：ceiling `60s`、每次 live sampler 固定耗時
`0.2s`、waiter／scheduler 固定正常 lateness `0.005s`，至少跨越兩次 scheduled samples。健康 child
不得出現 cadence reason或denial，所有 completion gaps 必須 `<= 60s`，且 wait timeout保持正值。

### FR-003｜真正超時仍 fail closed

另以 deterministic test 證明 sampler overhead 或 scheduler lateness使 completion gap真正超過 `60s`
時，結果仍為 `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`；verified PGID quiescent、denial
`automatic_clear_allowed=false`，且不得再啟動下一次sample或retry。

### FR-004｜既有 precedence 與無 drift

保留或補強下列 regression：

- monotonic absolute deadlines 不因 sampler duration 逐輪累積 drift；
- waiter在sample deadline後正常回傳仍 fail closed；
- hard runtime早於sample deadline時理由仍優先為 `HARD_RUNTIME_EXCEEDED`；
- on-time child、first-write sample、scheduled sample、child during sample 與 final sample phase語義不變。

### FR-005｜純 source 修復

本卡只允許修改 `app/storage_safety.py`、`tests/test_storage_safety.py`、本卡與 bounded verification
evidence。禁止執行 FOG／代表性 workload、觸碰任何 sandbox／denial、修改 policy 或啟用 live 排程。

## Acceptance

### AC-1｜健康 cadence

Given `sample_interval_seconds=60`、固定正 sampler overhead與正常 scheduler lateness
When 健康長 child跨越至少兩個 scheduled samples
Then每個completion gap皆`<=60`、無cadence stop／denial、timeout為正且排程無無界drift。

### AC-2｜硬上限不放寬

Given相同 ceiling且completion gap真正超過`60`
When guard完成取樣或收到late normal return
Then回`70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`、PGID quiescent、persistent denial成立；不得靠
epsilon、tolerance、ceiling變更或receipt解釋通過。

### AC-3｜runtime precedence

Given hard runtime早於下一個sample hard deadline
When waiter於deadline後TimeoutExpired或正常回傳
Then只以`HARD_RUNTIME_EXCEEDED`收斂，child exit不得覆蓋，既有deadline-normal-return修復仍通過。

### AC-4｜隔離與回歸

Given source base `73a1d17dee7a2f42b54d944db57f2d4656377447`
When完成實作
Then changed files只在allowlist；affected tests通過，full pytest通過或只保留可精確重現的既有gap，
`git diff --check`通過、worktree clean，主 checkout三個protected paths/hash不變。

## 驗證順序

1. 驗證正式 thread、獨立 worktree、HEAD exact、source parent、clean state與index lock。
2. Source decision前查CodeGraph；未初始化／無結果時保存`CONTEXT_DEGRADED`並限域讀
   `run_guarded_job`與storage safety tests。
3. 先加入可在舊source重現 `FOG-CADENCE-P1-001` 的 deterministic RED，保存失敗摘要。
4. 實作最小修正；跑新GREEN與所有cadence／runtime／PGID／denial affected tests。
5. 跑full pytest；若僅有基線既有failure，需用source base同命令重現並保存精確差異。
6. 驗證JSON／YAML（若有）、`git diff --check`、allowlist、protected hashes與worktree clean。

## Deliverables

- 最小 source diff與deterministic regression tests。
- `docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/verification.md`，至少包含RED／GREEN、
  completion gaps、wait timeouts、exit／reason／denial／PGID、affected與full suite結果、allowlist與hash核對。
- 更新本卡implementation receipt與狀態。
- 單一candidate commit；不得merge、push、deploy、執行workload或啟用排程。

## 收卡狀態

- `READY_FOR_REVIEW / CANDIDATE`
- `BLOCKED / SOURCE_OR_TEST_CONTRACT`
- `BLOCKED / PREFLIGHT_OR_SCOPE`

本卡為strict；candidate完成後必須回主線另開全新獨立Reviewer。Implementation不得自審；Review
未`REVIEW_GO`前不得回到FOG cycle，所有live排程維持停用。

## Implementation receipt

- `candidate_commit: reported_in_final_receipt`；candidate parent固定為
  `dad236825731130473e3b1ef543ff5b6605c8700`。
- Activation：formal thread `019fc789-3422-7711-8b8c-bde172db1ba1`；HEAD
  `dad236825731130473e3b1ef543ff5b6605c8700`，第一親代
  `73a1d17dee7a2f42b54d944db57f2d4656377447`；獨立 detached worktree、card/index lock與初始 clean
  全部通過。
- CodeGraph：獨立 worktree未初始化，保存 `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`；未建立
  index，fallback只讀 `run_guarded_job()` 與 storage safety regression seam。
- RED：`60s` ceiling、`0.2s` overhead、`0.005s`正常 lateness在舊 source得到
  `70 / LIVE_SAMPLE_CADENCE_EXCEEDED`，completion gap `[60.005]`、wait `[59.8]`。
- GREEN：target schedule使用 hard maximum的`19/20`，5% headroom由既有`1..300s` ceiling導出並
  bounded於`0.05..15s`；hard deadline仍是completion-to-completion完整 ceiling。兩個 scheduled
  gaps為`[57.005, 57.0]`，waits為`[56.8, 56.795, 56.795]`且全為正。
- 真超時：completion gap `60.005s`仍回`70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED`，persistent
  denial、verified PGID quiescence與第二次`75`成立；child exit`0`、hard runtime precedence與
  late-normal-return regressions均通過。
- 驗證：focused `8 passed`；affected `55 passed, 16 subtests passed`；full
  `688 passed, 1 failed, 270 subtests passed`，唯一 failure為既有 research ledger
  `evidence_exists` gap。完整證據見
  `docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/verification.md`。
- 收卡：`READY_FOR_REVIEW / CANDIDATE`。未執行FOG／workload／cycle／retry，未碰前代 sandbox或
  launchd／外部控制面，未merge／push／deploy／自審。

## 五行派工卡

- 任務ID：`TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01`
- 卡片類型｜派工對象：`strict implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、`docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01.md`、全域`rules/24-storage-capacity-safety.md`
- 任務目的：分離sample target schedule與completion hard maximum；60秒ceiling不放寬，健康overhead/lateness不誤停，真正超時仍fail closed。
- 證據路徑：`docs/evidence/TOP10-STORAGE-GUARD-CADENCE-SCHEDULE-HEADROOM-01/`
