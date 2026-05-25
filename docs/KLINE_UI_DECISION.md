# K 線 UI 技術決策

## 結論

新版主線採用 `React + KLineCharts + FastAPI`，不再把 Streamlit 視為長期 UI 方向。

## 為什麼不是 Streamlit

- Streamlit 適合快速資料展示，但不適合做長期看盤體驗。
- K 線互動、技術指標、滑動縮放與多 pane 管理會越寫越像前端框架。
- 現有專案已經出現三套圖表：Plotly、mplfinance、手刻 matplotlib，維護成本會持續上升。

## 為什麼選 KLineCharts

- 它是偏交易圖表的元件，不是一般圖表庫。
- MA、BOLL、VOL、MACD、KDJ 等指標可直接掛載。
- 前端可以逐步做成真正的研究/看盤桌面，不被 Streamlit layout 綁住。

## 架構邊界

- Python pipeline：保留，繼續負責資料擷取、特徵、模型、排名、報告。
- FastAPI：薄 API，只讀取既有 parquet/csv，轉成前端 JSON。
- React UI：負責互動、圖表、股票切換與決策體驗。
- 舊 Streamlit：已退役；`scripts/start_ui.sh` 僅保留為新版 UI 相容入口。

## 下一步

1. 先讓 `web/frontend` 顯示 Top10 與單股 K 線。
2. 再補交易計畫、模型理由、風險條件 overlay。
3. 持續整理 `chart_generator.py`、`visualization.py` 與報告產物職責。
