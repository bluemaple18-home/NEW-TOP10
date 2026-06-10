# Autonomous Research Manager

## 定位

`scripts/run_autonomous_research.py` 是研究總入口與管理層。它可以自己產生研究題目、選出可用既有 artifacts 回測的題目，並在 `--execute` 時跑白名單回測。

它不是模型升版 gate，不會訓練模型、不會覆蓋 `models/latest_lgbm.pkl`、不會修改正式 ranking，也不會輸出 promotion ready。

## 使用方式

只產題與更新管理層：

```bash
.venv/bin/python scripts/run_autonomous_research.py --date YYYY-MM-DD
```

產題後執行小樣本回測：

```bash
.venv/bin/python scripts/run_autonomous_research.py \
  --date YYYY-MM-DD \
  --execute \
  --max-ranking-files 3
```

指定某個 ranking 目錄：

```bash
.venv/bin/python scripts/run_autonomous_research.py \
  --date YYYY-MM-DD \
  --candidate-dir artifacts/backtest/<ranking-dir> \
  --execute
```

從管理佇列一次跑多個題目：

```bash
.venv/bin/python scripts/run_autonomous_research.py \
  --date YYYY-MM-DD \
  --execute \
  --from-queue \
  --execute-topic-count 3 \
  --max-ranking-files 5
```

若要重跑已跑過的題目，必須明確加 `--rerun`。預設會冷卻已執行過的 topic，避免同一題一直消耗回測資源。

## 管理層產物

```text
artifacts/autonomous_research/topic_registry.json
artifacts/autonomous_research/run_history.json
artifacts/autonomous_research/next_action_queue.json
artifacts/autonomous_research/manager_summary.json
artifacts/autonomous_research/runner_registry.json
```

- `topic_registry.json`：所有已看過的 topic、狀態、最後決策、下一步。
- `run_history.json`：每次 dry-run / execute 的歷史。
- `next_action_queue.json`：目前可推進的研究題目佇列。
- `manager_summary.json`：PM 快速讀的總摘要。
- `runner_registry.json`：允許使用的 runner 與安全契約。

## 狀態

- `candidate`：已發題，尚未跑 execute。
- `confirmed_for_next_replay`：小樣本 strategy matrix 同時通過 score / return / drawdown，可進更長 replay。
- `partial_needs_followup`：只有部分指標改善，需加長 window 或補風險檢查。
- `rejected`：strategy matrix 不支持，歸檔或等待新證據。
- `blocked_missing_evidence`：runner 沒產出 comparison evidence，需先查 artifact / runner 問題。

## 白名單 runner

目前只允許：

```text
scripts/run_backtest_strategy_matrix.py
scripts/compare_strategy_matrices.py
```

新增 runner 前必須先補 verifier，並明確證明：

- 不抓新資料。
- 不訓練模型。
- 不寫 `models/latest_lgbm.pkl`。
- 不改正式 ranking。
- 不輸出 promotion 授權。

## 佇列與冷卻

管理層會依 topic score 排序，但不會盲目重跑同一題：

- `--from-queue`：從 `next_action_queue` 語意選題。
- `--execute-topic-count N`：同一次最多跑 N 題。
- 預設跳過 `run_count > 0` 的 topic。
- `--rerun`：允許重跑已跑過的 topic。
- `--include-rejected`：允許 rejected topic 重新進入佇列。

單次 run 會保留：

- `selected_topic`：相容舊讀法，第一個被選中的 topic。
- `selected_topics`：本次所有選中的 topic。
- `topic_runs`：每個 topic 的 steps、outputs、outcome。
- `steps`：所有 topic steps 的平鋪版，方便快速檢查 OK/FAILED。

## 驗證

```bash
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  scripts/verify_autonomous_research.py \
  scripts/run_backtest_strategy_matrix.py

.venv/bin/python scripts/verify_autonomous_research.py
.venv/bin/python scripts/verify_backtest_strategy_matrix.py
git diff --check
```
