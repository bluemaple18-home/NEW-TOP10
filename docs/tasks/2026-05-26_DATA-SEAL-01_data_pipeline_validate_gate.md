# DATA-SEAL-01 data pipeline validate gate

## 卡片

任務ID：DATA-SEAL-01
卡片類型｜派工對象：Data / Model Ops Contract｜Codex
請讀：`app/pipeline/validation.py`、`scripts/verify_daily_market_coverage_gate.py`、`scripts/verify_model_group_acceptance.py`、`docs/tasks/2026-05-26_DAILY-PROD-04_latest_market_coverage_gate.md`、`docs/tasks/2026-05-26_MODEL-OPS-02_model_group_acceptance.md`
任務目的：把最新交易日 TWSE/TPEX 覆蓋檢查下沉到正式 `app.pipeline_cli validate`，並讓模型組總驗收在 production data 最新日缺市場時誠實 fail
證據路徑：`artifacts/model_group_acceptance_2026-05-26.json`、`scripts/verify_daily_market_coverage_gate.py`

## 邊界

- 不重跑正式 ETL。
- 不產生 ranking。
- 不訓練或替換模型。
- 不改 data freshness threshold、model threshold 或 ranking score。
- 只強化既有資料契約與 acceptance gate。

## 驗收

- `app.pipeline_cli validate --json` 對正式 `data/clean/features.parquet` 最新日檢查 required markets 覆蓋。
- 最新日只剩 TPEX 或 TWSE 單一市場時，pipeline validate 必須回 non-zero。
- synthetic regression 覆蓋 automation freshness gate 與 pipeline contract gate。
- `scripts/verify_model_group_acceptance.py` 必須納入正式 `data.pipeline.validate`。
- 目前 production data 因 `TWSE actual=0 expected=1080`，model group acceptance 應回 `FAILED`，不能偽裝成 OK。

## 本地驗證

- `uv run --with-requirements requirements.txt python scripts/verify_daily_market_coverage_gate.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/pipeline/validation.py scripts/verify_daily_market_coverage_gate.py scripts/verify_model_group_acceptance.py`
- `uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json` 目前預期失敗，原因為 `TWSE actual=0 expected=1080 ratio=0.0 < min=0.5`。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 目前預期失敗，且失敗步驟應為 `data.pipeline.validate`。
