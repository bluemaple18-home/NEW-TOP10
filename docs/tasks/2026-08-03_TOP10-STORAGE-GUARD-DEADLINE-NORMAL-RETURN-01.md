---
id: TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01
chain_id: TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN
parent_chain_id: TOP10-STORAGE-FOG-REVALIDATION-FRESH
status: ready_for_review
type: implementation
priority: P0
role: implementation
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 共用 storage guard 的 scheduler／child-exit 競態會把逾期監控誤報為 OK，且前一鏈已兩次漏掉相鄰路徑；屬核心 fail-closed 契約與高回退成本，採 strict Sol high。根因與 RED 已明確，無需 xhigh。
review_model: gpt-5.6-sol
review_reasoning: high
review_model_reason: Reviewer 必須獨立驗證 deadline precedence、process-group、denial 與 receipt 語義；同屬高風險共用安全邊界，不能降為一般 QA。
source_candidate: 7bd4dc0d36eda40847bb5604e3d7f3d2c4dbddf2
prior_blocked_chain: TOP10-STORAGE-FOG-REVALIDATION-FRESH
prior_blocked_status: BLOCKED / REVIEW_REPAIR_LIMIT
traces_to:
  - FOG-REV04-P1-002
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01.md
  - docs/evidence/TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01/verification.md
forbidden_scope:
  - 重新開啟、改寫或宣稱前一 fog revalidation chain 已通過
  - 修改前一鏈 task、review、repair 或 cycle evidence
  - 執行 fog workload、任何 representative workload、cycle、retry 或 fresh revalidation
  - 清除、修改、複製或復用 fresh／前代 sandbox、marker、contract 或 restart denial
  - 提高、放寬、繞過或重解釋 storage／RSS／swap／cadence／runtime ceiling
  - 修改 fog business logic、其他 job、production data/artifacts/models 或主工作區既有 dirty 檔
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - merge、push、deploy、發布外部訊息或自審
---

# TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01｜封住 deadline 後正常回傳競態

## Root question

當 `run_guarded_job()` 已把 `process.wait(timeout)` 排到下一個 monotonic sample／runtime deadline，
但 scheduler 直到 deadline 之後才恢復，而 child 恰好已正常退出、使 wait「正常回傳」時，guard 能否
仍依實際 monotonic completion time fail closed，留下正確 stop reason、persistent restart denial
與 exit `70`，而不是誤報 `0 / OK / reasons=[] / denial absent`？

## 與前一 blocked chain 的邊界

- 前一鏈 `TOP10-STORAGE-FOG-REVALIDATION-FRESH` 已永久停在
  `BLOCKED / REVIEW_REPAIR_LIMIT`；本卡不是第三個 Repair generation，也不得把前一 fog candidate
  改成 `REVIEW_GO`。
- 本卡的新 root question只修共用 guard 的 standalone deadline-normal-return invariant。即使本卡
  通過，前一輪 swap／cadence evidence、restart denial、cycle 2禁止與 production `NO-GO` 均不變。
- 任何未來 fog 重驗都仍需另一張 fresh revalidation卡、全新 sandbox／contract／marker、容量
  preflight與正式 activation；本卡不授權該動作。

## 已保存的失敗證據

獨立 Reviewer 已用 deterministic fake monotonic clock／tempdir 重現：

```text
sample_interval_seconds=10
process_waiter 在 monotonic 11 秒才因 child exit 0 正常回傳
actual:   result=0, status=OK, child_exit_code=0, reasons=[], denial_present=false
expected: result=70, status=STOPPED,
          reasons包含 LIVE_SAMPLE_CADENCE_EXCEEDED,
          persistent denial存在且 automatic_clear_allowed=false
```

已定位故障層：`run_guarded_job()` 只在 `subprocess.TimeoutExpired` 分支檢查 wake／runtime
deadline；正常回傳路徑沒有用 `monotonic_clock()` 比較實際 completion time。

## 排序假說

1. **主假說**：若在 wait 正常回傳後、離開 loop前執行與 timeout path共用的 monotonic deadline
   判定，late-success 將轉為 reason-coded stop；未逾期的 normal child exit保持原語義。
2. **相鄰假說**：若沒有明確 precedence，sample deadline與hard runtime同時／先後到期會產生錯誤
   reason；因此判定必須沿用既有 `runtime_deadline <= next_sample_deadline` 的 hard-runtime優先契約。

每次只驗一個變數；不得藉機重構完整 loop。

## Trace／Acceptance

### FR-001｜Normal-return late sample deadline fail closed

Given child 在 wait 開始時存活、下一 sample deadline為 `D`
When waiter 因 child exit `0` 正常回傳，但 monotonic completion `> D`
Then guard必須回 `70`、receipt為 `STOPPED`、reason包含
`LIVE_SAMPLE_CADENCE_EXCEEDED`、寫入 persistent restart denial，並終止／確認同一 verified PGID
quiescent；不得新增 scheduled或final sample掩蓋逾期。

### FR-002｜Hard runtime precedence

Given `runtime_deadline <= next_sample_deadline`
When waiter正常回傳時 monotonic completion已 `>= runtime_deadline`
Then reason必須是 `HARD_RUNTIME_EXCEEDED`，不得被 cadence reason覆蓋；PGID／denial／exit仍走
同一 fail-closed路徑。

### FR-003｜On-time normal exit不退化

Given waiter在相關 deadline前正常回傳且 child exit `0`
When guard收尾
Then維持既有成功語義，不建立 false denial；child non-zero、fast child、missing valid live sample與
max-runtime既有契約均不得退化。

### FR-004｜Timeout與sampler paths不退化

既有 scheduler `TimeoutExpired`、sampler-duration overrun、child在 overlong sampler內退出、
absolute deadline、first-write、RSS／swap、unknown／registered-unmetered write、PGID與 receipt tests
必須全綠。

## RED → GREEN 契約

1. 先在 `tests/test_storage_safety.py` 建立單一 public-observable RED：只呼叫
   `run_guarded_job()`，斷言 return、receipt、denial與 sample phases；不得只測 private helper。
2. RED必須精確重現 `0 / OK / no denial`，不能以 import error、fixture錯誤或無關 assertion冒充。
3. 最小修復後先讓該 RED轉綠，再加入／完成 runtime precedence與 on-time normal return相鄰測試。
4. 不使用真實長 sleep；fake clock／process waiter必須 deterministic，tempdir內執行。
5. 不新增 `[DBG-*]`；若因診斷臨時加入，收卡前必須清除並 `rg '\[DBG-'` 為零。

## 實作約束

- source decision 前先查 CodeGraph；未初始化／無結果才限域 source fallback並留下 reason。
- deadline判定只使用 monotonic time；不得用 `Sample.timestamp` wall clock。
- late normal return必須與 timeout path共用或等價地套用同一 precedence，避免第三套判斷。
- 不提高 interval、不加容忍值把逾期判為準時、不以 child exit `0` 覆蓋 guard stop。
- cadence stop後不得做額外昂貴 final sample；receipt仍須誠實保留 child exit code。
- 不新增 dependency、不改 policy ceiling/schema，除非既有 receipt欄位的 deterministic test證明是
  本 invariant必要；若需要超出 allowlist立即 `BLOCKED / SCOPE_CHANGE_REQUIRED`。

## 驗證

至少執行：

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -B -m pytest -q -p no:cacheprovider \
  tests/test_storage_safety.py tests/test_fog_storage_validation.py
```

另跑：

- 新增 RED／precedence／on-time cases focused suite。
- full suite；若仍只有既有 ledger evidence gap，精確記錄。
- `git diff --check`、changed-file allowlist、`rg '\[DBG-'`。
- 主 checkout三個既有 dirty檔 hash／集合唯讀核對。
- 八個 launchd labels與 policy `launch_verified=false`唯讀核對；不得改變其狀態。

## Deliverables

- 單一 implementation candidate commit，parent精確為本卡 overlay commit。
- `docs/evidence/TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01/verification.md`，包含 RED、GREEN、
  hypotheses、trace mapping、tests、diff、protected state與 launchd fail-closed evidence。
- worktree clean；changed files嚴格限於 allowlist。
- 收卡只可 `READY_FOR_REVIEW` 或 `BLOCKED / <REASON>`。

strict candidate 必須回主線建立新的獨立 Reviewer；本 implementation不得自審、不得沿用前一
blocked Reviewer作為本 chain的 checker、不得 merge／push／deploy或啟用排程。

## Implementation history

### Strict fact gate

- Activation：formal thread `019fc73e-bafe-7ca1-ac93-f04dbbb4e44f`；provisioning HEAD
  `dcf3ece6847b3a3c3c4c8b3945ea2318fe411899` clean；其第一親代為 source candidate
  `7bd4dc0d36eda40847bb5604e3d7f3d2c4dbddf2`。
- CodeGraph：indexed HEAD 與 provisioning HEAD 一致；`run_guarded_job()` 位於
  `app/storage_safety.py`，public callers包含 `scripts/storage_safety.py:main` 與
  `tests/test_storage_safety.py` 的 guard regression seam。首次自然語意 context未命中，精確
  symbol query與 impact query後定位成功。
- 受影響檔案只限本卡 allowlist；production code只改 `app/storage_safety.py` 的 waiter completion
  deadline判定，public signature、policy schema與 ceiling不變。
- Public observable契約：只由 `run_guarded_job()` 驗證 return code、receipt
  `status/reasons/child_exit_code/samples`、restart denial `reasons/automatic_clear_allowed` 與
  verified process group quiescence。
- 使用者邊界：不執行 fog／representative workload／cycle／retry；不碰前鏈 evidence、sandbox、
  denial、policy ceiling、launchd控制面或外部服務；不 merge／push／deploy／自審。

### 排序假說與驗證計畫

1. 若根因是正常 wait return後缺少 monotonic deadline判定，新增唯一 late-success RED會精確得到
   `0 / OK / reasons=[] / denial absent`；在同一 loop以既有 deadline precedence判定 completion
   後會轉為 `70 / STOPPED / LIVE_SAMPLE_CADENCE_EXCEEDED / denial present`。
2. 若 hard-runtime precedence仍由 `runtime_deadline <= next_sample_deadline` 控制，normal return在
   runtime deadline後只會產生 `HARD_RUNTIME_EXCEEDED`，不會被 cadence reason覆蓋。
3. 若判定只針對 completion已逾 deadline，on-time exit `0`會維持 `OK`且不建立 denial。

驗證順序固定為：唯一 RED → 最小修復 GREEN → precedence/on-time focused cases → storage/fog
affected suite（僅測試，不執行 workload）→ full suite → DBG、allowlist、protected hashes、
launchd/policy唯讀核對與 `git diff --check`。

### RED evidence

- 指令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider
  tests/test_storage_safety.py::StorageSafetyRegressionTest::test_late_normal_return_after_sample_deadline_fails_closed`
- 結果：`1 failed`；public observable actual精確為
  `(0, "OK", 0, [], false, ["preflight", "live", "final"])`，expected為
  `(70, "STOPPED", 0, ["LIVE_SAMPLE_CADENCE_EXCEEDED"], true,
  ["preflight", "live"])`。這排除 import、fixture與無關 assertion失敗，支持主假說。

### Minimal GREEN

- Production diff只在 `wait_for_process()` 正常回傳的 `else` 路徑，以同一
  `runtime_deadline <= next_sample_deadline` precedence檢查實際 monotonic completion；不改
  signature、policy、sampler或 receipt schema。
- 原 RED重跑為 `1 passed`；加入 hard-runtime precedence與 on-time normal-return相鄰案例後，
  focused suite為 `3 passed`。

### Verification receipt

- Adjacent suite：`13 passed`；affected storage/fog unit suite：`53 passed, 16 subtests passed`。
- Full suite：`686 passed, 1 failed, 270 subtests passed`；唯一 failure為既有且不在 diff的
  research component ledger `evidence_exists` gap，精確缺件列表已記於 verification evidence。
- `[DBG-` source scan零命中；`git diff --check`通過；main protected三檔 hashes、八個 launchd
  disabled/not-loaded與八個 policy `launch_verified=false`均維持不變。
- 收卡狀態：`READY_FOR_REVIEW`；需由主線建立新獨立 Reviewer，本 implementation不自審。
