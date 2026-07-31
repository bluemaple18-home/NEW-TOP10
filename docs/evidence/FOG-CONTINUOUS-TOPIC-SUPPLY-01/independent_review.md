# FOG-CONTINUOUS-TOPIC-SUPPLY-01 Independent Review

## Identity

- role: Independent Reviewer
- reviewed base SHA: `8cff3d0acbe2cea94f198166cc3a9a581b21319a`
- reviewed candidate SHA: `1674e293daeb759888b950be59d8c30d6020e833`
- review source SHA: `253874667cfcab746aff9f02ed005c447aa277bd`
- decision: `REVIEW_NO_GO`
- candidate source/tests modified by Reviewer: no
- live worker / LaunchAgent / retry circuit / promotion / production artifacts touched: no

## Findings

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001 — non-execute topic-index semantics regressed

- severity: `P1`
- category: `regression`
- path:line: `scripts/run_autonomous_research.py:2237`
- trigger: `execute=false`、`from_queue=false`、`execute_topic_count=1`、非零
  `topic_index`，同時存在 actionable queue row。
- evidence:
  - Reviewer hostile probe預期依 `topic_index=1` 選 `topic:indexed-second`，實際回
    `['topic:queue-first']`。
  - queue清空、indexed topic設為 manager `rejected` 後，實際回 `[]`。
  - base實作的 legacy preview直接回 `selected_topic(topics, topic_index)`，不讀
    queue、也不套執行用 manager gate。
- risk: 常態有 queue 時 `--topic-index` preview失效；被 manager阻擋的題目也無法
  供非執行診斷。這直接違反 Review卡 Standards axis的既有CLI相容性要求。
- suggested_fix: 在 queue仲裁前保留 legacy preview branch；僅 execute與 explicit
  queue paths使用 queue-first與 manager gate。
- validation_gap: Candidate測試只覆蓋 execute mode，未覆蓋 non-execute＋queue、
  非零 index、manager-blocked preview。
- confidence: `high`
- status: `open`

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002 — supply limit未限制exhaustion scan與重複I/O

- severity: `P2`
- category: `performance`
- path:line: `scripts/run_autonomous_research.py:2573`
- trigger: 多個 executable templates均沒有 exact-regime ranking intersection。
- evidence: legal combinations `720`、templates `3`、supply limit `1`的 hostile
  probe仍呼叫 ranking eligibility `2160`次才回
  `TOPIC_SUPPLY_EXHAUSTED`。真實 eligibility每次重掃 candidate與baseline
  inventory。
- risk: exhaustion工作量為 `O(720 × templates)`且與 supply limit無關，可能拖長
  worker並逼近 `max_seconds`，不符合 bounded scan／避免重複I/O的 Standards
  要求。
- suggested_fix: 依 candidate/baseline/horizon/as-of快取 eligibility，另設明確
  attempt budget與receipt計數。
- validation_gap: 現有測試只有單一template；exhaustion fixture在 eligibility前以
  `coverage_processed=720`短路。
- confidence: `high`
- status: `open`

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-003 — 新terminal decision未進入quota可觀測語意

- severity: `P2`
- category: `regression`
- path:line: `scripts/verify_daily_research_quota.py:134`
- trigger: default mode、零topic runs、decision為 `TOPIC_SUPPLY_EXHAUSTED`。
- evidence: 合成artifact獨立驗證得到
  `PARTIAL_NO_MORE_WORK`、failed count `0`、exit語意 `0`、
  worker `no_more_work=true`，但 `research_value_status=LOW_INFORMATION`。
- risk: terminal/exit 0正確，但quota verification與rollup遺失「真正耗盡」原因。
- suggested_fix: verifier不依賴 `from_queue`辨識兩種no-more-work decision，為
  `TOPIC_SUPPLY_EXHAUSTED`輸出穩定且專用的research value status。
- validation_gap: Candidate只有shell grep，未跑新decision的verifier/rollup
  observable regression。
- confidence: `high`
- status: `open`

## Spec axis

Verdict: `PASS`

- default execute與 explicit `--from-queue`均為 deterministic queue-first。
- stale／missing／manager-ineligible queue row會讓位給active fallback。
- queue與fallback同題以 `seen`單輪去重。
- 9 queued actionable fixture可選出題目，不再回 `NO_EXECUTABLE_TOPIC`。
- supplied ID由canonical hypothesis key穩定推導；registry、history、queue與
  same-round四路去重均有獨立測試。
- true exhaustion可輸出 `TOPIC_SUPPLY_EXHAUSTED`，main、quota verifier與worker
  terminal predicate皆為exit 0/no retry語意。

## Standards axis

Verdict: `FAIL`

- exact-regime eligibility、manager lifecycle、run-count與cooldown仍在execute
  arbitration中生效。
- development-only topic使用immutable development episode IDs；command含
  `--development-only`，不含pre-registration/closed registry；未發現production
  promotion或sealed execution繞過。
- P1-001破壞明文要求保留的non-execute/topic-index CLI語意。
- P2-002顯示exhaustion scan雖輸出bounded，但實際candidate evaluation與重複I/O
  未bounded。
- P2-003不影響exit 0，但使新terminal原因在既有quota觀測層降級。

## CodeGraph and source review

- capability preflight: worktree registered；Python tests與CodeGraph皆ready。
- indexed SHA: `253874667cfcab746aff9f02ed005c447aa277bd`；candidate是該SHA祖先，
  `scripts/**`與`tests/**`相對candidate無差異。
- CodeGraph changed-symbol trace:
  - `select_topics_for_run` caller：`main`
  - `replenish_development_topics` caller：`main`
  - `topic_allowed_by_manager` callers：`select_topics_for_run`、
    `apply_closed_experiment_capacity`
- 再以 `base..candidate`逐檔source diff確認7個changed files與上述資料流。

## Independent verification

- targeted suites:
  - `100 passed in 28.61s`
  - files:
    `test_autonomous_research_topic_bank.py`、
    `test_regime_research_autonomy.py`、
    `test_fog_continuous_topic_supply.py`、
    `test_daily_research_quota_verifier.py`
- shell runtime wiring: PASS
- shell syntax: PASS
- `py_compile`: PASS
- `git diff --check base..candidate`: PASS
- changed-file audit: 7/7均在Executor卡allowlist。
- changed source/tests `rg -n '\[DBG-'`: no matches。
- full suite:
  - `611 passed, 1 failed, 4 warnings, 246 subtests passed in 73.50s`

## Full-suite failure disposition

Verdict: `UNRELATED_ENVIRONMENT_ARTIFACT_FAILURE`，不替candidate洗成全綠。

- Reviewer獨立重跑唯一失敗：
  `ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
- Reviewer直接輸出failed checks，只有 `evidence_exists`。
- 缺失證據包含未版控的
  `artifacts/model_experiments/**`、`artifacts/market_context_*.json`、
  `data/clean/features.parquet`與reference CSV。
- `build_research_component_ledger.py`、
  `verify_research_component_ledger.py`、
  `test_research_component_ledger.py`在base..candidate無diff。
- 因此未發現candidate selection/supply導致此失敗的證據；但完整suite仍不是green，
  需在具備歷史artifact的環境重跑後才能關閉該環境缺口。
- 4個warnings來自SHAP/Starlette dependency deprecation；本diff未改依賴或相關
  code，未形成candidate-induced repeated warning pattern。

## Repair requirements

1. `RR-P1-001`
   - 修復 P1-001。
   - 新增observable regressions：
     - non-execute、default mode、有actionable queue、`topic_index=1`仍選index 1；
     - non-execute preview不因manager rejected/cooldown消失；
     - execute default與explicit queue仍保持queue-first＋fallback＋dedupe。
2. `RR-P2-002`
   - 為eligibility inventory加cache與明確attempt bound。
   - 測試須以多template、no-exact-date量測呼叫上限，不得只驗 supplied count。
3. `RR-P2-003`
   - 新增 `TOPIC_SUPPLY_EXHAUSTED` → verifier/rollup stable terminal status測試，
     同時證明exit 0且不進retry/circuit。

## Remaining risks

- 未操作live worker或代表性live autonomous research artifacts，符合卡片Forbidden。
- full suite仍有一個需artifact-rich環境確認的既有失敗。
- 未發現可利用security issue或production promotion/sealed safety risk。

## Final decision

`REVIEW_NO_GO`

Blocking finding：`FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001`。

---

# Repair-1 Independent Re-review

## Identity and preflight

- role: Independent Reviewer（沿用原 Reviewer thread）
- original review source SHA:
  `253874667cfcab746aff9f02ed005c447aa277bd`
- fixed re-review candidate SHA:
  `d166fa1483d2ca2288cda50ea204631cd8b0b972`
- candidate branch:
  `origin/codex/fog-continuous-topic-supply-repair-1-candidate-20260731`
- detached-HEAD preflight: exact HEAD符合固定candidate；tracked與untracked均clean。
- previous review evidence commit:
  `21ff2a386f1563fa2be965c2ce20f85ac928df22`，已由local/remote
  traceable review branches包含，重審前安全落盤。
- capability preflight: worktree registered；Python tests ready；CodeGraph ready。
- CodeGraph indexed SHA:
  `d166fa1483d2ca2288cda50ea204631cd8b0b972`。
- candidate source/tests modified by Reviewer: no。
- live worker / LaunchAgent / retry circuit / promotion / production artifacts touched:
  no。

## Findings disposition

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001 — RESOLVED

- severity: `P1`
- category: `regression`
- path:line: `scripts/run_autonomous_research.py:2215`
- trigger: non-execute default single-topic preview，同時存在actionable queue、
  non-zero topic index，或preview topic處於manager rejected/cooldown。
- evidence:
  - `select_topics_for_run`在queue與manager arbitration前保留
    `not execute and not from_queue and count == 1`分支。
  - 分支從`main`提供的active-bank `fallback_topics`依`topic_index`選題，
    不受queue或執行用manager gate覆寫。
  - execute default與explicit mode仍經queue-first、fallback與dedupe流程。
  - focused regressions：`3 passed, 18 deselected`。
- risk: 原CLI preview regression已解除；未發現修復導致execute routing退化。
- suggested_fix: 已完成，無後續修補要求。
- validation_gap: none；preview、manager-blocked preview與queue arbitration均有
  observable regression。
- confidence: `high`
- status: `resolved`

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002 — PARTIALLY RESOLVED / P2 BACKLOG

- severity: `P2`
- category: `regression`
- path:line: `scripts/run_autonomous_research.py:3835`
- trigger: eligibility cache misses達attempt budget，且完整search尚未完成、未供應題目。
- evidence:
  - `replenish_development_topics`已用
    `(candidate_dir, baseline_dir, horizon, as_of_date)`快取eligibility，並在receipt
    保存attempt budget、cache hits/misses與budget exhaustion。
  - hostile fixture `720` combinations、`3` templates、limit `1`已不再做
    `2160`次重掃；focused regressions為`2 passed, 4 deselected`。
  - function層在budget未完成search時回
    `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`，不冒充true exhaustion。
  - 但`main:3835-3838`只保留`TOPIC_SUPPLY_EXHAUSTED`，其他supply狀態一律
    降為`NO_EXECUTABLE_TOPIC`。Reviewer獨立probe實測：
    nested status=`TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`，
    top-level decision=`NO_EXECUTABLE_TOPIC`，
    verifier=`PARTIAL_NO_MORE_WORK/NO_MORE_EXECUTABLE_TOPIC`，
    worker terminal predicate=`true`。
- risk: 掃描本身已bounded且沒有production/sealed safety風險；但罕見的budget
  incomplete路徑會被營運層誤當成「確定無更多題目」並停止worker，失去Repair卡要求的
  fail-safe observable outcome。
- suggested_fix: 將`TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`傳遞至top-level
  outcome；verifier輸出專用非no-more-work狀態，worker不得把該狀態視為true
  exhaustion terminal。補main→verifier→worker整合測試。
- validation_gap: Candidate只測function receipt的budget狀態，未測該狀態經
  `main`、quota verifier與worker terminal predicate的端到端傳遞。
- confidence: `high`
- status: `open`

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-003 — RESOLVED

- severity: `P2`
- category: `regression`
- path:line: `scripts/verify_daily_research_quota.py:136`
- trigger: default或explicit mode、零topic runs，decision分別為
  `TOPIC_SUPPLY_EXHAUSTED`或`NO_EXECUTABLE_TOPIC`。
- evidence:
  - verifier不再依賴`from_queue=true`。
  - true exhaustion穩定映射為`SUPPLY_EXHAUSTED`；一般無可執行題映射為
    `NO_MORE_EXECUTABLE_TOPIC`。
  - 兩者仍維持`PARTIAL_NO_MORE_WORK`、failed count `0`、exit `0`；
    `TOPIC_SUPPLY_EXHAUSTED`仍在worker terminal allowlist且不進retry/circuit。
  - focused regressions：`3 passed, 10 deselected`；runtime wiring PASS。
- risk: 原terminal原因降級問題已解除。
- suggested_fix: 已完成；P2-002的budget-incomplete新狀態另列backlog。
- validation_gap: none for原finding。
- confidence: `high`
- status: `resolved`

## Spec axis

Verdict: `PASS`

- 原queue-first/default與explicit mode、stale fallback、dedupe、manager
  lifecycle/cooldown與non-execute topic-index語意均通過source trace及targeted
  tests。
- stable ID、四路去重、exact-regime eligibility、bounded deterministic supply、
  development-only與sealed/production fail-closed邊界未見直接regression。
- true `TOPIC_SUPPLY_EXHAUSTED`仍為worker terminal、exit `0`、no retry/circuit。

## Standards axis

Verdict: `PASS_WITH_P2_BACKLOG`

- P1 CLI相容性已恢復。
- ranking eligibility重複I/O已由cache消除，scan有明確attempt bound與receipt。
- true exhaustion與一般no-executable的verifier分類已分離。
- 唯一residual為budget-incomplete狀態未跨`main`／verifier／worker完整傳遞；
  定級P2，未發現P0/P1、production safety、security或repeated warning blocker。

## Independent verification

- focused findings:
  - preview/queue：`3 passed, 18 deselected`
  - cache/budget/exhaustion：`2 passed, 4 deselected`
  - verifier classification：`3 passed, 10 deselected`
- affected targeted suites:
  - `105 passed in 1.73s`
  - files:
    `test_autonomous_research_topic_bank.py`、
    `test_regime_research_autonomy.py`、
    `test_fog_continuous_topic_supply.py`、
    `test_daily_research_quota_verifier.py`
- shell syntax、runtime wiring與`py_compile`: PASS。
- `git diff --check review-source..fixed-candidate`: PASS。
- Repair-1 commit changed-file audit: 7/7均在Repair卡allowlist。
- changed source/tests `rg -n '\[DBG-'`: no matches。
- full suite:
  - `616 passed, 1 failed, 4 warnings, 246 subtests passed in 52.94s`

## Full-suite failure disposition

Verdict: `UNRELATED_ENVIRONMENT_ARTIFACT_FAILURE`，完整suite仍不可宣稱green。

- 唯一失敗仍為
  `ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
- Reviewer獨立建立ledger並直接檢查verifier：唯一failed check為
  `evidence_exists`，缺少12個未版控歷史artifact/reference files。
- 缺失樣本包含：
  `artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json`、
  `artifacts/market_context_2026-06-09.json`、
  `data/clean/features.parquet`、
  `data/reference/stock_industry_map.csv`與
  `data/reference/stock_concept_membership.csv`。
- ledger builder、verifier與test在review source..fixed candidate均無diff。
- 因此沒有Repair-1造成此失敗的證據；需在artifact-rich環境另行關閉環境缺口。
- 4個warnings仍來自SHAP/Starlette dependency deprecation；Repair-1未改依賴或
  相關code，不構成candidate-induced repeated warning pattern。

## Final decision

`REVIEW_GO`

- resolved:
  `FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001`、
  `FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-003`
- open P2 backlog:
  `FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002`
- unresolved P0/P1: none
