# NEW-TOP10 開發規範

## 外接驗證與 runtime 入口
- FOG 外接代表性驗證必須使用 `tmp_artifact_lifecycle run --external-only --owned-root-writes-only --preserve validation_evidence`；daily 維持既有模式。exact child 沿 owner marker 驗 parent 原生容量 admission、持鎖與卷身分，容量持續監測／停損仍屬原 lifecycle parent；禁止改以 child APFS 控制權或 wide 外層略過隔離。
- 新 runtime 一律用 `scripts/prepare_runtime_checkout.py`：只建立外接 detached 程式碼 worktree，明示重用外接 `.venv`，核對 accepted commit 的 `uv.lock`／`pyproject.toml`；不複製 data／models／artifacts／archive 或建立環境。
- daily／FOG／`storage_safety validate-run` 的 payload 只能寫入現有 ai-core `tmp_artifact_lifecycle --external-only` 的 active owned sandbox。source 可唯讀在內建；lifecycle owner 的 Git common dir、tmp/cache、證據須在外接。缺卷、UUID／device 不符即拒絕，禁止 `/tmp` fallback。
- 檢查命令與持久證據路徑見 `docs/operations/top10-storage-safety.md`。cleanup 交既有 lifecycle；保留小型 receipt／hash／log，未知 root、dirty、備份與回復版本保留。不把此入口防線宣稱成任意 raw shell 的攔截器。

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
