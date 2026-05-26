# MODEL-OPS-01 model health report

## 卡片

任務ID：MODEL-OPS-01  
卡片類型｜派工對象：Model Ops / M11 Health Report｜Codex  
請讀：`docs/architecture/MODEL_ROADMAP.md`、`scripts/run_automation.py`、`scripts/generate_model_health_report.py`、`artifacts/psi_report.json`、`artifacts/factor_monitor_report.json`  
任務目的：把模型檔、ranking artifact、PSI、factor、industry monitor 與 ranking realized outcome 收斂成一份只讀健康報告，補足 M11 監控閉環  
證據路徑：`artifacts/model_health_report_YYYY-MM-DD.json`、`artifacts/model_health_report_latest.json`

## 邊界

- 不訓練模型。
- 不重跑 ranking。
- 不改 ranking score 權重。
- 不啟用 `monitor.auto_retrain`。
- 不接 UI。

## 驗收

- 報告能讀取 `models/latest_lgbm.pkl`，並記錄 sha256、mtime、feature_count、metadata / calibrator 狀態。
- 報告能讀取最近 ranking artifacts，並對已成熟 horizon 的 Top10 計算 realized outcome；尚未成熟者列為 pending。
- 報告能整合 PSI / factor / industry monitor status。
- `scripts.run_automation monitor` 會把 `model.health` 納入 dry-run / 正式 monitor 流程。
- 報告只讀既有 artifacts 與 data，不呼叫模型訓練、ranking、ETL、API 或外部網路。

## 本地驗證

- 新增 `scripts/generate_model_health_report.py`。
- 新增 `scripts/verify_model_health_report.py`，使用 temp project 驗證 outcome 與 status aggregation，不碰正式模型。
- `scripts/run_automation.py` 的 monitor flow 新增 `model.health` step。
- `docs/AUTOMATION.md` 補上 model health report 說明。
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile scripts/generate_model_health_report.py scripts/verify_model_health_report.py scripts/run_automation.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_model_health_report.py` 通過，輸出 `MODEL_HEALTH_VERIFY_OK`。
- `uv run --with-requirements requirements.txt python scripts/generate_model_health_report.py` 通過，輸出 `artifacts/model_health_report_2026-05-26.json` 與 `artifacts/model_health_report_latest.json`。
- 目前 health report status=`CRITICAL`：模型檔 OK、latest ranking OK；PSI=`CRITICAL`、factor=`WARN`、industry momentum=`OK monitor_only`、realized outcome 樣本不足。
- `uv run --with-requirements requirements.txt python -m scripts.run_automation monitor --dry-run` 通過，`model.health=DRY_RUN`。

## Review 結論

- MODEL-OPS-01：PASS。
- 確認 health report 只讀既有 artifacts / data / model，不呼叫 train、ranking、ETL 或外部 API。
- 確認報告不遮掩紅燈：整體 `CRITICAL`，PSI=`CRITICAL`，factor=`WARN`，realized outcome=`WARN`。
