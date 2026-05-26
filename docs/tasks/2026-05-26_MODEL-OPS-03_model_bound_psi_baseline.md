# MODEL-OPS-03 model-bound PSI baseline

## 卡片

任務ID：MODEL-OPS-03  
卡片類型｜派工對象：Model Ops / PSI Baseline｜Codex  
請讀：`app/model_monitor.py`、`scripts/refresh_model_baseline.py`、`scripts/run_automation.py`、`scripts/verify_retrain_rollback.py`、`models/baseline_stats.json`  
任務目的：讓 PSI baseline 綁定現行正式模型 feature list 與 M4 feature frame，避免 stale baseline 把模型健康誤報成 CRITICAL；retrain 成功後刷新 baseline，失敗時模型與 baseline 一起 rollback  
證據路徑：`models/baseline_stats.json`、`artifacts/psi_report.json`、`artifacts/model_health_report_YYYY-MM-DD.json`、`artifacts/model_group_acceptance_YYYY-MM-DD.json`、`artifacts/retrain_rollback_injection_YYYY-MM-DD.json`

## 邊界

- 不訓練模型。
- 不重跑 ranking。
- 不改 ranking score 權重。
- 不啟用 auto retrain。
- 不調低 PSI 門檻。

## 驗收

- `models/baseline_stats.json` metadata 必須包含 `schema_version=model-baseline-stats.v1`、model sha256、model feature count、latest date、source。
- baseline metadata 必須揭露 `monitored_model_feature_count` 與 `skipped_empty_model_features`，不得把全空模型特徵偽裝成已監控。
- `app/model_monitor.py` 使用 M4 feature frame 與正式模型 feature_names 計算 baseline / drift。
- health report 若 baseline 分佈數少於模型 feature count，或 skipped/missing model features 非空，至少標 WARN。
- `scripts/refresh_model_baseline.py --check-after` 能刷新 baseline 並回報 PSI。
- retrain flow 會備份 baseline、刷新 baseline；後續失敗時會 `model.baseline.rollback=OK`。
- `verify_retrain_rollback.py` 必須驗證模型與 baseline 都會 rollback。

## 本地驗證

- 舊 baseline：created_at=`2026-01-20T16:39:25.864537`、samples=314316、features_count=58；正式模型 feature_count=86。
- 臨時重建 baseline 後 PSI 從 `CRITICAL avg_psi=0.5199` 降級；正式 model-bound baseline 刷新後，`avg_psi=0.0365`、status=`OK`。
- `uv run --with-requirements requirements.txt python scripts/refresh_model_baseline.py --check-after` 通過，輸出 `MODEL_BASELINE_REFRESH_OK features=84 samples=643063 latest=2026-05-25 status=OK`。
- `uv run --with-requirements requirements.txt python -m app.model_monitor` 通過，`artifacts/psi_report.json` 更新為 `status=OK`。
- `uv run --with-requirements requirements.txt python scripts/generate_model_health_report.py` 通過，health status 從 `CRITICAL` 降為 `WARN`。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 通過，`model_health_status=WARN`、`auto_retrain_readiness=BLOCKED`。
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile app/model_monitor.py scripts/refresh_model_baseline.py scripts/run_automation.py scripts/verify_retrain_rollback.py scripts/generate_model_health_report.py scripts/verify_model_group_acceptance.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_retrain_rollback.py` 通過；`ranking` / `promotion_gate` 等失敗 case 會 `model.baseline.rollback=OK`、`restored_original_baseline=true`。
- `uv run --with-requirements requirements.txt python scripts/verify_model_health_report.py` 通過，含 baseline coverage WARN regression。
- 剩餘阻塞：factor monitor 仍為 `WARN`，latest ranking realized outcome 尚未成熟；因此 auto retrain readiness 仍為 `BLOCKED`。

## Review 修正

- REVIEW-MODEL-OPS-03 P2：baseline 只有 84 個分佈，但模型 feature_count=86；`revenue_yoy` / `revenue_mom` 全空被跳過，metadata 卻未揭露。
- 修正：`app/model_monitor.py` 會在 baseline metadata 記錄 `skipped_empty_model_features` 與 `monitored_model_feature_count`。
- 修正：`scripts/generate_model_health_report.py` 新增 `baseline` 區塊與 `monitor.psi_baseline` check；baseline coverage 不完整時標 WARN。
- 修正：`scripts/verify_model_health_report.py` 補 baseline coverage WARN regression。
- evidence：`models/baseline_stats.json` metadata 目前為 `model_feature_count=86`、`features_count=84`、`monitored_model_feature_count=84`、`skipped_empty_model_features=["revenue_yoy","revenue_mom"]`、`missing_model_features=[]`。
- evidence：`artifacts/model_health_report_2026-05-26.json` 目前 `status=WARN`，`baseline.status=WARN`，reason=`monitored_model_feature_count=84<model_feature_count=86; skipped_empty_model_features=2`。
- evidence：`artifacts/model_group_acceptance_2026-05-26.json` 目前 `status=OK`、`model_health_status=WARN`、`auto_retrain_readiness=BLOCKED`。
