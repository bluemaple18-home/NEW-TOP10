# REVIEW-DATA-SEAL-01 data + sealed gate review

## 五行派工卡

任務ID：REVIEW-DATA-SEAL-01
卡片類型｜派工對象：Data / Model Ops Review｜Reviewer AI
請讀：`docs/tasks/2026-05-26_DATA-SEAL-01_data_pipeline_validate_gate.md`、`app/pipeline/validation.py`、`scripts/verify_daily_market_coverage_gate.py`、`scripts/verify_model_group_acceptance.py`、`docs/tasks/2026-05-26_DAILY-PROD-04_latest_market_coverage_gate.md`、`docs/tasks/2026-05-26_MODEL-OPS-02_model_group_acceptance.md`
任務目的：複查 pipeline latest market coverage gate 與 model group acceptance fail-fast 是否正確，且沒有把壞資料或單一市場資料放進正式驗收
證據路徑：`artifacts/model_group_acceptance_2026-05-26.json`、`scripts/verify_daily_market_coverage_gate.py`、`app.pipeline_cli validate --json`

## Review 重點

- TWSE-SOURCE-02 已獨立 review 通過並推上 `main`；本卡只檢查資料契約與 acceptance gate。
- 確認 `app.pipeline_cli validate` 會對正式 `data/clean/features.parquet` 最新日檢查 TWSE/TPEX 覆蓋，且只有 test fixture / 非正式 contract 不會被誤殺。
- 確認 `scripts/verify_model_group_acceptance.py` 把正式 `data.pipeline.validate` 納入總驗收；目前正式資料缺 TWSE 時，總驗收應回 `FAILED` 而不是 `OK`。
- 確認本次沒有重跑正式 ETL、ranking、retrain，沒有改模型、權重、threshold 或 production data。

## 預期現況

- `scripts/verify_daily_market_coverage_gate.py` 應通過。
- `python -m app.pipeline_cli validate --json` 目前應失敗，原因為最新日 `TWSE actual=0 expected=1080 ratio=0.0 < min=0.5`。
- `scripts/verify_model_group_acceptance.py` 目前應失敗，且唯一失敗步驟應是 `data.pipeline.validate`。

## Reviewer 判定

- PASS：上述閉環都成立，且沒有發現資料契約誤判 OK、或總驗收繞過正式資料 gate。
- FAIL：任一條閉環不成立，或發現單一市場 latest data 仍可進入 ranking / model acceptance。
