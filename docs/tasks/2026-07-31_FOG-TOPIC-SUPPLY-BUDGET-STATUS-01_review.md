---
id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01-REVIEW
status: REVIEW_GO
type: review
ownership: reviewer
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
chain_id: FOG-TOPIC-SUPPLY-BUDGET-STATUS
parent_card_id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01
base_sha: 85ca3efb403519925d28afc8d94ed43f5111b2b3
candidate_sha: 6af35c839f85040ba24648b226949dc31e584e6c
---

# FOG-TOPIC-SUPPLY-BUDGET-STATUS-01 Independent Review

## Role

你是獨立 Reviewer，不是 Executor、Repairer 或 mainline Integrator。

- 固定審查 candidate
  `6af35c839f85040ba24648b226949dc31e584e6c`。
- 不修改 production code、tests 或原實作 evidence。
- 只可新增本 Review receipt：
  `.work/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/review/**`。
- 不 merge、不 push、不 deploy，不操作 live worker、LaunchAgent 或 circuit。

## Review question

candidate 是否以最小且完整的 main → quota verifier → Fog worker 契約，
把 `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED` 保留成 exit 0、可重試、
非 no-more-work 的狀態，同時維持 true `TOPIC_SUPPLY_EXHAUSTED` 與一般
`NO_EXECUTABLE_TOPIC` 的 terminal 語意？

## Fixed diff

```text
base      85ca3efb403519925d28afc8d94ed43f5111b2b3
candidate 6af35c839f85040ba24648b226949dc31e584e6c
```

只審：

- `scripts/run_autonomous_research.py`
- `scripts/verify_daily_research_quota.py`
- `scripts/run_fog_research_worker.sh`
- `tests/test_fog_continuous_topic_supply.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_runtime_time_wiring.sh`
- 原卡狀態與
  `docs/evidence/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/verification.md`

## Required checks

1. preflight固定 HEAD、clean worktree、candidate changed-file allowlist。
2. source decision前查 CodeGraph context／explore，再讀 fixed diff。
3. 獨立確認：
   - main無topic時保留完整 attempt-budget receipt與decision；
   - verifier state／research value穩定、非no-more-work，CLI exit為0；
   - worker遇該state可進下一bounded batch，不會進terminal／failure circuit；
   - true exhaustion與一般no-executable仍維持原terminal／exit 0。
4. 重跑：
   - 新增regressions與既有affected suites；
   - shell wiring與syntax；
   - `py_compile`；
   - full `pytest`；
   - `git diff --check`、DBG與allowlist audit。
5. Executor回報full suite為`618 passed, 1 failed`，唯一failure為
   `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
   的historical artifact/reference `evidence_exists`缺漏。Reviewer必須獨立
   判斷它是candidate regression、環境缺件或既有問題，不得直接照抄結論。

## Severity and verdict

- 只有未解 `P0`／`P1` 可輸出 `REVIEW_NO_GO`。
- `P2`／`P3` 必須記入 backlog，但不得阻擋本P2維護卡。
- 無未解 `P0`／`P1` 時輸出 `REVIEW_GO`。
- finding格式：ID、severity、file/line、reproduction、impact、required fix。

## Exit

將可重現receipt寫入：

`.work/FOG-TOPIC-SUPPLY-BUDGET-STATUS-01/review/review_receipt.md`

最後只回報：

- fixed base／candidate SHA
- changed-file audit
- checks與結果
- findings（含P2／P3 backlog）
- `REVIEW_GO` 或 `REVIEW_NO_GO`
