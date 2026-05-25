# Changelog

## [v2.7.0-async-boost] - 2026-01-22 (效能飛躍與全域技能)

### 🚀 效能與架構升級 (Major)
- **非同步資料抓取 (Async Fetcher)**: 
  - 徹底重構 `data_fetcher.py`，導入 `aiohttp` + `asyncio`。
  - 從「單線程逐日爬取」進化為「多線程併發 (Semaphore=3)」。
  - 實測資料回補速度提升 3~5 倍，並移除冗餘同步代碼。
- **全域技能庫 (Global Skills)**:
  - 建立 `~/.agent/skills` 標準庫，包含 Playwright, Async Patterns, Scikit-learn 等核心能力。
  - 實現「零接觸 (Zero-Touch)」技能掛載，新專案自動繼承，無須重複安裝。

### ✨ 新功能與優化
- **市場訊號矩陣 (Signal Matrix)**: 
  - UI 佈局更新為矩陣式卡片 (趨勢、動能、量能、AI信心)。
  - 解決了選股切換時的「狀態鎖死」問題 (State Lock Fix)。
- **AI 可解釋性 (SHAP)**:
  - `agent_b_modeling.py` 新增 SHAP Summary Plot 實作，模型訓練後自動產出特徵影響力圖表。
- **穩健自動化測試**:
  - 重寫 `verify_ui_robust.py`，導入 `networkidle` 等待機制，徹底解決網路延遲導致的 False Positive。

### 🐛 錯誤修復
- **UI Reactivity**: 修復當選擇非 Top 10 股票時，下拉選單無法同步更新的問題。
- **Dependencies**: 清理 `requirements.txt`，加入 `aiohttp` 依賴。

---

## [v2.6.0-ui-verified] - 2026-01-22 (UI 重構與報告整合)

### 🚀 主要功能更新
- **SMC 矩陣式佈局**: 重構個股頁面，導入「主要趨勢」、「動能指標」、「量能分析」、「AI 信心」四象限矩陣。
- **垂直指標圖表**: MACD 與 KD 指標改為垂直堆疊排列，提升移動端與桌面端閱讀體驗。
- **分析報告深度整合**: 直接解析 `analysis_report.md`，將 TL;DR、交易建議、買入理由無縫整合至個股詳情頁底部。
- **介面優化**: 移除獨立的「分析報告」頁面，簡化導覽結構。

### 🐛 錯誤修復
- **YAML Loading Fix**: 修復因 numpy 數據類型導致的 `yaml.constructor.ConstructorError`，改為容錯讀取。
- **Syntax Fixes**: 修復 `ui.py` 中的縮排錯誤與 SyntaxError。
- **Robust Verification**: 強化自動化測試腳本，支援 Markdown 內容驗證與錯誤快照。

## [v2.5.0-verified] - 2026-01-21 (驗證系統整合)

### 🔧 系統改進

#### Added
- **自動化驗證腳本**: 新增 `scripts/verify_ui_robust.py`
  - 使用 Playwright 進行完整的 UI 功能測試
  - 自動檢測頁面載入、點擊互動、中文化驗證
  - 支援 headless 與 visible 兩種模式
  - 自動截圖存證功能
- **雙重驗證機制**: 整合原生瀏覽器工具與 Python 腳本驗證

#### Fixed
- **PyArrow 相容性**: 確認 pyarrow 21.0.0 與 pandas 2.3.3 版本相容
- **推薦理由中文化**: 整合 Mini 環境的 `SIGNAL_TRANSLATIONS` 對照表

#### Technical
- 新增 Playwright 依賴 (用於自動化測試)
- 建立標準化驗證流程，確保未來開發的穩定性

---

## [v2.4.0-ui] - 2026-01-21 (UI/UX 大幅優化)

### 🎨 Web UI 改進

#### Added
- **股票名稱對照表**: 新增 `app/stock_names.py`，自動顯示股票中文名稱（瑞展、聲寶等）
- **個股分析頁面**: 全新設計，專注於 AI 推薦理由與投資決策支援
  - 🤖 AI 推薦理由區塊：白話解釋每個技術訊號
  - 📍 技術位置分析：自動判斷多空格局、RSI 超買超賣、KD 交叉
  - 📈 整合式 K 線圖：K 線 + 成交量雙子圖設計
  - 💡 投資建議：明確的進場/出場參考指標
- **側邊欄股票選擇器**: 新增「📈 個股分析」頁籤，可直接選股查看詳細資訊
- **工作流程定義**: 新增 `.agent/workflows/switch-to-stock.md` 用於專案切換

#### Changed
- **台股配色模式**: K 線圖改為台股習慣（紅漲綠跌）
- **成交量視覺化**: 根據漲跌上色（紅色=漲，綠色=跌）並整合到 K 線圖下方
- **推薦理由顯示**: 解析 AI 訊號並翻譯成易懂的中文說明
  - ✅ 綠色顯示正面訊號
  - ⚠️ 橙色顯示警示訊號
- **均線顏色優化**: 使用更明亮的顏色以便區分（MA5/MA20/MA60）

#### Fixed
- **股票名稱缺失**: 修正選股列表只顯示代號的問題
- **資料型態問題**: 修正 `stock_id` 字串/整數型態不匹配導致圖表無法顯示
- **推薦理由格式**: 修正原始 AI 輸出格式，改為結構化展示

#### Technical
- 整合 Plotly subplots 實現 K 線 + 成交量雙子圖
- 新增技術訊號解釋字典（volume_ratio_20d, bb_width, macd, kd 等）
- 優化頁面路由邏輯支援個股詳細頁

#### Philosophy
- **以使用者為中心**: 從「展示技術指標」轉向「幫助理解投資決策」
- **可解釋 AI**: 每個推薦都有清楚的理由和建議
- **降低進入門檻**: 適合股市小白理解 AI 選股邏輯

---

## [v2.2.0-ml] - 2026-01-20 (Mini 發布: Web UI 介面)

### 📱 Web Interface

#### Added
- **Streamlit Web UI**: 完整的視覺化介面 (`app/ui.py`)
  - 今日選股頁面（Top 10 + AI 推薦理由）
  - 歷史績效頁面（趨勢圖 + 回測報告）
  - PSI 監控頁面（漂移狀態視覺化）
  - 系統資訊頁面
- **ngrok 遠端存取**: 從任何地方連回 Mac Mini
- **啟動腳本**: `scripts/start_ui.sh` (整合 Streamlit + ngrok)
- **launchd 自動啟動**: 開機自動啟動 Web UI
- **使用手冊**: `docs/WEBUI.md` (詳細安裝與設定指南)

#### Features
- 響應式設計（支援手機、平板、電腦）
- 即時資料更新（快取 5 分鐘）
- 互動式圖表（Plotly）
- 自訂 CSS 樣式

---

## [v2.1.0-ml] - 2026-01-20 (Mini 發布: 自動化系統)

### 🤖 Automation System

#### Added
- **每日自動執行腳本**: `scripts/run_daily.sh` (22:00 ETL + 選股)
- **每日自動重訓腳本**: `scripts/daily_retrain.sh` (02:00 模型訓練)
- **PSI 漂移監控**: `app/model_monitor.py` (自動偵測特徵分佈變化)
- **macOS launchd 排程**: 完整的 plist 設定檔與安裝腳本
- **自動化設定檔**: `config/automation.yaml` (集中管理參數)
- **使用手冊**: `docs/AUTOMATION.md` (詳細安裝與管理指南)

#### Features
- 模型自動備份 (保留 30 天)
- 訓練失敗自動恢復備份
- PSI 監控報告 (`artifacts/psi_report.json`)
- 完整日誌記錄 (`logs/`)

---

## [v2.0.0-ml] - 2026-01-20 (Mini 發布: ML模型優化)

### 🎯 Advanced Modeling: 中長期波段策略

#### Added
- **標籤系統升級**: 實作 `LabelGenerator` (持有 10 天, 獲利門檻 5%)
- **機率校準**: 整合 Isotonic Calibration 提升模型可信度
- **AI 可解釋性**: 加入 SHAP TreeExplainer，提供每日選股推薦理由
- **二元事件特徵**: 突破、均線交叉、布林通道、MACD、RSI 等技術訊號

#### Changed
- **模型訓練目標**: 從「短期獲利 (>0%)」改為「中長期波段 (>5%, 10天)」
- **排名邏輯優化**: 使用原始機率 (raw_prob) 排序，避免校準平坦化影響
- **回測持有期**: 從 5 天調整為 10 天，符合中長期定位

#### Fixed
- **資料洩漏修復**: 排除 `return_long`, `future_return` 等未來資訊欄位
- **ETL 穩定性**: 更新 TWSE RWD API 動態解析邏輯，支援欄位變更

#### Performance
- **平均單次報酬**: +5.33% (10天持有)
- **正報酬勝率**: 67.0%
- **適用客群**: 股市小白、無時間盯盤的中長期投資者

---

## [1.0.0] - 2025-XX-XX (估)

### Initial Release
- ETL 資料擷取 (TWSE, TPEX)
- LightGBM 分類模型 (Optuna 調優)
- Walk-forward Validation
- 基礎回測系統
