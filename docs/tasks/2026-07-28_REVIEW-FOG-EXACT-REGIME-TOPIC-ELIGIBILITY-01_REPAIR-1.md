---
id: REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1
chain_id: FOG-I5-EXACT-REGIME-ELIGIBILITY
status: REVIEW_GO
type: targeted_re_review
ownership: original_independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: xhigh
model_reason: 原 P1涉及 repo authority與 matrix外部資料讀取；必須由原 Reviewer identity在固定 Repair candidate上重建攻擊與回歸證據。
repair_source_sha: e50022a9db130832d9855846d12168a79d454cef
repair_candidate_sha: 51c084cd077cd4e997873e4a924f73e3dca2ba3d
original_candidate_sha: 684d3adf3916100a7eb9bb57c6164f3b67a58064
original_reviewer_thread_id: 019fa76b-e568-7653-ade0-a399a3a1aa4a
finding_id: FOG-EXACT-REGIME-REVIEW-P1-001
review_commit: 0b1373bdea3d02b6a92c07a121f664949e4f48f2
evidence_path: docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/
---

# REVIEW FOG exact-regime topic eligibility Repair-1

## 角色與固定邊界

你是原 independent Reviewer，不是 Repairer或 Integrator。

- Targeted Repair diff：
  `e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Combined behavior boundary：
  `33aee4d..51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Original finding：`FOG-EXACT-REGIME-REVIEW-P1-001`
- Original verdict：`REVIEW_NO_GO`

先確認現有 Reviewer worktree clean，再切到 Repair candidate detached HEAD；確認
HEAD精確、cwd仍為原獨立 Reviewer worktree，並重跑 capability preflight。

## Must read

1. `AGENTS.md`
2. 本卡
3. `docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review.md`
4. `docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/evidence.md`
5. `scripts/run_autonomous_research.py`
6. `tests/test_regime_research_autonomy.py`
7. Coordinator commit中的：
   - `.work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/review/review_plan.json`
   - `diff_entries.jsonl`
   - `finding_schema.json`

## Review plan

依 review-orchestrator full/strict計畫，分開檢查：

- correctness：逐檔驗證與 candidate/baseline role／reason precedence；
- regression：合法 regular-file、legacy、zero exact-date與selection行為；
- security：symlink、broken link、非regular entry、strict resolve與repo containment；
- test gap：新增測試是否打到 observable eligibility，不只測 private shape；
- maintainability／agents drift：只列實質問題，不擴大卡片邊界。

只有 P0／P1、production safety risk或可利用 security issue可阻擋；P2／P3列
residual risk。

## Required hostile probes

至少獨立重建：

1. candidate ranking file symlink指向 repo外 regular file；
2. baseline ranking file symlink指向 repo外 regular file；
3. broken file symlink與 matched non-regular entry；
4. 合法 candidate/baseline regular-file control；
5. 原 reviewer hostile probe全16案；
6. `eligible=False`、`RANKING_INVENTORY_PATH_ESCAPE`與
   `inventory_role=candidate|baseline` observable payload；
7. index／fallback／queue不選回 fail-closed topic；
8. protected matrix與原 Review evidence/probe在 Repair diff中為零。

若建立新 hostile probe，只能放在本 re-review `.work/.../review/**`內。

## Verification

至少執行：

```bash
cd <repo-root>
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
.venv/bin/python -m pytest -q
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d
git diff --quiet 684d3adf3916100a7eb9bb57c6164f3b67a58064..51c084cd077cd4e997873e4a924f73e3dca2ba3d \
  -- scripts/run_backtest_strategy_matrix.py
git diff --quiet e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d \
  -- docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01 \
     .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01
```

Full suite若只重現既有 isolated-worktree ledger missing ignored-artifact failure，
需再次確認相關 test／builder／verifier在 Repair diff為零；其他 failure不可豁免。

## Exact output allowlist

- `docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/review.md`
- `.work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/review/**`

只提交一個原子 re-review commit。禁止修改 candidate code、Repair evidence、
原 Review artifacts、protected matrix、production/runtime state。

## Verdict

若原 P1已關閉且無新 P0／P1：

```text
REVIEW_GO
```

否則：

```text
REVIEW_NO_GO
```

回報 verdict、reviewed Repair SHA、re-review commit完整 SHA、findings、commands、
remaining risks後停止；不得自行 Repair-2或整合。

## Re-review receipt

- Verdict：`REVIEW_GO`
- Reviewed Repair SHA：
  `51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Re-review commit：
  `0b1373bdea3d02b6a92c07a121f664949e4f48f2`
- Original finding：`resolved`
- New P0／P1：無
- Original hostile probes：`16/16`
- Repair-1 probes：`7/7`
- Targeted：`88 passed`
- Reviewer full suite：`586 passed, 1 failed`；唯一失敗為 isolated worktree
  missing ignored-artifact ledger case，Repair diff為零。
- Main checkout acceptance full suite：`587 passed`。
