# MODEL-PROD-05 formal sealed model

## 卡片

任務ID：MODEL-PROD-05  
卡片類型｜派工對象：Model Production / Formal Manual Retrain｜Codex  
請讀：`config/automation.yaml`、`scripts/run_automation.py`、`scripts/daily_retrain.sh`、`scripts/run_sealed_oos_gate.py`、`scripts/verify_model_group_acceptance.py`  
任務目的：用已建立的 sealed OOS / rollback / baseline gate 產出新一代正式模型，讓 `models/latest_lgbm.pkl` 具備 sealed OOS metadata，並確認 ranking smoke 與 model group acceptance 可重跑  
證據路徑：`artifacts/automation_status.json`、`artifacts/retrain_run_summary_YYYY-MM-DD.json`、`artifacts/sealed_oos_report_YYYY-MM-DD.json`、`artifacts/model_group_acceptance_YYYY-MM-DD.json`

## 背景

- 目前正式模型可載入，但 metadata 尚無 `sealed_oos`。
- `scripts/run_sealed_oos_gate.py` 對舊模型回 `FAILED` 是正確安全行為。
- 本機資料若最新日市場覆蓋不足，必須先刷新 `data/clean`，不得繞過 data gate。

## 邊界

- 不啟用 `monitor.auto_retrain`。
- 不改模型權重、feature list 或 ranking score 公式。
- 不降低 sealed OOS、market coverage、PSI 或 promotion gate 門檻。
- 不把 reference / 產業資訊接進模型分數。
- 不做 UI / Clawd 延伸功能。

## 驗收

- `app.pipeline_cli validate --json` 通過，最新日 TWSE/TPEX 覆蓋足夠。
- 正式 manual retrain `dry_run=false` 完成。
- 新模型 metadata 含 `sealed_oos`，且 `scripts/run_sealed_oos_gate.py` 對新模型通過。
- retrain summary 包含 `model.validate`、`model.sealed_oos`、`model.baseline`、`model.ranking_smoke`、monitor steps。
- `models/baseline_stats.json` 重新綁定新模型 SHA。
- `scripts/verify_model_group_acceptance.py` 可重跑；若 health 仍為 WARN，需明確列出 WARN 來源，不得宣告 auto retrain ready。

## 初始盤點

- 舊模型 `feature_count=86`，metadata 無 `sealed_oos`。
- `app.pipeline_cli validate --json` 目前失敗：`features.parquet` 最新日 TWSE 覆蓋不足。
- 下一步先刷新正式 clean data，再跑 retrain。

## 執行紀錄

- 先執行 `python -m app.pipeline_cli run --end-date 2026-05-26` 刷新正式 clean data。
- `python -m app.pipeline_cli validate --json` 通過：`features/events/universe` 最新日皆為 `2026-05-26`，`ERROR=0`、`WARN=0`。
- `bash scripts/daily_retrain.sh retrain --trigger manual` 正式執行完成，`dry_run=false`。
- 新模型 SHA256：`ccb677c8bd7df0c0a5b04c9773b73b41fef04d88b2589e9cc48871a77c40889c`。
- 新模型 `feature_count=86`，metadata 已含 `sealed_oos`。
- `sealed_oos` window：development 至 `2026-01-14`，embargo `2026-01-15` ~ `2026-01-28`，sealed `2026-01-29` ~ `2026-05-12`。
- Sealed OOS gate 通過：AUC `0.6905502174`，Top10 hit-rate uplift `0.102499`。
- Baseline 已重新綁定新模型 SHA，且依 sealed train end date 限縮至 `2026-01-14`。
- Ranking smoke 產出 `artifacts/ranking_2026-05-26.csv`，Top1 為 `3402 漢科`。

## 驗證紀錄

- `uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json` 通過。
- `bash scripts/daily_retrain.sh retrain --trigger manual` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 通過，輸出 `artifacts/model_group_acceptance_2026-05-27.json`。
- `artifacts/automation_status.json`：`mode=retrain`、`status=OK`、`dry_run=false`。
- `artifacts/retrain_run_summary_2026-05-27.json`：`status=OK`。
- `artifacts/sealed_oos_report_2026-05-27.json`：`status=OK`。

## 剩餘風險

- `model_health_status=WARN`，因此 `auto_retrain_readiness=BLOCKED`，仍不可開啟 auto retrain。
- WARN 來源：
  - `monitor.psi_baseline`：`monitored_model_feature_count=81 < model_feature_count=86`，5 個模型特徵因空值無法監控。
  - `monitor.factor`：factor monitor 仍為 WARN。
  - `ranking.realized_outcome`：成熟樣本數 `2 < 10`，仍需等更多實際交易日。
- manual retrain 本身已可放行；auto retrain 必須留到 MODEL-HEALTH-01 再處理。
