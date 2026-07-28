---
id: REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01
chain_id: FOG-I5-EXACT-REGIME-ELIGIBILITY
status: RUNNING
type: review
ownership: independent-reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: xhigh
model_reason: scheduler eligibility、canonical exact-regime date authority、candidate/baseline path boundary與 stacked source-lineage皆屬 production safety contract；正式 thread繼承使用者設定的 gpt-5.6-sol xhigh，不降級。
base_sha: 33aee4d
candidate_sha: 684d3adf3916100a7eb9bb57c6164f3b67a58064
implementation_sha: 3969aba5c62171ef52d5c54856f0c0821b750627
reviewer_thread_id: 019fa76b-e568-7653-ade0-a399a3a1aa4a
---

# REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01

## Role

你是獨立 Reviewer，不是 Executor、Repairer或 mainline Integrator。

- 只審查固定範圍與重建證據。
- 不得修改 candidate code、自行 repair、merge、push、deploy或操作 live runtime。
- 只有 P0／P1 finding可回 `REVIEW_NO_GO`；P2／P3列入 residual risk，不得
  移動球門。

## Fixed review boundary

```text
33aee4d..
684d3adf3916100a7eb9bb57c6164f3b67a58064
```

Candidate branch：
`codex/fog-exact-regime-topic-eligibility-handoff-20260728`

Reviewer必須從 fixed candidate commit建立獨立 clean worktree，不信任
Executor stored PASS。

## Must read

1. `AGENTS.md`
2. `docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md`
3. `docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/verification.md`
4. `.work/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/status.md`
5. `scripts/run_autonomous_research.py`
6. `scripts/run_backtest_strategy_matrix.py`
7. `tests/test_regime_research_autonomy.py`
8. `tests/test_fog_daily_source_lineage.py`

## Spec axis

逐項確認：

1. Closed-regime topic在 matrix執行前，candidate與 baseline都必須各自具有
   canonical exact-regime allowed date交集。
2. Allowed dates必須由 repo authority重建，並與 matrix使用的 development
   episode split/profile horizons語意一致；不得以 run date、檔名暗示或全部
   exact-regime日期近似。
3. Zero exact-date topic必須 `eligible=False`，使用穩定 reason code，且
   index、fallback、queue皆不可選回。
4. Legal exact-date topic仍可選；legacy non-closed mode不可被誤擋。
5. Malformed/impossible date、future-only、path/symlink escape、缺 canonical
   authority、transition與 `UNKNOWN`皆 fail closed。
6. `NO_EXECUTABLE_TOPIC`仍是合法 no-work round，且保留
   `fog-daily-source-lineage.v1`。
7. `scripts/run_backtest_strategy_matrix.py` exact-regime guard未放寬；不得把
   matrix failure或 `NO_COMPARISON_EVIDENCE`改寫為成功。
8. Production model、ranking、weights、baseline、promotion、manager history、
   LaunchAgent、retry circuit與 live artifacts未被修改。

## Standards axis

分開審查：

- correctness：authority/date intersection、candidate/baseline角色與錯誤優先序
- regression：legacy topic generation、topic JSON/bank、index/fallback/queue
- security：repo containment、symlink/path traversal、authority confusion
- performance：每 profile/inventory掃描是否有不必要無界 I/O
- maintainability：reason code與既有 authority/helper邊界
- testing：測試是否打到 observable scheduler behavior而非只測 private shape

Finding必須包含固定 ID、`severity`、`category`、`path:line`、觸發條件、
evidence、risk、suggested fix、validation gap與 confidence。

## Required hostile probes

至少重建：

- candidate legal、baseline zero-intersection；
- baseline legal、candidate zero-intersection；
- both legal control；
- malformed與 impossible ISO date；
- future-only ranking inventory；
- absolute path escape與 symlink escape；
- missing canonical authority；
- current regime為 transition／`UNKNOWN`；
- index／fallback／queue不會重新選回 ineligible topic；
- `NO_EXECUTABLE_TOPIC`仍保留 daily source lineage；
- protected matrix guard在 candidate diff中為零。

## Verification

至少執行：

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
.venv/bin/python -m pytest -q
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check 33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064
git diff --quiet 33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064 \
  -- scripts/run_backtest_strategy_matrix.py
```

## Exact output allowlist

- 本卡的 review receipt／狀態欄位
- `docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review.md`
- `.work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/**`

Reviewer只提交單一原子 review commit；candidate code、implementation evidence與
runtime state必須維持不變。

## Output contract

`review.md`至少包含：

- `verdict: REVIEW_GO | REVIEW_NO_GO`
- `reviewed_commit: 684d3adf3916100a7eb9bb57c6164f3b67a58064`
- `base_commit: 33aee4d`
- Spec axis與Standards axis分離結論
- P0–P3 findings
- hostile probes與命令/exit codes
- 未驗證項目與剩餘風險

若無 P0／P1：

```text
REVIEW_GO
```

若有可重現 P0／P1：

```text
REVIEW_NO_GO
```

回報後停止；不得自行建立 Repair或整合。
