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
