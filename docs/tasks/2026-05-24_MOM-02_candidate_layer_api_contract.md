# MOM-02：候選頁分層 API Contract

任務ID：`MOM-02`

證據路徑：`artifacts/mom02_candidate_layer_contract_2026-05-24.json`

## 目的

把 `/api/weekly-candidates` 從「只回本週候選 Top10」推進成可區分「本週模型初選池」與「全域投資設定後候選」的 API contract。

## 範圍

- `WeeklyCandidatesResponse` 新增 `model_pool`。
- `WeeklyCandidatesResponse` 新增 `candidate_layer`。
- 現有 `stock_candidates` 保持向後相容，仍是前端目前使用的候選清單。
- `candidate_layer` 記錄 model pool count、visible candidate count、settings hidden count 與 settings effects。

## 不做

- 不改模型分數。
- 不重算 ranking。
- 不改 UI 視覺版面。
- 不接 ETF ranking。
- 不新增個股搜尋或持股追蹤。

## 驗收

- API response 同時包含 `model_pool` 與 `stock_candidates`。
- `target_type=stocks` 時，`candidate_layer.visible_candidate_count == len(stock_candidates)`。
- `target_type=etfs` 時，現階段 stock model pool 會被設定隱藏，`stock_candidates=[]`，並在 `settings_effects` 揭露原因。

## 驗證紀錄

- `uv run --with-requirements requirements.txt python -m py_compile app/contracts/weekly.py app/contracts/__init__.py app/services/weekly_decision_service.py` 通過。
- `pnpm --dir web/frontend build` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py` 通過。
- FastAPI TestClient contract 驗證通過，輸出 `artifacts/mom02_candidate_layer_contract_2026-05-24.json`。

## 證據摘要

- `target_type=stocks`：`model_pool_len=10`、`stock_candidates_len=10`、`hidden_by_settings_count=0`、Top1 `3030`。
- `target_type=etfs`：`model_pool_len=10`、`stock_candidates_len=0`、`hidden_by_settings_count=10`、`settings_effects[0].reason=target_type`。
- `target_type=etfs` 的 `market_summary` 已改用設定後可見候選：`符合設定數量=0 檔`、狀態分布全為 0、`主要壓低品質原因=尚無候選`。
- 這張只新增 API contract 欄位；現有前端仍讀 `stock_candidates`。

## Review 修正

- `REVIEW-MOM-02` P2 已修正：`market_summary` 與 `status_counts` 改用 `visible_stock_candidates`。
- ETF 模式不再用被設定隱藏的股票候選計算 summary，避免混淆模型初選池與設定後候選。
- `REVIEW-MOM-02-FIX` 結論：未發現阻塞問題，可放行。
- Contract 分層確認：`model_pool` 保留模型初選池，`stock_candidates` 是設定後可見候選，`candidate_layer` 揭露被設定隱藏的數量與原因。

## Review 派工卡

任務ID：REVIEW-MOM-02-FIX
卡片類型｜派工對象：Review / API Contract｜另一個 AI
請讀：`docs/tasks/2026-05-24_MOM-02_candidate_layer_api_contract.md`、`app/contracts/weekly.py`、`app/services/weekly_decision_service.py`、`web/frontend/src/types.ts`
任務目的：複查 market_summary 是否使用設定後可見候選，weekly candidates API 是否清楚區分模型初選池與設定後候選，且沒有改 ranking/model/UI 行為
證據路徑：`artifacts/mom02_candidate_layer_contract_2026-05-24.json`
