# MOM-01：本週模型初選池與每日快照 Contract

任務ID：`MOM-01`

證據路徑：`artifacts/weekly_candidate_snapshot_2026-05-15.json`

## 目的

讓 Momentum UI 的「本週候補」不只依賴 API runtime 讀 latest ranking，而是有明確的本週模型初選池 / 每日快照 artifact。

## 範圍

- 新增 `scripts/build_weekly_candidate_snapshot.py`。
- 新增 `artifacts/weekly_candidate_snapshot_YYYY-MM-DD.json` contract。
- API `/api/weekly-candidates` 優先讀最新 weekly snapshot，無 snapshot 才 fallback latest ranking。
- `run_automation daily` 在 ranking artifact 後產生 `weekly.snapshot`，預設啟用。

## 不做

- 不改模型分數。
- 不重算 ranking。
- 不接 ETF 候選。
- 不做前台歷史快照切換。
- 不改 Momentum UI 視覺。

## 驗收

- snapshot JSON 包含 `schema_version`、`snapshot_date`、`ranking_date`、`week_version`、`model_pool_count`、`model_pool`。
- `/api/weekly-candidates` response 包含 `snapshot` metadata。
- `run_automation daily --dry-run` 會出現 `weekly.snapshot=DRY_RUN`，但不實際生成。

## 驗證紀錄

- `uv run --with-requirements requirements.txt python -m py_compile scripts/build_weekly_candidate_snapshot.py scripts/run_automation.py app/data/market_repository.py app/services/weekly_decision_service.py app/contracts/weekly.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/build_weekly_candidate_snapshot.py --ranking artifacts/ranking_2026-05-15.csv` 通過，輸出 `artifacts/weekly_candidate_snapshot_2026-05-15.json`。
- `TOP10_RUN_DATE=2026-05-22 uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run` 通過，`weekly.snapshot=DRY_RUN`，且 command 明確傳入 `/Users/matt/TOP10new/artifacts/ranking_2026-05-15.csv`。
- `pnpm --dir web/frontend build` 通過。
- FastAPI TestClient 驗證 `/api/weekly-candidates`：`snapshot_source=ranking_artifact`、`snapshot_date=2026-05-15`、`model_pool_count=10`、`top_stock=3030`。
- `uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py` 通過。

## 證據摘要

- snapshot schema：`weekly-candidate-snapshot.v1`。
- snapshot date / ranking date：`2026-05-15`。
- week version：`2026-05-11`。
- model pool count：`10`。
- 第一名：`3030 德律`。
- contract 標記：`strategy=long_only_momentum`、`settings_applied=false`、`intraday_prices=false`。

## Review 修正

- `REVIEW-MOM-01` P2 已修正：`scripts/run_automation.py` 的 `weekly.snapshot` 正式與 dry-run 都會明確傳入 `ranking_{_latest_feature_date()}.csv`。
- 修正後 snapshot builder 不再自行挑最新 ranking 檔，避免 daily status 指向 A ranking、weekly snapshot 卻由 B ranking 產生。
- `REVIEW-MOM-01-FIX` 結論：未發現阻塞問題，可放行。
- 剩餘小風險：builder standalone 未傳 `--ranking` 時仍保留挑最新 ranking 的便利行為；automation daily 已固定傳入本次已驗證 ranking artifact。

## Review 派工卡

任務ID：REVIEW-MOM-01-FIX
卡片類型｜派工對象：Review / Contract｜另一個 AI
請讀：`docs/tasks/2026-05-22_MOM-01_weekly_candidate_snapshot_contract.md`、`scripts/build_weekly_candidate_snapshot.py`、`app/services/weekly_decision_service.py`、`app/data/market_repository.py`、`scripts/run_automation.py`
任務目的：複查 weekly.snapshot 是否綁定本次已驗證 ranking artifact，沒有讓 builder 自行挑最新檔，且 weekly snapshot contract 沒有改 ranking/model
證據路徑：`artifacts/weekly_candidate_snapshot_2026-05-15.json`
