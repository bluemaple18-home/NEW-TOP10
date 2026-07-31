---
id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01
status: READY_TO_DISPATCH
type: maintenance
ownership: executor
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 狹窄但跨main outcome、quota verifier與shell worker terminal語意，契約明確且有既有finding／probe，適合standard跨檔實作並獨立Review
chain_id: FOG-TOPIC-SUPPLY-BUDGET-STATUS
parent_card_id: FOG-CONTINUOUS-TOPIC-SUPPLY-01
source_finding_id: FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002
code_base_sha: 99b101bae6a91fcceb2d13c6f141a3fdfc8cb937
---

# FOG-TOPIC-SUPPLY-BUDGET-STATUS-01

## Role

你是本卡 Executor，不是 Reviewer 或 mainline Integrator。

- 在獨立 clean worktree／branch 建立 RED、實作、驗證並產生單一 candidate
  commit。
- 完成後只交 `READY_FOR_INDEPENDENT_REVIEW`。
- 不得自行整合 `main`、操作 live scheduler或關閉 Review finding。

## Goal

完整傳遞 `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`，避免罕見的
budget-incomplete search被降成確定的 `NO_EXECUTABLE_TOPIC`。

## Requirements

- `FR-BUDGET-01`：`replenish_development_topics()` 回傳
  `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED` 且沒有topic時，top-level outcome
  必須保留相同decision與完整`topic_supply` receipt。
- `FR-BUDGET-02`：quota verifier須將該decision分類為穩定、
  retryable且非no-more-work的status/research value；exit維持0，不得進
  worker failure retry/circuit。
- `FR-BUDGET-03`：Fog worker不得把該decision或verifier status視為terminal；
  同一invocation可進下一個bounded batch。
- `SC-BUDGET-01`：true `TOPIC_SUPPLY_EXHAUSTED`與一般
  `NO_EXECUTABLE_TOPIC`既有terminal／exit 0語意不得改變。
- `SC-BUDGET-02`：budget-incomplete main → verifier → worker observable
  regression全綠，且既有continuous topic supply tests不退化。

## Scope

- `scripts/run_autonomous_research.py`保留top-level budget-incomplete decision。
- quota verifier輸出專用、非no-more-work狀態。
- worker不得把budget-incomplete視為true exhaustion terminal。
- 補main → verifier → worker observable regression。

## Slices

### `SLICE-BUDGET-RED`

- `traces_to`: FR-BUDGET-01, FR-BUDGET-02, FR-BUDGET-03
- `blocked_by`: none
- 用公開artifact／script語意建立三個RED：
  - main將budget status錯降為`NO_EXECUTABLE_TOPIC`；
  - verifier錯標`PARTIAL_NO_MORE_WORK`／`NO_MORE_EXECUTABLE_TOPIC`；
  - worker因此提前terminal。

### `SLICE-BUDGET-GREEN`

- `traces_to`: FR-BUDGET-01, FR-BUDGET-02, FR-BUDGET-03
- `blocked_by`: SLICE-BUDGET-RED
- 最小修改完整傳遞decision、穩定retryable verifier status與worker
  non-terminal語意。

### `CHECKPOINT-BUDGET`

- `traces_to`: SC-BUDGET-01, SC-BUDGET-02
- `blocked_by`: SLICE-BUDGET-GREEN
- targeted、full、shell wiring／syntax、`py_compile`、allowlist與
  `git diff --check`全數驗證。

Frontier：`SLICE-BUDGET-RED`。

## Boundary

- 不重做本次已接受的queue-first、topic supply或exact-regime邏輯。
- 不操作live worker、LaunchAgent、retry circuit、promotion、production ranking
  或model。
- 本卡為非阻塞 P2 backlog；不得回溯否定
  `FOG-CONTINUOUS-TOPIC-SUPPLY-01` 的 mainline runtime acceptance。

## Exact changed-file allowlist

- 本卡狀態欄位
- `scripts/run_autonomous_research.py`
- `scripts/verify_daily_research_quota.py`
- `scripts/run_fog_research_worker.sh`
- `tests/test_fog_continuous_topic_supply.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_runtime_time_wiring.sh`
- `docs/evidence/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/**`
- `.work/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/**`

需要allowlist外檔案時停止並回報，不得自行擴張。

## Forbidden

- 修改ranking/model/weights、promotion或sealed/closed registry。
- 修改attempt budget大小、topic ranking eligibility或queue-first ownership。
- 將budget-incomplete標成真正耗盡、runtime failure或circuit failure。
- live Fog `--execute`、LaunchAgent load/bootstrap/kickstart、清除或旋轉
  retry circuit。
- merge／push `main`、cleanup任何thread／branch／worktree。

## Phase 0 RED

Production code修改前，先保存可重現RED：

1. main收到budget receipt卻輸出`NO_EXECUTABLE_TOPIC`。
2. verifier將budget decision輸出`PARTIAL_NO_MORE_WORK`或no-more-work value。
3. worker observable predicate會因上述狀態停止。

Evidence：

`docs/evidence/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/verification.md`

## Acceptance

- budget-incomplete不映射為`NO_EXECUTABLE_TOPIC`。
- verifier輸出穩定retryable status/research value、exit 0；worker不宣稱
  no-more-work且可繼續下一個bounded batch。
- true `TOPIC_SUPPLY_EXHAUSTED`仍保持terminal、exit 0、no retry。
- affected targeted tests與原continuous supply suites通過。
- full `pytest`、shell runtime wiring／syntax、`py_compile`、
  exact allowlist、DBG audit與`git diff --check`通過。

## Candidate exit

只交付：

- exact base／candidate SHA
- FR／SC → RED → GREEN對照
- changed files與allowlist audit
- targeted／full驗證結果
- remaining risks
- `READY_FOR_INDEPENDENT_REVIEW`

不得自審、整合、deploy或操作live runtime。
