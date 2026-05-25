# UI 大翻修切片計畫

## 原則

- 核心演算法先保留，透過 service/API 包起來。
- UI、報告、圖表、啟動入口都可翻掉。
- 回測績效獨立成 domain，不和即時看盤資料流混在一起。
- 所有頁面先吃共用 contract，不直接讀 parquet/csv。

## Slice 1：資料契約與 Market API 分層

驗收條件：
- `app/contracts` 定義前端可依賴的 ranking / ohlcv schema。
- `app/data` 只負責讀既有檔案。
- `app/services` 組裝 API response。
- `app/api` 只保留 HTTP routing；`web/api` 僅作舊路徑相容。

驗證：
- `python -m py_compile app/api/main.py app/contracts/market.py app/data/market_repository.py app/services/market_service.py`
- `/api/health`、`/api/rankings/latest`、`/api/stocks/{id}/ohlcv` 可回應。

## Slice 2：前端共用元件骨架

驗收條件：
- 建立不含業務耦合的 Button / Panel / Metric / Stock item / App shell。
- 現有首頁可以逐步改用共用元件。

驗證：
- `pnpm build`

## Slice 3：K 線工作台模組化

驗收條件：
- K 線工作台吃 `StockOhlcvResponse` contract。
- 支援拖曳平移、滾輪縮放、時間窗、回最新。
- 指標 pane 與 overlay 後續可擴充。

驗證：
- `pnpm build`
- 本機 API + Vite smoke test。

## Slice 4：回測績效隔離

驗收條件：
- 新增 backtesting domain/service/API contract。
- UI 只讀回測摘要與曲線結果，不直接觸發長時間回測。
- 回測資料產物與 market ranking 分開。

驗證：
- 回測 API 能在沒有前端狀態下獨立 smoke test。
