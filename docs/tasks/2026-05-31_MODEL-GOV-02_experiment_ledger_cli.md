# MODEL-GOV-02 experiment ledger CLI

## 任務卡

任務ID：MODEL-GOV-02
卡片類型｜派工對象：CLI / Model Governance｜Codex
請讀：`docs/architecture/MODEL_EXPERIMENT_LEDGER.md`、`scripts/build_model_experiment_plan.py`、`scripts/build_model_experiment_run_manifest.py`
任務目的：新增 `scripts/model_experiment_ledger.py`，提供 deterministic ledger CLI，讓模型實驗可登錄、查詢、到期掃描、驗收、改期、取代與統計。
證據路徑：`artifacts/model_experiments/model_experiment_ledger.json`、`artifacts/model_experiments/model_experiment_ledger_cli_verification_latest.json`

## 交付內容

- 新增 `scripts/model_experiment_ledger.py`。
- CLI 子命令：
  - `add`
  - `list`
  - `due`
  - `resolve`
  - `reschedule`
  - `supersede`
  - `stats`
  - `validate`
- 使用 atomic write，避免 ledger 寫到一半中斷。
- 支援 `--ledger` 指定測試 ledger。
- 支援 `--asof YYYY-MM-DD` 固定日期，方便測試。
- 同 id 且 hypothesis 太不同時必須拒絕，避免 slug 碰撞覆蓋。
- `due` 應自動把逾期超過門檻的 pending experiment 標成 `expired`。

## CLI 範例

```bash
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py add \
  --type feature \
  --candidate candidate_persistence \
  --slug streak-20d-top10 \
  --hypothesis "candidate_persistence_20d 會讓 sealed Top10 return 相對 baseline 提升 >= 0.002" \
  --falsification "sealed uplift <= 0" "production replay MDD 惡化 > 0.01" \
  --baseline artifacts/model_experiments/model_exp_run_manifest_YYYY-MM-DD.json \
  --target-metric sealed_top10_return_uplift:0.002 \
  --risk-metric replay_mdd_delta_max:0.01 \
  --trigger-date YYYY-MM-DD \
  --source MODEL-EXP-01
```

## 不可做

- 不在 CLI 裡計算模型結果。
- 不讀 production ranking。
- 不覆蓋既有 model experiment artifacts。
- 不把 `passed` 當成 promotion-ready。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py --ledger /tmp/top10_model_exp_ledger_test.json add --type feature --candidate candidate_persistence --slug smoke --hypothesis "candidate_persistence smoke hypothesis improves sealed top10 uplift" --falsification "sealed uplift <= 0" --baseline artifacts/model_experiments/model_exp_run_manifest_YYYY-MM-DD.json --target-metric sealed_top10_return_uplift:0.002 --risk-metric replay_mdd_delta_max:0.01 --trigger-date YYYY-MM-DD --source smoke
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py --ledger /tmp/top10_model_exp_ledger_test.json list
uv run --with-requirements requirements.txt python scripts/model_experiment_ledger.py --ledger /tmp/top10_model_exp_ledger_test.json validate
git diff --check -- scripts/model_experiment_ledger.py docs/tasks/2026-05-31_MODEL-GOV-02_experiment_ledger_cli.md
```

## TDD Loop

- RED：先補 CLI 行為測試，覆蓋 insert、collision、due、resolve、expired、stats。
- GREEN：完成最小 deterministic CLI。
- Refactor：把 schema validation 與 date helper 抽出，但保持單檔工具可讀。
