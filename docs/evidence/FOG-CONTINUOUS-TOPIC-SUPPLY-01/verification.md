# FOG-CONTINUOUS-TOPIC-SUPPLY-01 Verification

## Identity

- role: Executor
- base SHA: `8cff3d0acbe2cea94f198166cc3a9a581b21319a`
- candidate SHA: `SELF`（由包含本檔的單一 candidate commit 解析）
- candidate exit: `READY_FOR_INDEPENDENT_REVIEW`
- live execution: 未執行

## Root cause and falsifiable hypotheses

### H1 — active-bank ownership deadlock

若 deadlock 來自 `write_topic_bank(... queued_ids=...)` 排除 queued topics，而
default worker 又只把 active bank 傳給 selector，則 active bank 為空時即使 queue
有 actionable topics，main 仍會輸出 `selected_topics=[]`。

Routing RED 已直接重現此症狀；修正 main 以 current generated topics 作 queue
authority，並只用 active-bank 集合作 fallback 後症狀消失。

### H2 — `--from-queue` 是 queue-only 分岔

若顯式 `--from-queue` 使用 queue-only path，stale queue row 會阻止 active fallback，
且 default／顯式模式排序不一致。RED 顯示 default 順序為 active-first，而顯式模式
沒有 fallback；統一仲裁後兩者均為 queue-first、active fallback。

### H3 — 固定 profile catalog 沒有 replenishment seam

若既有流程只產生 ranking directory × 固定 validation profiles，當既有路徑都不可
執行時只能輸出 `NO_EXECUTABLE_TOPIC`。Supply RED 因不存在
`replenish_development_topics` 而失敗；GREEN 加入 bounded contract-derived supply。

## RED receipts

### Routing RED

```text
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  -k 'main_routes_actionable_queue_when_active_bank_is_empty or queue_first_falls_back_and_deduplicates_for_all_cli_modes'

2 failed
- active bank 空時 selected_topics=[]，decision=NO_EXECUTABLE_TOPIC
- default 順序 active-first；顯式 --from-queue 缺 active fallback
```

最終 regression fixture 已擴為 9 個 queued actionable topics。

### Supply RED

```text
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_fog_continuous_topic_supply.py

2 failed
- AttributeError: replenish_development_topics 不存在
```

失敗點是缺少目標能力，不是 import、fixture 或環境錯誤。

## GREEN and acceptance evidence

### Routing checkpoint

```text
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_regime_research_autonomy.py \
  -k 'selection or queue or topic_bank or exact_date_topic'

22 passed
```

涵蓋：

- 9 個 queued actionable topics、active bank 空時仍至少選出 1 題。
- queue-first deterministic ordering。
- stale／missing queue row 不阻擋 active fallback。
- queue 與 fallback 同題只選一次。
- default worker mode 與顯式 `--from-queue` 結果一致。
- exact-regime ineligible topics 不會被 queue／index／fallback 帶回。
- manager lifecycle、run-count 與 cooldown gate 保持 authority。

### Supply checkpoint

```text
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_fog_continuous_topic_supply.py

5 passed
```

涵蓋：

- canonical hypothesis tuple 產生 stable topic ID；相同輸入重跑 ID 完全一致。
- registry、history、queue、same-round 四處去重。
- 每輪 supply limit 有上限，且只使用現有 allowlisted matrix runner。
- 每一候選重新驗證 repo-owned candidate／baseline ranking inventory 與
  horizon-safe exact-regime dates。
- supplied topic 固定為 `DEVELOPMENT_SCREEN`，只允許 immutable development
  episodes；validation、embargo、sealed 全數排除。
- development command 帶 `--development-only`，不帶 `--pre-registration` 或
  `--experiment-registry`。
- 720 個 legal combinations 全部已處理時，輸出
  `TOPIC_SUPPLY_EXHAUSTED`、`coverage_processed=720`、evidence refs，main exit 0。

### Affected targeted suites

```text
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_regime_research_autonomy.py \
  tests/test_fog_continuous_topic_supply.py \
  tests/test_daily_research_quota_verifier.py

100 passed
```

### Shell and compile checks

```text
bash -n scripts/run_fog_research_worker.sh \
  scripts/run_daily_research_quota.sh \
  tests/test_fog_runtime_time_wiring.sh
bash tests/test_fog_runtime_time_wiring.sh
<repo-root>/.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_fog_continuous_topic_supply.py

PASS
```

Worker source明確把 `TOPIC_SUPPLY_EXHAUSTED` 與 `NO_EXECUTABLE_TOPIC` 視為
terminal no-more-work；研究 command 本身 exit 0，因此不開 retry circuit。

## Full suite

```text
<repo-root>/.venv/bin/python -m pytest -q

611 passed, 1 failed, 4 warnings, 246 subtests passed
```

唯一失敗：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

失敗 check 為 `evidence_exists`。獨立 worktree 缺少未版控的歷史
`artifacts/model_experiments/**`、`artifacts/market_context_*.json`、
`data/clean/features.parquet` 與 reference CSV；不是本卡 selection／supply
behavior failure。以下三個相關檔案相對 base SHA 無 diff：

- `scripts/build_research_component_ledger.py`
- `scripts/verify_research_component_ledger.py`
- `tests/test_research_component_ledger.py`

本卡 allowlist 不允許修改上述 verifier 或補造缺失 artifacts，因此保留為獨立
環境 blocker，不以假資料或放寬 verifier 製造全綠。

## Data contract

```text
data_contract:
  source_and_grain: exact-regime × ranking artifact × legal parameter combination
  confirmed_schema_and_status_semantics: repo-owned research contract、manager registry/history/queue
  joins_and_cardinality: stable topic ID 對 registry/history/queue 一對一去重
  aggregation_invariants: 同輪同 topic 最多一次；processed combination 不再補題
execution_boundary:
  database_pushdown: n/a
  controlled_artifacts: autonomous research run/topic-bank/manager receipts
degradation:
  unavailable_data: 缺 exact-regime authority 或 ranking 交集時 fail closed
  provisional_thresholds: 無
  model_limits: 只覆蓋 contract 已證明可執行的四維 720-family
validation:
  fixture_or_unit: 100 passed affected targeted suites
  representative_real_data: 未執行 live worker；卡片明文禁止
  old_vs_new_reconciliation: routing RED→GREEN public main behavior
  business_invariants: queue ownership、exact regime、development-only、no promotion
warnings_and_exclusions: full suite 1 個 unrelated missing-artifact failure
remaining_risk: 未以 live autonomous research artifacts 做受控 replay
```

## Safety and scope audit

- 未修改 production ranking/model/weights/baseline/promotion state。
- 未讀寫 closed experiment registry、sealed split、validation/embargo artifacts。
- 未操作 LaunchAgent、retry state/context/circuit 或 live worker。
- 未 merge、push、deploy 或清理 branch/worktree。
- changed files 僅限卡片 allowlist。
- `[DBG-...]` instrumentation：無。

## Remaining risk

- 獨立 worktree 沒有 main checkout 的未版控研究 artifacts，因此未做代表性
  read-only live-artifact replay。
- Full suite 的 component-ledger artifact existence check 仍需在具備該批歷史
  artifacts 的環境重跑。
- Candidate 尚未經 strict independent Reviewer；本 Executor 不宣告 Review GO。
