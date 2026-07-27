# Autonomous Research Manager

## 定位

`scripts/run_autonomous_research.py` 是研究總入口與管理層。它可以自己產生研究題目、選出可用既有 artifacts 回測的題目，並在 `--execute` 時跑白名單回測。

它不是模型升版 gate，不會訓練模型、不會覆蓋 `models/latest_lgbm.pkl`、不會修改正式 ranking，也不會輸出 promotion ready。

## 封閉盤勢研究模式

`--closed-regime-research` 是 default-off 的嚴格模式。啟用後，manager 不再以
ranking 目錄名稱作正式資格，而會：

1. 從 `market_regime_history.v2` 讀取不晚於研究日的 `as_of_date`。
2. 把 `base_regime + 完整 family tag set` 寫入 topic。
3. 依 relevance、evidence gap、information gain、product value、
   feasibility 與 compute cost 輸出可重現 score breakdown。
4. 把 exact-match identity 傳給 strategy matrix；matrix 在建立 entry plan
   前排除 base-only match、family mismatch、transition 與 `UNKNOWN`。

```bash
.venv/bin/python scripts/run_autonomous_research.py \
  --date YYYY-MM-DD \
  --closed-regime-research \
  --market-regime-history artifacts/market_regime_history_YYYY-MM-DD.json
```

盤勢 history 缺少 `as_of_date`、當前盤勢為 transition／`UNKNOWN`，或沒有
exact-match ranking date 時一律 fail closed，不會回退到檔名或全期間結果。

## 參數宇宙與封閉實驗

單一契約在 `config/regime_research_contract.json`。目前從既有可執行程式盤點出
四個維度、720 個穩定 combination ID；「兩百萬級」來源尚無可稽核 inventory，
所以明確標記 `PARTIAL_BLOCKED_SOURCE_UNKNOWN`，不得外推或宣稱完整覆蓋。

封閉實驗以 immutable hash 固定 research question、baseline、dataset、split、
parameter space 與 metric policy。registry 使用 JSONL append-only；已影響選擇的
sealed episode 不得再次當新 OOS。跨實驗零件拼接必須使用新 experiment ID 與
全新 sealed episodes。

漏斗只能依序前進：

```text
REGISTERED
→ COARSE_SCREEN
→ SAME_REGIME_VALIDATION
→ SEALED_OOS
→ FORWARD_SHADOW
→ REGIME_POLICY_CANDIDATE
```

最高分不等於通過；Bonferroni family-wise correction、鄰近參數穩定度與 drawdown
必須同時通過。全部候選失敗時輸出 `NO_STRATEGY`，樣本不足則輸出
`INSUFFICIENT_EVIDENCE`。

Universal candidate 只有在 parameter universe 已證明完整、逐盤勢 coverage
closed、沒有高價值區域待研究、參數完全凍結、每個具足夠證據的盤勢都通過獨立
sealed OOS 時才可能解鎖。目前 inventory 未完成，因此 gate 預設 locked。

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

已跑過的題目只能依 manager 狀態、最大執行次數與 24 小時 cooldown 受控重跑，不需要也不能用 CLI flag 繞過政策。`--rerun` 與 `--include-rejected` 僅保留舊入口參數相容性，不會放寬選題資格。

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
- `confirmed_for_next_replay` 最多執行 2 次，`partial_needs_followup` 最多執行 3 次；兩者每次 execute 後至少冷卻 24 小時。
- 仍有後續執行次數的 topic 會保留在 queue；冷卻期間 selection gate 會跳過，但不會把它從 queue 移除。
- `rejected`、已達最大執行次數、缺少可證明真實 execute 時間的 topic 均 fail closed。
- history fallback 只接受 `execute=true` 的 real-execution row；dry-run 或缺少 `execute` 的 row 不構成 cooldown 證據。
- `--rerun`／`--include-rejected`：僅相容 legacy 呼叫，不得繞過上述 manager policy。

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
.venv/bin/python scripts/verify_regime_research_autonomy.py
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
git diff --check
```
