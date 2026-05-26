# RETRAIN-02 formal manual retrain acceptance

## 卡片

任務ID：RETRAIN-02  
卡片類型｜派工對象：Model Ops / Formal Manual Retrain Acceptance｜Codex  
請讀：`docs/tasks/2026-05-25_RETRAIN-01_retrain_acceptance_gate.md`、`scripts/daily_retrain.sh`、`scripts/run_automation.py`、`app/agent_b_modeling.py`、`app/agent_b_ranking.py`  
任務目的：正式執行一次 `bash scripts/daily_retrain.sh retrain`，驗證模型備份、新模型產出、模型驗證、ranking smoke、monitor 與 summary/status 閉環  
證據路徑：`artifacts/automation_status.json`、`artifacts/retrain_run_summary_YYYY-MM-DD.json`、`artifacts/ranking_YYYY-MM-DD.csv`、`logs/retrain_YYYYMMDD.log`

## 邊界

- 不啟用 `monitor.auto_retrain`。
- 不改 ranking score 權重。
- 不改模型 feature list。
- 若正式流程失敗，以 RETRAIN-01 rollback 為準，不手動覆蓋正式模型。

## 驗收

- `models/latest_lgbm.pkl` 在訓練前有備份。
- 新模型通過 `model.validate`，且 feature count 不低於 `config.retrain.min_feature_count`。
- `model.ranking_smoke` 成功，並產出 latest feature date 對應的 ranking artifact。
- PSI / factor / industry momentum monitor 都成功。
- `artifacts/automation_status.json` 與 `artifacts/retrain_run_summary_YYYY-MM-DD.json` 為 `mode=retrain`、`dry_run=false`、`status=OK`。
- 若任一段失敗，status 必須記錄錯誤且 `models/latest_lgbm.pkl` 必須 rollback 到備份。

## 本地驗證

- `bash scripts/daily_retrain.sh retrain` 正式執行完成，wrapper exit code 0。
- `artifacts/automation_status.json`：`mode=retrain`、`status=OK`、`dry_run=false`、`run_date=2026-05-26`。
- `artifacts/retrain_run_summary_2026-05-26.json` 同步為 `mode=retrain`、`status=OK`、`dry_run=false`。
- `model.backup=OK`，備份檔：`models/backup/lgbm_20260526_111531.pkl`。
- 新模型：`models/latest_lgbm.pkl`，sha256 `468f271c13a0f16c2e0e12a009f4b7de0c779c54328ca75538bea6556fd8c70a`，feature_count=86，sha256_changed=true。
- 舊模型備份 sha256：`30c0b18d8d14fc42fff213074d36ad995fbb55736254c0fe584c1ee913ff5442`。
- ranking smoke：`artifacts/ranking_2026-05-25.csv` 產出 10 rows，Top1=`6125 廣運`。
- monitor：`psi.monitor=OK`、`factor.monitor=OK`、`industry_momentum.monitor=OK`、`backup.cleanup=OK`。
- 觀察到 PSI 報告為 `CRITICAL`、factor monitor 為 `FACTOR_MONITOR_WARN factors=60 warns=25`；目前腳本把這兩者視為監控警示而非 failed exit。
- `.gitignore` 已補 `models/backup/`，模型備份不納入 Git。

## Review 結論

- Formal manual retrain：PASS。
- Auto retrain readiness：BLOCKED；不建議開啟自動重訓。
- 主要原因：PSI `CRITICAL` 與 factor `WARN` 目前不阻斷手動 retrain，這對手動流程可接受，但不足以支撐未來 auto retrain。
- 後續已開 RETRAIN-03 補 auto/scheduled promotion gate。
