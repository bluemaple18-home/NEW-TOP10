# NEW-TOP10 開發規範

## 1. 專案核心 (Core Context)
- **目的**：台股波段預測與自動化排名系統。
- **技術棧**：Python, LightGBM, Pandas, TWSE OpenAPI, Technical Indicators.
- **關鍵組件**：
  - `indicators.py`: 技術指標計算
  - `fundamental_data.py`: 基本面數據抓取
  - `reason_generator.py`: 推薦理由生成

## 2. 常用操作 (Common Workflows)
- **環境同步**：`uv sync`
- **數據抓取**：`uv run scripts/fetch_data.py`
- **模型訓練**：`uv run scripts/train_model.py`

## 3. 開發紀律 (Boris Standard)
- **Plan-Execute**：在修改核心 Signal（如新增 MACD 邏輯）前，產出訊號定義 Plan。
- **回饋閉環**：修改 ETL Pipeline 後，必須跑數據測試確保沒漏掉股票或產生 NaN。
- **AGENTS.md 複利**：將發現的卷商數據坑位、API 限制記錄於此。

## 4. 程式碼規範 (Style)
- **資料科學規範**：保持數據處理管線的乾淨，重要計算需寫單元測試。
- **環境管理**：嚴格使用 `uv` 與 `.venv` 建立隔離環境。
- **註解要求**：指標計算邏輯必須用繁體中文詳細說明（PM 視角）。
- **No Vibe Coding**：拒絕隨意調整權重，所有權重更動需有數據回測支持。
