# MODEL-GOV-05 result report ledger resolver

## 任務卡

任務ID：MODEL-GOV-05
卡片類型｜派工對象：Report Resolver / Model Governance｜Codex
請讀：`scripts/build_model_experiment_result_report.py`、`scripts/verify_model_experiment_result_report.py`、`scripts/model_experiment_ledger.py`、`scripts/verify_model_experiment_ledger.py`
任務目的：讓既有 model experiment result report 成為實驗結果 source of truth，並由 resolver 把 result report 的 verdict 回寫到 ledger；不建立第二套 acceptance report。
證據路徑：`artifacts/model_experiments/model_exp_result_report_YYYY-MM-DD.json`、`artifacts/model_experiments/model_experiment_ledger.json`

## 交付內容

- 新增或擴充薄 adapter，讀取 `model_exp_result_report_YYYY-MM-DD.json` 後呼叫 ledger resolve/reschedule。
- `verify_model_experiment_result_report.py` 可檢查 result report 是否包含足夠欄位讓 ledger resolver 使用，但不把 ledger 當 acceptance source。
- Result report 若要支援 ledger resolver，需輸出或可映射：
  - `ledger_id`
  - `hypothesis`
  - `baseline`
  - `decision_policy`
  - `actual_metrics`
  - `verdict`
  - `next_action`
  - `promotion_allowed=false`
- 若必要 evidence 尚未成熟，必須 `reschedule`，不可猜 verdict。
- 若部分 metric 通過但風險 metric 失敗，必須 `partial` 或 `failed`，不可只看主要 metric。

## Source of truth 分工

- 實驗結果判定：`model_exp_result_report_YYYY-MM-DD.json`。
- 長期狀態保存：`model_experiment_ledger.json`。
- Ledger resolver 只做狀態同步，不重新計算 metrics、不改 verdict policy。

## Ledger 狀態映射

- `passed`：主要 metric 達標，風險 metric 未破壞，必要 evidence 完整。
- `failed`：主要 metric 未達標，或風險 metric 明確破壞。
- `partial`：主要 metric 有改善但 evidence 不完整、或不同 window 結論衝突。
- `expired`：到期後超過設定天數仍未有可驗收 evidence。

## 不可做

- 不把 `passed` 改寫成 `promotion_ready`。
- 不新增第二套 acceptance report。
- 不在 resolver 中重新定義 pass/fail 門檻。
- 不在 result report 階段新增新 filter。
- 不把 diagnostic-only variant 變成正式 winner。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/build_model_experiment_result_report.py scripts/verify_model_experiment_result_report.py scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/build_model_experiment_result_report.py --date YYYY-MM-DD
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_result_report.py --artifact artifacts/model_experiments/model_exp_result_report_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check -- scripts/build_model_experiment_result_report.py scripts/verify_model_experiment_result_report.py docs/tasks/2026-05-31_MODEL-GOV-05_result_report_acceptance.md
```

## TDD Loop

- RED：建立 synthetic report，覆蓋 pass/fail/partial/reschedule。
- GREEN：讓 report builder 正確呼叫 ledger resolve/reschedule。
- Refactor：把 metric policy 判定整理成純函式，避免 report 文字與判定邏輯混在一起。
