# TW Top10 選股系統

## 專案簡介

這是一個針對台灣股市的自動化選股系統，透過技術指標分析與機器學習模型，每日篩選出最具潛力的前 10 支股票。

## 專案結構

```
TOP10new/
├── data/              # 資料目錄（Git 只保留空目錄，資料可重抓）
│   ├── raw/          # 原始資料
│   └── clean/        # 清理後的資料
├── models/           # 訓練好的模型檔案
├── artifacts/        # 產出物（圖表、報告等）
├── app/              # 應用程式
│   ├── api/         # FastAPI 看盤資料 API
│   ├── pipeline/    # ETL stage 與資料契約
│   └── trading/     # 交易計畫、排名政策、市場狀態
├── web/frontend/     # React + KLineCharts 看盤 UI
├── skills/           # 自訂技能與工具
├── requirements.txt  # Python 套件相依
├── .env.sample      # 環境變數範本
└── README.md        # 專案說明文件
```

## 安裝步驟

### 1. 建立虛擬環境（使用 uv）

```bash
# 安裝 uv（如果尚未安裝）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 建立虛擬環境
uv venv

# 啟動虛擬環境
source .venv/bin/activate  # macOS/Linux
```

### 2. 安裝相依套件

```bash
uv pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp .env.sample .env
# 編輯 .env 填入實際設定值
```

## 使用方式

### Agent A：盤後資料整備

#### 快速測試（7 天資料）

```bash
python test_agent_a.py
```

#### 完整 ETL 流程（3 年資料）

```bash
# 執行完整 ETL 流程
uv run --with-requirements requirements.txt python -m app.pipeline_cli run

# 指定日期範圍
uv run --with-requirements requirements.txt python -m app.pipeline_cli run --start-date 2023-01-01 --end-date 2026-01-20

# 僅執行驗收測試
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
```

**產出檔案**：
- `data/clean/features.parquet`：完整特徵資料（所有股票 × 所有指標）
- `data/clean/events.parquet`：技術事件訊號
- `data/clean/universe.parquet`：經風險過濾後的股票池
- `artifacts/etl_report.md`：ETL 執行報告
- `artifacts/signals_preview.png`：訊號預覽圖

> [!NOTE]
> 首次執行會需要約 30-60 分鐘（需下載近 3 年資料），請耐心等待。
> API 請求間隔預設 3 秒，避免被 TWSE/TPEX 封鎖。

### Agent B｜選股系統（v2.0.0-ml）

**中長期波段策略** - 適合股市小白、無時間盯盤的投資者

- **每日選股**: 自動產出 Top 10 推薦股票
- **深度學習**: LightGBM 分類模型 + Isotonic 機率校準
- **AI 可解釋性**: SHAP 推薦理由（告訴你為什麼選這檔）
- **績效驗證**: 回測勝率 67%，平均報酬 5.33% (10天持有)

```bash
# 手動執行選股
python app/agent_b_ranking.py

# 查看結果
cat artifacts/ranking_$(date +%Y-%m-%d).csv
```

---

## 🤖 自動化系統

### 快速安裝（macOS）

```bash
# 一鍵安裝自動排程
bash scripts/setup_launchd.sh
```

**功能**:
- 📊 **每日 22:00**: ETL 資料更新 + 選股推論
- 🔧 **每日 02:00**: PSI 漂移監控
- 📈 **PSI 監控**: 自動偵測市場環境變化

### 手動測試

```bash
# 測試每日執行流程
bash scripts/run_daily.sh

# 本機輕量測試 PSI 監控；重型產業監控會被 local_safe 跳過
bash scripts/daily_retrain.sh monitor

# 模擬正式 02:00 monitor 排程
TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh monitor --trigger scheduled

# 手動模型重訓
bash scripts/daily_retrain.sh retrain

# 測試 PSI 漂移監控
python app/model_monitor.py
```

詳細說明請參考：[AUTOMATION.md](docs/AUTOMATION.md)

---

## 📱 Web UI 介面

### 快速啟動

```bash
# 本地開發
bash scripts/start_ui.sh

# 開啟瀏覽器
open http://127.0.0.1:5173

# 驗證 API / 前端連線
bash scripts/verify_local_dev_health.sh

# 驗證前端不是空骨架，候補、個股與 K 線資料都有載入
node scripts/verify_frontend_smoke.mjs

# 選用：安裝本機 Web UI launchd agent，讓登入後自動啟動
bash scripts/setup_webui_launchd.sh
```

**功能**:
- 🎯 **今日選股**: 查看 Top 10 推薦與 AI 理由
- 📈 **互動 K 線**: KLineCharts 可拖拉、縮放、切換股票
- 📊 **回測摘要**: 只讀呈現回測 artifact，不在 UI 觸發回測
- 🔍 **市場狀態**: 顯示風險調整後排名與市場 regime

詳細說明請參考：[WEBUI.md](docs/WEBUI.md)

---

## 核心功能

### Agent A｜盤後資料整備系統

完整的台股盤後資料處理系統，整合技術指標、量能分析與基本面訊號：

- **資料擷取**：從 TWSE（上市）、TPEX（上櫃）自動下載近 3 年日行情
  - Yahoo Finance 備援機制
  - 自動容錯與資料來源記錄
  - 處置股與全額交割股清單
  
- **技術指標計算**：
  - 趨勢指標：MA5/10/20/60、EMA12/26
  - 動量指標：RSI、MACD、KD
  - 波動指標：布林通道
  - 前高突破旗標

- **量能分析**：
  - 平均成交量與量比（5/10/20 日）
  - OBV（能量潮指標）
  - 近 20 日日均成交值

- **基本面整合**：
  - 月營收 YoY/MoM
  - 近四季 EPS、ROE、毛利率
  - 殖利率

- **風險過濾機制**：
  - 剔除處置股、全額交割股
  - 上市滿 60 日
  - 近 20 日日均成交值 ≥ 1000 萬
  - 股價 ≥ 10 元

- **自動化報告**：
  - ETL 執行報告（缺值率、資料來源統計）
  - 訊號預覽圖（K 線 + 技術指標 + 成交量）

### 選股系統（開發中）

- **機器學習模型**：使用 LightGBM/XGBoost 預測股價走勢
- **自動選股**：根據模型預測與技術指標篩選前 10 支股票
- **視覺化介面**：透過 React + KLineCharts 呈現選股結果與互動 K 線

## 技術棧

- **資料處理**：pandas, numpy, pyarrow, duckdb
- **技術分析**：ta (Technical Analysis Library)
- **機器學習**：scikit-learn, lightgbm, xgboost
- **視覺化**：matplotlib, KLineCharts, React
- **資料擷取**：requests

## 開發規範

- 使用 `uv` 管理 Python 環境，避免污染系統環境
- 所有程式碼註解與文件使用繁體中文
- Git commit messages 使用繁體中文台灣用語

## 授權

本專案僅供個人學習與研究使用。

## 注意事項

> [!WARNING]
> 本系統產生的選股結果僅供參考，不構成投資建議。投資有風險，請謹慎評估。
