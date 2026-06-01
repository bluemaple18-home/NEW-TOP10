# AUTO-TRAINING-04 revenue features or technical-only lane

## 任務ID

`AUTO-TRAINING-04`

## 卡片類型｜派工對象

Data Contract / Training Lane Policy｜Codex

## 請讀

- `scripts/verify_training_automation_readiness.py`
- `artifacts/training_automation_readiness_2026-06-01.json`
- `artifacts/model_health_report_latest.json`
- `app/pipeline/fundamental_data.py`
- `app/modeling/feature_contract.py`

## 任務目的

處理 model health WARN 中的 `revenue_yoy` / `revenue_mom` PSI baseline 缺口。決策方向二選一：補月營收資料來源，或正式化 technical-only training lane。

## 背景

目前 PSI baseline 少 2 個 model features。這不阻擋 training candidate launch，但阻擋 production promotion。不能讓這個 warning 永遠靠口頭豁免。

## 要做

- 確認 `revenue_yoy` / `revenue_mom` 缺失原因。
- 若資料源可補，補 ETL / feature contract / coverage verifier。
- 若短期不可補，建立 technical-only lane artifact，明確標記：
  - research-only allowed。
  - promotion disallowed unless sealed/replay/acceptance all accept degradation。
- 更新 readiness policy，避免文字互相矛盾。

## 不可做

- 不把缺值當好訊號。
- 不靜默 drop model features。
- 不讓 technical-only lane 自動 promotion。
- 不因 data unavailable 降低 sealed/replay/acceptance 門檻。

## 驗收

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

若選擇補資料：

```bash
uv run --with-requirements requirements.txt python -m app.pipeline_cli run
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json
```

## 回報格式

```text
AUTO-TRAINING-04 status:
chosen path: data_fix/technical_only_lane
revenue_yoy coverage:
revenue_mom coverage:
readiness:
promotion allowed:
errors:
```
