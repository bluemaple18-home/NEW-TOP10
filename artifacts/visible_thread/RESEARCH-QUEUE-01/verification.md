---
id: RESEARCH-QUEUE-01-verification
status: DELIVERED_CANDIDATE
type: evidence
---

# RESEARCH-QUEUE-01 Verification

## Facts

- Worktree 與 main cwd 不同，起始 Git worktree 與 index 乾淨。
- Git metadata 可讀，起始 HEAD 為 `2ca23b2d6157e3336ae69babe81cb0cefb6800bd`，無 `index.lock`。
- `confirmed_for_next_replay` 政策：總執行上限 2 次、冷卻 24 小時。
- `partial_needs_followup` 政策：總執行上限 3 次、冷卻 24 小時。
- 已執行題目缺少可驗證的最後執行時間時 fail closed。
- `rejected`、冷卻未滿、超限及其他不支援的已執行狀態不可重跑；legacy `--rerun` / `--include-rejected` 不可繞過。
- research-only、allowlisted runner 與 production promotion 禁止契約保留。

## Verification

- `uv run python -m unittest tests.test_autonomous_research_topic_bank tests.test_daily_research_quota_verifier tests.test_pm_research_harness_loop`
  - 結果：17 tests passed。
- bounded Python fixture
  - 結果：`confirmed_ready=true`、`partial_ready=true`；cooling、exhausted、rejected 皆為 `false`。
  - 詳細結果：`artifacts/visible_thread/RESEARCH-QUEUE-01/bounded_fixture.json`。
- `bash -n scripts/run_fog_research_worker.sh`
  - 結果：passed。
- `git diff --check`
  - 結果：passed。

## Acceptance mapping

- Queue 內已有 run history 的 follow-up / replay 題目：由狀態別上限與冷卻決定，不再被 `run_count > 0` 全面排除。
- 空 queue：selection 回傳空集合，不執行 topic；回歸測試覆蓋。
- 禁止全域無條件重跑：legacy flags 不參與受控 eligibility 放行。
- Queue owner 與 worker lock：未修改。
- Production promotion：仍為 `false`，未修改 ranking、模型或 promotion。

## Remaining risk

- 舊 registry 沒有 `last_run_at` 時依 manager `run_history.json` 回填判斷；若兩者都缺失，會安全停止該題，需由主線確認此 fail-closed 行為符合營運預期。
- 未執行真實 strategy matrix 長跑；本卡只做 bounded fixture 與受影響回歸，避免改寫既有研究 artifacts。

## Status boundary

僅為 `DELIVERED_CANDIDATE`；未宣稱 `ACCEPTED`、`INTEGRATED` 或 `CLOSED`。
