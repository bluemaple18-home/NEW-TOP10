---
id: REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1-EVIDENCE
verdict: REVIEW_GO
reviewed_commit: 51c084cd077cd4e997873e4a924f73e3dca2ba3d
repair_source_commit: e50022a9db130832d9855846d12168a79d454cef
combined_base_commit: 33aee4d
finding_id: FOG-EXACT-REGIME-REVIEW-P1-001
finding_status: resolved
coordinator_card_commit: 813a829
---

# Repair-1 targeted re-review

## Verdict

`REVIEW_GO`

Targeted boundary：
`e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d`。

Combined behavior boundary：
`33aee4d..51c084cd077cd4e997873e4a924f73e3dca2ba3d`。

原`FOG-EXACT-REGIME-REVIEW-P1-001`已關閉；未發現新P0/P1。

## Preflight

- 切換前Reviewer HEAD精確為
  `e50022a9db130832d9855846d12168a79d454cef`，worktree clean、index lock absent。
- 安全切至detached
  `51c084cd077cd4e997873e4a924f73e3dca2ba3d`後，HEAD精確、worktree clean、
  index lock absent。
- cwd維持`<repo-root>`獨立Reviewer worktree，與`<main-checkout>`不同。
- Capability preflight：exit 0；
  `worktree_registered=true`、`python_tests=ready`、
  `codegraph=degraded:fallback_rg`。
- Repair candidate parent精確為
  `e50022a9db130832d9855846d12168a79d454cef`。

## Finding disposition

### FOG-EXACT-REGIME-REVIEW-P1-001 — resolved

Repair在`scripts/run_autonomous_research.py:1532`起逐一驗證matched ranking
entry：

- entry為symlink或非regular file時fail closed；
- `resolve(strict=True)`失敗時fail closed；
- resolved target不在`PROJECT_ROOT`時fail closed；
- reason維持`RANKING_INVENTORY_PATH_ESCAPE`，candidate/baseline role精確保留。

原攻擊已無法通過scheduler eligibility或selection，因此不再重報P1。

P0：無。P1：無。P2：無。P3：無。

## Spec axis

1. **Candidate symlink：符合。**
   外部file symlink、broken symlink、matched non-regular entry皆回
   `eligible=false`、`RANKING_INVENTORY_PATH_ESCAPE`、
   `inventory_role=candidate`。
2. **Baseline symlink：符合。**
   同三類 hostile entry皆fail closed且
   `inventory_role=baseline`。
3. **Selection paths：符合。**
   Fail-closed topic在index、fallback、queue皆為空。
4. **Legal control：符合。**
   Candidate與baseline均為repo內regular file時維持`ELIGIBLE`，三條selection
   path皆可選。
5. **Combined behavior：符合。**
   原Reviewer 16案全部通過，包含exact-date角色、malformed/impossible、
   future-only、directory path escape、UNKNOWN/transition、daily lineage與
   matrix development split。
6. **Protected boundaries：符合。**
   Protected matrix、原Review evidence與原hostile probe在Repair diff皆為零；
   production/runtime state未修改。

## Standards axis

- **Correctness：** reason precedence與candidate/baseline role在direct helper、
  topic observable payload及selection結果一致。
- **Regression：** 合法regular file、legacy/exact-date與既有selection測試保持
  通過。
- **Security：** 原repo authority escape已在scheduler matrix前fail closed。
- **Testing：** Candidate新增兩角色外部symlink regression；Reviewer另以獨立
  probe覆蓋broken symlink、non-regular與selection。
- **Maintainability：** 修補集中於既有inventory helper，未擴大matrix或runtime
  邊界。
- **Performance：** 每entry新增`is_file`與strict resolve；未見無界新迴圈，
  large-inventory benchmark仍未執行。

## Hostile probes

原Reviewer probe：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
```

Result：exit 0，`16/16`通過，`failed_probes=[]`。

Repair-1獨立probe：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/review/hostile_probes.py
```

Result：exit 0，`7/7`通過，`failed_probes=[]`。

獨立probe涵蓋：

- candidate／baseline外部file symlink；
- candidate／baseline broken file symlink；
- candidate／baseline matched non-regular directory entry；
- 合法candidate/baseline regular-file control；
- direct result、topic payload的reason／role；
- index／fallback／queue observable selection。

## Verification

Focused candidate tests：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py -k external_file_symlink
```

Result：exit 0，`2 passed, 61 deselected`。

Affected targeted suite：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
```

Result：exit 0，`88 passed in 2.04s`。

Full suite：

```text
.venv/bin/python -m pytest -q
```

Result：exit 1，`1 failed, 586 passed, 4 warnings, 246 subtests passed in
55.89s`。

唯一failure仍為
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
Reviewer獨立重建report，唯一failed check為`evidence_exists`；原因是隔離
worktree未提供ignored evidence/data artifacts。該test、builder與verifier在
Repair diff均為零，與原Review記錄相同，因此不列Repair candidate finding。

Static與boundary gates：

```text
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d
```

Result：exit 0。

```text
git diff --quiet \
  684d3adf3916100a7eb9bb57c6164f3b67a58064..51c084cd077cd4e997873e4a924f73e3dca2ba3d \
  -- scripts/run_backtest_strategy_matrix.py
git diff --quiet \
  e50022a9db130832d9855846d12168a79d454cef..51c084cd077cd4e997873e4a924f73e3dca2ba3d \
  -- docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01 \
     .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01
```

Result：兩者exit 0。

## Remaining risks / unverified

- Full suite仍受isolated-worktree missing ignored artifacts限制；需在含完整
  runtime data的mainline環境重跑。
- Protected matrix若被直接繞過scheduler呼叫，仍會跟隨ranking symlink；
  正常scheduler path已在matrix前阻擋。Eligibility validation與後續read之間
  仍有一般filesystem TOCTOU residual。
- 未執行large inventory performance benchmark。
- 未執行live Fog、第四次live probe、LaunchAgent、retry circuit、push、
  merge、deploy或integration。
