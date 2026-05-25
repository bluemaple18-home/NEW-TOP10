# OPS-01：本地 dev 啟動與健康檢查

任務ID：`OPS-01`
卡片類型｜派工對象：Ops / Local dev healthcheck｜Codex
請讀：`scripts/start_market_ui.sh`、`web/frontend/.env.example`、`web/frontend/src/api.ts`、`README.md`
任務目的：修正本地重啟後 API port 與前端 API base URL 不一致的問題，提供可重複執行的本地健康檢查，避免前端骨架載入但資料 API 失敗。
證據路徑：`artifacts/top10_ops01_local_dev_healthcheck_2026-05-19.json`

## 狀態

`completed`

## 範圍

- `scripts/start_market_ui.sh` 預設 API port 改為 `8001`，與前端預設 `VITE_API_BASE_URL=http://127.0.0.1:8001` 對齊。
- 新增 `scripts/start_ui.sh`，保留 README 既有啟動命令。
- 新增 `scripts/verify_local_dev_health.sh`，驗證：
  - `/api/health`
  - `/api/weekly-candidates`
  - `/api/stocks/3030/detail`
  - 前端 dev server `/`
- README 補健康檢查命令。

## 不做

- 不改 production API contract。
- 不改 ranking / model / data pipeline。
- 不新增外部服務依賴。

## 驗收結果

- `bash -n scripts/start_market_ui.sh scripts/start_ui.sh scripts/verify_local_dev_health.sh` 通過。
- `bash scripts/verify_local_dev_health.sh` 通過：
  - `api.health status=200`
  - `api.weekly_candidates status=200`
  - `api.stock_detail status=200`
  - `frontend status=200`

## Review 派工卡

任務ID：`REVIEW-OPS-01`
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-19_OPS-01_local_dev_healthcheck.md`、`scripts/start_market_ui.sh`、`scripts/start_ui.sh`、`scripts/verify_local_dev_health.sh`、`README.md`
任務目的：review 本地啟動腳本是否統一使用 API port 8001、README 啟動命令是否存在、healthcheck 是否能驗證 API 與前端資料路徑。
證據路徑：`artifacts/top10_ops01_local_dev_healthcheck_2026-05-19.json`
