---
id: REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-EVIDENCE
verdict: REVIEW_NO_GO
reviewed_commit: 684d3adf3916100a7eb9bb57c6164f3b67a58064
base_commit: 33aee4d
candidate_implementation_commit: 3969aba5c62171ef52d5c54856f0c0821b750627
dispatcher_card_commit: bca6e75c9c576fe6e3e128381fa4b626e0312518
dispatch_receipt_commit: 2d29a8d
---

# Strict independent review

## Verdict

`REVIEW_NO_GO`

固定邊界 `33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064`
有一個可重現 P1 finding。Coordinator commits只用來讀卡片／receipt，未納入
reviewed boundary。

## Preflight

- Reviewer cwd：
  `<repo-root>` 的獨立 Codex worktree，與`<main-checkout>`不同。
- Initial HEAD：
  `684d3adf3916100a7eb9bb57c6164f3b67a58064`。
- Initial worktree：clean。
- `worktree_capability_preflight.sh --check`：exit 0；
  `worktree_registered=true`、`python_tests=needs_prepare`、
  `codegraph=degraded:fallback_rg`。
- `uv sync`建立 worktree-local `.venv`；未改 lockfile。

## Spec axis

1. **Candidate/baseline exact-date intersection：部分不符合。**
   一般 regular-file案例正確區分 candidate/baseline角色；但 repo內的
   ranking symlink file可指向 repo外並被當成合法交集，見
   `FOG-EXACT-REGIME-REVIEW-P1-001`。
2. **Canonical allowed dates：符合。**
   Reviewer以相同 history、contract與 `3,5,10` horizons重建，scheduler
   allowed dates與 matrix development split皆為60日且集合相同。
3. **Zero exact-date selection：符合。**
   `eligible=False`／`NO_EXACT_REGIME_RANKING_DATE`；index、fallback、queue
   均為空。
4. **Legal與legacy control：符合。**
   Candidate/baseline均有合法exact date時可選；non-closed topic仍為
   `LEGACY_TOPIC`且eligible。
5. **Hostile dates／authority／paths：不符合。**
   malformed、impossible、future-only、absolute directory escape、
   symlink directory escape、missing authority、transition與`UNKNOWN`
   均fail closed；但 file-level symlink escape未fail closed。
6. **No-work round lineage：符合。**
   `NO_EXECUTABLE_TOPIC`保留`fog-daily-source-lineage.v1`。
7. **Protected matrix與failure semantics：符合已審邊界。**
   `scripts/run_backtest_strategy_matrix.py` candidate diff為零；
   `NO_COMPARISON_EVIDENCE`／matrix failure邏輯未被本candidate改寫。
8. **Protected production/runtime state：符合repo diff邊界。**
   Diff未修改 production model、ranking、weights、baseline、promotion、
   LaunchAgent、retry circuit或live artifacts。

## Standards axis

- **Correctness：** candidate/baseline角色、reason code、selection與profile
  split語意通過 regular-file probes；file-level symlink authority有P1缺口。
- **Regression：** affected targeted suite `86 passed`；legacy non-closed、
  topic selection與daily lineage control通過。
- **Security：** `REVIEW_NO_GO`。directory containment只驗證inventory目錄，
  未驗證每一個matched ranking entry。
- **Performance：** 未做large-inventory benchmark；目前每個topic/profile會
  重掃candidate與baseline inventory，列為remaining risk，非阻擋finding。
- **Maintainability：** reason code與現有authority/helper邊界清楚；未發現
  另一個阻擋問題。
- **Testing：** candidate測試覆蓋absolute directory escape，未覆蓋
  file-level symlink；reviewer hostile probe已補出可重現失敗。

## Findings

### FOG-EXACT-REGIME-REVIEW-P1-001 — repo內symlink ranking file可繞過containment

- severity：`P1`
- category：`security`
- path:line：`scripts/run_autonomous_research.py:1527`
- trigger：candidate或baseline directory位於repo內，但
  `ranking_YYYY-MM-DD.csv`本身是指向repo外regular file的symlink。
- evidence：eligibility回
  `eligible=true`／`reason_code=ELIGIBLE`；protected matrix選中該symlink，
  ranking reader實際讀得外部fixture的`stock_id=9999`。
- risk：closed-regime scheduler會把repo外ranking資料視為repo-owned
  canonical inventory並執行matrix，違反symlink escape fail-closed與source
  authority契約。
- suggested fix：inventory逐檔拒絕symlink、非regular file、
  `resolve(strict=True)`後repo外target與解析錯誤，回穩定
  `RANKING_INVENTORY_PATH_ESCAPE`；candidate與baseline都補observable
  regression。
- validation gap：既有測試只驗證整個candidate directory位於repo外。
- confidence：`high`
- status：`open`

P0：無。P2：無。P3：無。

## Hostile probes

Command：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
```

Result：exit 1；16 probes中15通過，僅`symlink_file_escape`失敗。

通過案例：

- candidate legal／baseline zero-intersection；
- baseline legal／candidate zero-intersection；
- both legal control；
- malformed與impossible ISO date；
- future-only inventory；
- absolute path escape與symlink directory escape；
- missing canonical authority；
- current transition／`UNKNOWN`；
- index／fallback／queue排除ineligible topic；
- `NO_EXECUTABLE_TOPIC`保留daily source lineage；
- legacy non-closed mode；
- scheduler allowed dates等於matrix development split。

失敗案例：

- repo內ranking file symlink指向repo外：eligibility仍為`ELIGIBLE`，
  matrix選中symlink並讀到外部內容。

Protected matrix：

```text
git diff --quiet 33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064 \
  -- scripts/run_backtest_strategy_matrix.py
```

Result：exit 0。

## Verification commands

Affected targeted：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
```

Result：exit 0，`86 passed in 1.63s`。

Full suite：

```text
.venv/bin/python -m pytest -q
```

Result：exit 1，`1 failed, 584 passed, 4 warnings, 246 subtests passed`。
唯一失敗為
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`；
其reason是隔離worktree缺少未追蹤／ignored evidence與data artifacts。
該test、builder與verifier在review boundary的diff為零；抽查缺少的paths在
base亦非tracked files，因此不歸因於candidate，但完整綠燈未能在此隔離
worktree重建。

Static／diff gates：

```text
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check 33aee4d..684d3adf3916100a7eb9bb57c6164f3b67a58064
```

Result：exit 0。

## Remaining risks / unverified

- Full suite因isolated worktree缺少ignored fixture artifacts而非全綠；candidate
  affected targeted suite已全綠，但mainline含完整runtime data的full suite仍需
  重跑。
- 未執行live Fog、第四次live probe、LaunchAgent、retry circuit、deploy、
  merge或production acceptance，符合review邊界。
- 未做large ranking inventory效能benchmark。
- File-level symlink TOCTOU與matrix reader的defense-in-depth仍待Repair範圍決定；
  Reviewer未修改candidate或建立Repair。
