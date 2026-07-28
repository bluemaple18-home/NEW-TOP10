---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-VERIFICATION
status: READY_FOR_INDEPENDENT_REVIEW
base_sha: 33aee4d
stacked_parent_sha: 5e6c0385fc8d93a89561583c79981d273c44fde6
dispatch_sha: d565fdd932576505ee9612954e5c4f8c52c24d7d
implementation_candidate_sha: 3969aba5c62171ef52d5c54856f0c0821b750627
---

# Verification

## Phase 0 RED receipt

Deterministic fixture 在 repo-owned synthetic root 建立 candidate 與 baseline ranking
inventory；兩邊都有 `ranking_*.csv`，但日期皆與 closed-regime canonical dates
零交集。測試不啟動 live worker、不讀寫既有 queue／manager history。

Command：

```text
uv run pytest -q tests/test_regime_research_autonomy.py::test_zero_exact_date_topic_is_ineligible_across_selection_paths
```

Result：`1 failed`

Observed：

```text
eligible=True
reason_code=ELIGIBLE
index=[strategy-matrix:artifacts-backtest-candidate]
fallback=[strategy-matrix:artifacts-backtest-candidate]
queue=[strategy-matrix:artifacts-backtest-candidate]
```

Expected：

```text
eligible=False
reason_code=NO_EXACT_REGIME_RANKING_DATE
index=[]
fallback=[]
queue=[]
```

這證明上游只以 ranking file count 與 regime identity/coverage 判斷 eligibility；
一旦誤標為 eligible，index、fallback、queue 三條 selection path 都會選回該
topic。

## Protected state preflight

- Branch：`codex/fog-exact-regime-topic-eligibility-handoff-20260728`
- HEAD：`d565fdd932576505ee9612954e5c4f8c52c24d7d`
- `5e6c0385fc8d93a89561583c79981d273c44fde6`：確認為 HEAD ancestor
- LaunchAgent：`launchctl list com.new-top10.fog-research-worker` 找不到 service，
  維持 unloaded
- Retry state：`attempts=3`、`circuit_open=1`
- Retry state SHA-256：
  `acfbfbc43bc02af51e5fb6b1d3e285616bf2fcf846e41ceda8ee3b79cd74096c`
- Retry context SHA-256：
  `528d5cca4482f0e9ccb9e6d2374e856ca57557ebd69df3deb87c858a787f3255`
- Installed plist SHA-256：
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`

## Green gates

### Implementation

- 以 `statistical_lineage_authority` 與各 validation profile horizons重建
  canonical development episode dates。
- Candidate與 baseline皆由 repo-owned `ranking_YYYY-MM-DD.csv` 建立
  deterministic inventory。
- 任一 inventory沒有 exact-date交集時，topic回
  `eligible=False`／`NO_EXACT_REGIME_RANKING_DATE`。
- Path escape、malformed date、future-only與缺 canonical authority皆 fail
  closed。
- `select_topics_for_run`先排除 ineligible topics；index、fallback、queue不會
  重新選回。
- `scripts/run_backtest_strategy_matrix.py`未修改，保留第二道 exact-regime
  fail-closed guard。

### Commands

Focused Phase 0 GREEN：

```text
uv run pytest -q tests/test_regime_research_autonomy.py::test_zero_exact_date_topic_is_ineligible_across_selection_paths
1 passed in 1.88s
```

Affected targeted：

```text
uv run pytest -q tests/test_regime_research_autonomy.py tests/test_autonomous_research_topic_bank.py tests/test_fog_daily_source_lineage.py tests/test_fog_closed_regime_runtime.py
86 passed in 2.79s
```

Full suite：

```text
uv run pytest -q
585 passed, 4 warnings, 246 subtests passed in 63.26s
```

Static gates：

```text
.venv/bin/python -m py_compile scripts/run_autonomous_research.py tests/test_regime_research_autonomy.py
PASS

git diff --check
PASS
```

Exact allowlist audit：

```text
scripts/run_autonomous_research.py
tests/test_regime_research_autonomy.py
docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/verification.md
docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md
.work/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/status.md
```

Protected runtime recheck：

- LaunchAgent仍找不到 service，維持 unloaded。
- Retry state仍為 `attempts=3`、`circuit_open=1`。
- Retry state/context/installed plist SHA-256與 preflight完全一致。
- 沒有 live `--execute` Fog run、第四次 probe、LaunchAgent load/kickstart或
  circuit recovery。

## Remaining risk

- 依任務邊界未執行 live scheduler acceptance；實際 I5恢復只能在獨立 Review
  GO並整合後另行決定。
- 尚未經獨立 Reviewer檢查完整 `33aee4d..candidate` stacked範圍。
- Executor不宣告 Review GO；狀態只到 `READY_FOR_INDEPENDENT_REVIEW`。
