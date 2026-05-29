# Context Manifest

## 必讀檔案
- `scripts/verify_pipeline_refactor.py`
- `scripts/verify_production_write_guard.py`
- `app/pipeline/orchestrator.py`
- `scripts/verify_model_group_acceptance.py`

## 證據來源
- `artifacts/automation_status.json`
- `artifacts/model_group_acceptance_2026-05-29.json`
- `data/clean/features.parquet`
- `data/clean/events.parquet`
- `data/clean/universe.parquet`

## 不可破壞
- 正式 `data/clean/*.parquet` 不得被 verify 腳本覆寫成測試資料。
- production daily 入口仍需允許寫正式 `data/clean`。
- `TOP10_ALLOW_VERIFY_PRODUCTION_WRITE=1` 只作明確人工 override，不可成為預設。
