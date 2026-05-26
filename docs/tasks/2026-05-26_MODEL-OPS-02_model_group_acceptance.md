# MODEL-OPS-02 model group acceptance

## 卡片

任務ID：MODEL-OPS-02  
卡片類型｜派工對象：Model Ops / Acceptance Suite｜Codex  
請讀：`docs/tasks/2026-05-26_MODEL-OPS-01_model_health_report.md`、`scripts/verify_model_group_acceptance.py`、`scripts/verify_model_foundation.py`、`scripts/verify_review_fixes.py`、`scripts/verify_data_contracts.py`  
任務目的：建立一鍵模型組驗收入口，確認模型底座、ranking regressions、data contracts、health report、rollback gate 都可重跑，並明確標示 auto retrain readiness  
證據路徑：`artifacts/model_group_acceptance_YYYY-MM-DD.json`

## 邊界

- 不訓練模型。
- 不重跑 ranking。
- 不抓外部資料。
- 不啟用 auto retrain。
- 不改 production score。

## 驗收

- 驗收入口能依序跑 model foundation、review regressions、data contracts、model health unit、retrain rollback、model health report。
- 任一驗證命令非 0 時，總驗收 status 必須 FAILED。
- `model_health_status` 必須獨立揭露，不把 CRITICAL 偽裝成 OK。
- `auto_retrain_readiness` 必須在 health 非 OK 時標為 BLOCKED。
- `monitor.auto_retrain=true` 且 readiness 非 READY 時，總驗收必須 FAILED。
- `monitor.auto_retrain=true` 且 readiness=READY 時，總驗收可為 OK，避免未來開啟自動重訓時被固定擋死。

## 本地驗證

- 新增 `scripts/verify_model_group_acceptance.py`。
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile scripts/generate_model_health_report.py scripts/verify_model_health_report.py scripts/verify_model_group_acceptance.py scripts/run_automation.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 通過。
- 輸出 `artifacts/model_group_acceptance_2026-05-26.json`。
- acceptance status=`OK`、commands_ok=`true`。
- 子驗證全部通過：model.foundation、review.regressions、data.contracts、model.health.unit、retrain.rollback、model.health.report。
- model_health_status=`CRITICAL`，auto_retrain_enabled=`false`，auto_retrain_readiness=`BLOCKED`。
- Review 後修正：`acceptance_status()` 不再把 `auto_retrain_enabled=true` 一律視為 FAILED；只有 enabled 且 readiness 非 READY 才 FAILED。`verify_model_health_report.py` 已補對應四組狀態組合測試。

## Review 結論

- MODEL-OPS-01 / MODEL-OPS-02：PASS。
- 確認 health report 只讀既有模型、ranking、features 與 monitor artifacts，不訓練、不重跑 ranking、不抓外部 API。
- 確認 evidence 如實標出 `model_health_status=CRITICAL`、PSI=`CRITICAL`、factor=`WARN`、realized outcome=`WARN`。
- 確認 acceptance suite 六個子驗證 exit code 全 0，commands_ok=true；auto retrain 仍 disabled 且 readiness=`BLOCKED`。
