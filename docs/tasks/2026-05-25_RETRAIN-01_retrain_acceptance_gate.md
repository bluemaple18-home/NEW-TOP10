# RETRAIN-01 retrain acceptance gate

## 卡片

任務ID：RETRAIN-01  
卡片類型｜派工對象：Model Ops / Retrain Safety Gate｜Codex  
請讀：`scripts/run_automation.py`、`scripts/daily_retrain.sh`、`config/automation.yaml`、`docs/AUTOMATION.md`  
任務目的：補上手動/未來自動重訓的 preflight、模型備份、新模型驗證、ranking smoke、monitor 後驗收、失敗回滾與 retrain summary  
證據路徑：`artifacts/automation_status.json`、`artifacts/retrain_run_summary_YYYY-MM-DD.json`、`artifacts/retrain_rollback_injection_YYYY-MM-DD.json`、`logs/retrain_YYYYMMDD.log`

## 邊界

- 不開啟 auto retrain。
- 不修改 ranking score 權重。
- 不改 LightGBM 訓練邏輯。
- 不把 `models/backup/`、`artifacts/` 或 `logs/` 納入 Git。

## 驗收

- `bash scripts/daily_retrain.sh retrain --dry-run` 會列出 data.validate、model.backup、model.train、model.validate、model.ranking_smoke、monitor 與 backup cleanup，且不覆蓋正式模型。
- 正式 retrain 會先備份舊模型。
- 新模型必須是 dict payload，且包含 model、feature_names / model.feature_name、metadata。
- 新模型 mtime 必須晚於本次訓練開始時間。
- ranking smoke 必須產出同一個 latest feature date 的 ranking artifact。
- 訓練後驗證、ranking smoke 或 monitor 任一失敗時，必須回滾 `models/latest_lgbm.pkl`。
- shell wrapper 失敗時仍會列印本次 status，且不會讀上一輪 stale status 當成證據。

## 本地驗證

- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile scripts/run_automation.py scripts/print_daily_status.py` 通過。
- `uv run --with-requirements requirements.txt python -m py_compile scripts/run_automation.py scripts/print_daily_status.py` 通過。
- `bash -n scripts/daily_retrain.sh scripts/run_daily.sh` 通過。
- `uv run --with-requirements requirements.txt python -m scripts.run_automation retrain --dry-run` 通過。
- `bash scripts/daily_retrain.sh retrain --dry-run` 通過，`logs/retrain_20260525.log` 內有「手動模型重訓」與 dry-run retrain status。
- `artifacts/automation_status.json` 顯示 `mode=retrain`、`status=OK`、`dry_run=true`，且步驟包含 `model.validate`、`model.ranking_smoke`、三個 monitor 與 `backup.cleanup`。
- `artifacts/retrain_run_summary_2026-05-26.json` 已由 wrapper dry-run 產出 summary。
- `print_daily_status.py --min-started-at-epoch 4102444800` 正確拒絕 stale status。
- `bash scripts/daily_retrain.sh status` 在本機權限環境通過，wrapper 會列印本次 status。
- `logs/retrain_20260526.log` 包含 `bash scripts/daily_retrain.sh retrain --dry-run` 產出的「手動模型重訓」區塊，並列印 `mode=retrain`、`run_date=2026-05-26` 與 retrain summary 路徑。
- `uv run --with-requirements requirements.txt python scripts/verify_retrain_rollback.py` 通過，`artifacts/retrain_rollback_injection_2026-05-26.json` 顯示 model.validate、ranking smoke、monitor 三種故障注入都會回滾原模型。
- 直接呼叫 `_validate_retrained_model()` 驗證目前正式模型：`features=86`。
