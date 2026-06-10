# REVIEW-AUTONOMOUS-RESEARCH-MANAGER

## 任務卡

任務ID：`REVIEW-AUTONOMOUS-RESEARCH-MANAGER`
卡片類型｜派工對象：Code Review / Research Automation Governance｜Reviewer
請讀：`docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md`、`scripts/run_autonomous_research.py`、`scripts/verify_autonomous_research.py`、`scripts/run_backtest_strategy_matrix.py`
任務目的：review autonomous research manager 是否能自己發題、管理佇列、多題執行安全回測、更新管理層狀態，同時不抓新資料、不訓練模型、不覆蓋 `models/latest_lgbm.pkl`、不修改正式 ranking、不中途產生 promotion 授權。
證據路徑：`artifacts/autonomous_research/autonomous_research_2026-06-10.json`、`artifacts/autonomous_research/autonomous_research_execute_smoke_2026-06-10.json`、`artifacts/autonomous_research/autonomous_research_queue_smoke_2026-06-10.json`、`artifacts/autonomous_research/manager_summary.json`、`artifacts/autonomous_research/topic_registry.json`、`artifacts/autonomous_research/run_history.json`、`artifacts/autonomous_research/next_action_queue.json`、`artifacts/autonomous_research/runner_registry.json`

## Scope

本次 review 只看 autonomous research manager 這條線：

- 新增 `scripts/run_autonomous_research.py`
- 新增 `scripts/verify_autonomous_research.py`
- 新增 `docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md`
- 修改 `scripts/run_backtest_strategy_matrix.py` 補齊 `run_portfolio_replay` namespace 相容欄位

不 review 其他 research scripts、模型訓練候選、daily publish、UI、外部 reviewer 收集器或正式 ranking overlay。

## Review 重點

- 總入口是否真的能自行產題，而不是只跑手動指定題目。
- `--from-queue --execute-topic-count N` 是否能多題執行，且每題都有 `topic_runs` / steps / outputs / outcome。
- 管理層是否正確更新：
  - `topic_registry.json`
  - `run_history.json`
  - `next_action_queue.json`
  - `manager_summary.json`
  - `runner_registry.json`
- 冷卻邏輯是否避免同一 topic 被無限重跑；`--rerun` 是否才允許重跑。
- `rejected` topic 是否預設不回佇列；`--include-rejected` 是否才允許重跑。
- runner allowlist 是否只能執行：
  - `scripts/run_backtest_strategy_matrix.py`
  - `scripts/compare_strategy_matrices.py`
- 任何輸出都不得包含或暗示：
  - `PROMOTION_READY`
  - `AUTO_PROMOTE`
  - `MODEL_APPROVED`
  - `production_promotion_allowed=true`
- `scripts/run_backtest_strategy_matrix.py` 的 namespace 相容修正是否只補 replay args，不改策略矩陣語意。

## 已跑證據

```bash
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  scripts/verify_autonomous_research.py \
  scripts/run_backtest_strategy_matrix.py

.venv/bin/python scripts/verify_autonomous_research.py
.venv/bin/python scripts/verify_backtest_strategy_matrix.py

.venv/bin/python scripts/run_autonomous_research.py \
  --date 2026-06-10 \
  --output artifacts/autonomous_research/autonomous_research_2026-06-10.json

.venv/bin/python scripts/run_autonomous_research.py \
  --date 2026-06-10 \
  --execute \
  --max-ranking-files 3 \
  --output artifacts/autonomous_research/autonomous_research_execute_smoke_2026-06-10.json

.venv/bin/python scripts/run_autonomous_research.py \
  --date 2026-06-10 \
  --execute \
  --from-queue \
  --execute-topic-count 2 \
  --max-ranking-files 2 \
  --output artifacts/autonomous_research/autonomous_research_queue_smoke_2026-06-10.json

git diff --check
```

目前觀察到的管理層狀態：

```text
topic_count: 12
run_count: 3
status_counts:
  partial_needs_followup: 1
  rejected: 2
  candidate: 9
next_action_count: 10
latest_run: autonomous_research_queue_smoke_2026-06-10
promotion_allowed: false
```

## 必查風險

- 多題執行時，只要其中一題失敗，run status 是否會正確 FAILED。
- `run_history.json` 是否會把 dry-run 與 execute 混淆成同等證據。
- `topic_registry.json` 是否可能用同一 `topic_id` 覆蓋不同 ranking 目錄。
- 冷卻規則是否會跳過應該 follow-up 的 partial topic，導致 queue 看似有下一步但不會被跑。
- `runner_registry.json` 是否足夠作為新增 runner 的審查入口。
- artifacts 若未納入 git，review 是否仍能用重新執行指令復現證據。

## 建議驗證

```bash
.venv/bin/python scripts/verify_autonomous_research.py
.venv/bin/python scripts/verify_backtest_strategy_matrix.py

.venv/bin/python scripts/run_autonomous_research.py \
  --date 2026-06-10 \
  --execute \
  --from-queue \
  --execute-topic-count 2 \
  --max-ranking-files 2 \
  --rerun \
  --output artifacts/autonomous_research/review_queue_rerun_2026-06-10.json

git diff --check -- \
  scripts/run_autonomous_research.py \
  scripts/verify_autonomous_research.py \
  scripts/run_backtest_strategy_matrix.py \
  docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md \
  docs/tasks/2026-06-10_REVIEW-AUTONOMOUS-RESEARCH-MANAGER.md
```

## 預期結論格式

- Findings：依 P0/P1/P2/P3 排序；若無阻塞，明確寫「未發現阻塞問題」。
- Testing Gaps：只列會影響 autonomous research manager / runner allowlist / promotion boundary 的缺口。
- Merge Recommendation：`approve` / `approve_with_followups` / `block`。

## Review 結論

日期：2026-06-10
狀態：`APPROVED`
Merge Recommendation：`approve`

Reviewer 回報未發現阻塞問題。上一輪兩個 finding 已收斂：

- `--from-queue` 現在讀 `artifacts/autonomous_research/next_action_queue.json`，依 queue order 選題；缺 queue 時不 fallback 到 generated topics。
- `partial_needs_followup` 且 `run_count > 0` 的 topic 預設會被 cooldown 跳過；只有加 `--rerun` 才會從 queue head 開始。

Reviewer 重跑驗證：

```text
py_compile：OK
scripts/verify_autonomous_research.py：OK
scripts/verify_backtest_strategy_matrix.py：OK
scoped git diff --check：OK
production / promotion / model 寫入字串掃描：未看到誤升級入口
read-only queue probe：不帶 --rerun 選 queue 第 2、3 筆；帶 --rerun 選 queue head、第 2 筆，符合預期
untracked 檔 trailing whitespace 掃描：OK
```

本地核對：

- `scripts/run_autonomous_research.py` 已有 atomic write helper，run artifact 先寫入，再更新 manager，最後補寫含 manager summary 的 final artifact。
- `scripts/verify_autonomous_research.py` 已覆蓋 queue order、cooldown、`--rerun` 與缺 queue 不 fallback。
- 仍未 `git add` / commit / push；本 review scope 的新增 scripts/docs 仍維持 untracked 狀態。
