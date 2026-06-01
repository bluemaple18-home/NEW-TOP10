# MODEL-GOV-06 governance surfacing

## 任務卡

任務ID：MODEL-GOV-06
卡片類型｜派工對象：Reporting / Ops Visibility｜Codex
請讀：`scripts/generate_daily_report.py`、`scripts/build_weekend_research_decision_report.py`、`scripts/build_model_experiment_result_report.py`、`scripts/model_experiment_ledger.py`
任務目的：把 experiment ledger 狀態露出到 daily / weekend / research reports，讓 PM 能看到目前哪些模型假設 pending、哪些已失敗、哪些值得下一輪研究。
證據路徑：`artifacts/daily_report_YYYY-MM-DD.json`、`artifacts/weekend_research_decision_report_YYYY-MM-DD.json`、`artifacts/model_experiments/model_experiment_ledger_stats_YYYY-MM-DD.json`

## 交付內容

- 新增 `scripts/build_model_experiment_ledger_stats.py`。
- Daily report 增加精簡區塊：
  - pending experiments due soon
  - failed / partial since last run
  - blocked promotion reasons
- Weekend research decision report 增加治理區塊：
  - candidate hit rate
  - expired count
  - repeated failed hypothesis family
  - next research priorities
- 報告只顯示摘要，不塞完整 ledger。

## 顯示原則

- 先講結論：本週是否有任何 experiment 可進下一關。
- failed/partial 必須列原因，不可只列分數。
- expired 要列為 follow-through 失敗，不算 hit rate 分母，但要算治理缺口。
- pending due soon 必須列下一步 action。

## 不可做

- 不讓 daily report 改 ranking。
- 不把治理摘要塞進股票推薦理由。
- 不要求 UI 必須同步實作；若要 UI，再另開卡。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/build_model_experiment_ledger_stats.py scripts/generate_daily_report.py scripts/build_weekend_research_decision_report.py
uv run --with-requirements requirements.txt python scripts/build_model_experiment_ledger_stats.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/generate_daily_report.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/build_weekend_research_decision_report.py --date YYYY-MM-DD
git diff --check -- scripts/build_model_experiment_ledger_stats.py scripts/generate_daily_report.py scripts/build_weekend_research_decision_report.py docs/tasks/2026-05-31_MODEL-GOV-06_governance_surfacing.md
```

## TDD Loop

- RED：用 synthetic ledger 驗證 stats 對 pending/passed/failed/partial/expired 的統計。
- GREEN：接到 report builder。
- Refactor：保持 report schema 向後相容，新增欄位不破壞既有 verifier。
