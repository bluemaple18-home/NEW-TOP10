---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01
status: GO_LOCAL_DETERMINISTIC
type: repair
ownership: executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: production scheduler eligibility、exact-regime authority與bounded-retry安全邊界需要strict契約判斷
chain_id: FOG-I5-EXACT-REGIME-ELIGIBILITY
base_sha: 33aee4d
stacked_parent_sha: 5e6c0385fc8d93a89561583c79981d273c44fde6
integration_sha: 374792652b8bee8a869052228da78f7a0d4558b4
---

# FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01

## Role

你是本卡的 Executor，不是 Reviewer 或 mainline Integrator。

- 在獨立 worktree／branch 實作、驗證並產生 candidate commit。
- 不得自行宣告 Review GO、整合 `main` 或啟動 live Fog worker。
- candidate 完成後交回主線，另開獨立 Reviewer 檢查完整範圍
  `33aee4d..candidate`；這個範圍同時包含 source-lineage 與本卡修復。

## Mainline completion receipt

- Initial candidate：
  `684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Repair-1：
  `51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Independent re-review：`REVIEW_GO`
- Re-review commit：
  `0b1373bdea3d02b6a92c07a121f664949e4f48f2`
- Local integration：
  `374792652b8bee8a869052228da78f7a0d4558b4`
- Main checkout acceptance：hostile probes `16/16`與`7/7`、targeted
  `88 passed`、full suite `587 passed`。
- I5 live acceptance、push與 deploy均未執行。

## Goal

修正 closed-regime scheduler 的 topic eligibility：沒有任何
exact-match regime ranking 日期的 strategy-matrix topic，必須在執行 matrix
以前被標記為不可執行，不能再被 index、fallback 或 queue 選中。

## Root question

為什麼
`strategy-matrix:artifacts-backtest-production_baseline_harness_smoke:long_horizon`
在目前 exact regime 沒有可用 ranking 日期時仍被選中，直到
`run_backtest_strategy_matrix.py` 才以
`FileNotFoundError: ranking artifacts 沒有 exact-match regime 日期`
fail closed？

## Fixed starting state

- Main base：`33aee4d`
- Source-lineage implementation：`be9bb74`
- Source-lineage evidence refinement／stacked parent：
  `5e6c0385fc8d93a89561583c79981d273c44fde6`
- Source branch：`codex/fog-daily-source-lineage-01`
- Source-lineage targeted：`69 passed`
- Source-lineage full suite：
  `576 passed, 4 warnings, 246 subtests passed`
- Fog LaunchAgent：保持 **unloaded**
- Retry circuit：保持既有 `attempts=3`、`circuit_open=1`
- Live probe：已達三次停損；禁止第四次 live probe

## Current blocker evidence

- Source lineage 已正確產生：
  - `features_path=data/clean/features.parquet`
  - `features_sha256=057177ae3348c023ab2994ccc97a82a7228386b776e9ae65c35f2b22662d88af`
  - `daily_source_date=2026-07-27`
- 最新失敗 run（local runtime artifact）：
  `artifacts/autonomous_research/run_2026-07-28_115728`
- Matrix 的 exact-regime filter 正確 fail closed；candidate 與 comparison
  因 baseline matrix 失敗而跳過。
- Outcome：`NO_COMPARISON_EVIDENCE`
- Closed experiment state：`BLOCKED`
- Repo 內摘要：
  `docs/evidence/FOG-DAILY-SOURCE-LINEAGE-01/verification.md`

## Must read

1. `AGENTS.md`
2. `.work/current/status.md`
3. `.work/current/handoff.md`
4. `.work/current/context_manifest.md`
5. `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_I5_live_acceptance.md`
6. `docs/tasks/2026-07-28_FOG-DAILY-SOURCE-LINEAGE-01.md`
7. `docs/evidence/FOG-DAILY-SOURCE-LINEAGE-01/verification.md`
8. 本卡

## Preflight

開始修改前先回報：

- repo／worktree／branch
- `git status --short`
- `git rev-parse HEAD`
- 是否精確包含 stacked parent `5e6c038...`
- 預計修改檔案
- protected runtime／production state未被改動的證據

若 worktree 不乾淨、HEAD 不含 fixed parent、或 allowlist 衝突，立即停止。

## Phase 0 — RED first

先建立 deterministic hostile regression，不執行 live worker：

1. 建立一個 ranking inventory 有檔案、但目前 exact regime 的 allowed dates
   與 candidate／baseline ranking dates 交集為空的 topic。
2. 證明現況會把它保留為 eligible，且可能被 index、fallback 或 queue 選中。
3. 紅燈測試必須在 production edit 前失敗，並把命令與 failure 摘要寫入 evidence。

不得用 mock 直接把 topic 設成 `eligible=False` 來冒充重現。

## Implementation contract

- Eligibility 必須使用 repo-owned、deterministic 的 ranking date inventory 與
  canonical exact-regime allowed dates判斷交集。
- 沒有交集時：
  - `eligible=False`
  - 使用穩定 reason code
  - index、fallback、queue 三條 selection path都不得再選到該 topic
- 有至少一個合法 exact-match date的 topic仍可選。
- malformed date、path escape、future-only、transition／`UNKNOWN` 或缺少
  canonical regime authority時 fail closed。
- `run_backtest_strategy_matrix.py` 的 exact-regime filter仍是第二道防線；
  不得放寬或移除。
- `NO_EXECUTABLE_TOPIC` 仍是合法 no-work scheduler round，且必須保留
  `fog-daily-source-lineage.v1`。
- 不得把 `NO_COMPARISON_EVIDENCE`、matrix failure或 blocked experiment改寫為成功。

## Exact changed-file allowlist

- 本卡
- `scripts/run_autonomous_research.py`
- 可選新增：`scripts/fog_exact_regime_topic_eligibility.py`
- `tests/test_regime_research_autonomy.py`
- 可選新增：`tests/test_fog_exact_regime_topic_eligibility.py`
- `docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/**`
- `.work/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/**`

`scripts/run_backtest_strategy_matrix.py` 為 protected second-line guard。本卡不允許
修改；若證據顯示必須修改，先停手請主線修訂 allowlist。

## Do not touch

- production model、ranking、weights、baseline、promotion state
- queue policy與既有 manager history
- `artifacts/market_regime_history.json`
- installed LaunchAgent plist
- retry state／context／circuit
- live research artifacts
- `main`、任何 branch cleanup或 worktree cleanup

禁止執行：

- `launchctl load/bootstrap/kickstart`
- live `--execute` Fog run
- 刪除／旋轉 retry circuit
- 第四次 live probe
- merge／deploy／production acceptance

## Verification

至少需要：

- Phase 0 RED receipt
- focused eligibility tests：
  - zero exact-date topic不可選
  - legal exact-date topic仍可選
  - index／fallback／queue都不會重新帶回 ineligible topic
  - malformed／future-only／unknown authority fail closed
  - `NO_EXECUTABLE_TOPIC` 保留合法 source lineage
- source-lineage hostile regressions仍通過
- affected targeted suite
- full `pytest`
- `py_compile`
- `git diff --check`
- exact allowlist audit

所有命令、結果、base SHA、candidate SHA與剩餘風險寫入：
`docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/verification.md`

## Candidate exit

完成時只回報：

- candidate full SHA
- base／stacked parent
- changed files
- RED→GREEN證據
- targeted／full suite結果
- 未驗證項目與剩餘風險
- `READY_FOR_INDEPENDENT_REVIEW`

不得自行整合。主線將另開 strict independent Review；Review GO且整合後，
才可由 I5 acceptance線決定是否安全恢復 circuit並重新開始三輪 scheduler
acceptance。

## Executor result

- Phase 0 RED已證明 zero exact-date topic原本會維持 `ELIGIBLE`，並被
  index、fallback、queue選回。
- Candidate已改用 canonical development episode dates與 repo-owned
  candidate/baseline ranking inventory判斷 eligibility。
- Targeted：`86 passed`
- Full：`585 passed, 4 warnings, 246 subtests passed`
- Live acceptance未執行；LaunchAgent與 retry circuit保持原狀。
- Candidate SHA記錄於同卡 evidence；等待 strict independent Review。
