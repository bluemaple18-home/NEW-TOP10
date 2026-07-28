---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1-EVIDENCE
status: READY_FOR_REVIEW
finding_id: FOG-EXACT-REGIME-REVIEW-P1-001
repair_source_sha: e50022a9db130832d9855846d12168a79d454cef
reviewed_candidate_sha: 684d3adf3916100a7eb9bb57c6164f3b67a58064
---

# Repair-1 evidence

## Scope

- 只修正 file-level ranking symlink authority。
- Coordinator commit `292f2f6`只用來讀取最新卡片與 dispatch receipt，未納入
  Repair candidate history。
- 未修改 reviewer hostile probe、protected matrix、production/runtime state。

## Preflight

- Initial HEAD：
  `e50022a9db130832d9855846d12168a79d454cef`。
- Initial worktree：clean。
- cwd：獨立 worktree，不是 main checkout。
- `worktree_capability_preflight.sh --check`：exit 0；
  `worktree_registered=true`、`python_tests=needs_prepare`、
  `codegraph=degraded:fallback_rg`。
- `uv sync`完成 worktree-local `.venv`，未修改 tracked dependency files。

## Phase 0 RED

原 reviewer hostile probe：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
```

Result：exit 1；16 probes中15通過，唯一失敗為
`symlink_file_escape`。Observed eligibility仍為
`eligible=true`／`reason_code=ELIGIBLE`，matrix選中 symlink並讀到 repo外
fixture的`stock_id=9999`。

新增 candidate／baseline observable regression後、production edit前：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py -k external_file_symlink
```

Result：exit 1；`2 failed, 61 deselected`。Candidate與 baseline兩個角色都實際
回`eligible=true`，因此在`assert result["eligible"] is False`失敗。

## Repair

`repo_owned_ranking_date_inventory`現在逐一驗證每個 matched ranking entry：

- entry本身為 symlink或不是 regular file時，整個 inventory fail closed；
- entry必須可`resolve(strict=True)`；
- resolved target必須位於`PROJECT_ROOT`內；
- 任一失敗回穩定`RANKING_INVENTORY_PATH_ESCAPE`。

## GREEN

Candidate／baseline regression：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py -k external_file_symlink
```

Result：exit 0；`2 passed, 61 deselected`。兩個角色皆 assert
`eligible=false`、`reason_code=RANKING_INVENTORY_PATH_ESCAPE`，且
`inventory_role`精確對應 candidate或 baseline。

原 reviewer hostile probe：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
```

Result：exit 0；16/16通過、`failed_probes=[]`。`symlink_file_escape`的
eligibility observable payload為：

```text
eligible=false
reason_code=RANKING_INVENTORY_PATH_ESCAPE
inventory_role=candidate
```

## Required verification

Targeted suite：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
```

Result：exit 0；`88 passed in 7.09s`。

Full suite：

```text
.venv/bin/python -m pytest -q
```

Result：exit 1；`1 failed, 586 passed, 4 warnings, 246 subtests passed in
67.07s`。唯一失敗：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

此為原 Review已記錄的 isolated-worktree ignored-artifact failure。Repair source
中的`review.md`記錄同一 test為唯一 failure。下列 repair-boundary diff gate為
exit 0：

```text
git diff --quiet e50022a9db130832d9855846d12168a79d454cef -- \
  tests/test_research_component_ledger.py \
  scripts/build_research_component_ledger.py \
  scripts/verify_research_component_ledger.py
```

獨立重建 ledger verifier的唯一 failed check為`evidence_exists`；缺少的是
`artifacts/model_experiments/*`、`artifacts/market_context_*`、
`data/clean/features.parquet`與`data/reference/*`等未隨隔離 worktree提供的
evidence/data artifacts。本 Repair未建立、修改或補入這些 protected artifacts。

Static gate：

```text
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
```

Result：exit 0。

## Diff and authority gates

- `git diff --check`：exit 0。
- Protected matrix：
  `git diff --quiet 684d3adf3916100a7eb9bb57c6164f3b67a58064 -- scripts/run_backtest_strategy_matrix.py`
  為 exit 0。
- Changed-file allowlist只有：
  `scripts/run_autonomous_research.py`、
  `tests/test_regime_research_autonomy.py`、
  `docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/evidence.md`。
- 因所有 changed files都在 Repair allowlist，protected
  production/runtime paths diff為零。

## Remaining risk / unverified

- Full suite未全綠；唯一 failure已如上歸因為 Review已知的 missing ignored
  artifacts，需由含完整runtime data的主線環境重跑。
- 未執行 live Fog、第四次 live probe、LaunchAgent、retry circuit、deploy、
  push、merge或 integration。
- 未執行 large inventory performance benchmark。
- File validation與後續 matrix read之間仍存在一般 filesystem TOCTOU風險；
  本 Repair依卡片邊界在 scheduler authority層 fail closed。
