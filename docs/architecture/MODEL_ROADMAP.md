# 模型底座路線圖

## 目標

把選股系統拆成可獨立訓練、驗證、回測與監控的模型層。UI 只讀結果，不直接耦合演算法。

## 外部研究吸收

### taiwan-stock-analysis

用途：補強基本面品質模型。

- 可吸收：Goodinfo 三張表、ROE/ROA/毛利率/負債比率/FCF、合理性檢查、MOPS provenance。
- 不直接搬：HTML template 與 Claude Skill 工作流。
- 接入方式：先進 `app.fundamentals`，只產 JSON/metrics，再由 API 與 UI 使用。
- 目前底座：`/api/stocks/{stock_id}/fundamentals` 只讀本地 cache，不即時爬外部網站。

### machine-learning-for-trading

用途：補強研究與驗證方法論。

- 可吸收：ML4T workflow、alpha factor research、IC/turnover、walk-forward、out-of-sample prediction、backtest bias guard。
- 不直接搬：notebook 與大型依賴環境。
- 接入方式：讓每個模型都有輸入/輸出契約、驗證閘門、回測證據與監控。

## 模型分層

| ID | 模型 | 層級 | 狀態 | 輸出 |
|---|---|---|---|---|
| M1 | 技術因子模型 | factor | active | MA、RSI、MACD、突破、量價 |
| M2 | 基本面品質模型 | factor | scaffolded | ROE、ROA、毛利率、FCF、負債 |
| M3 | 事件訊號模型 | signal | active | events、positive/risk signals |
| M4 | 報酬預測模型 | prediction | active | model_prob、expected_return |
| M5 | 市場狀態模型 | risk | active_thin | regime、risk_multiplier |
| M6 | 風險模型 | risk | active_thin | risk_penalty、setup_quality |
| M7 | 排名融合模型 | decision | active | risk_adjusted_score |
| M8 | 交易計畫模型 | decision | active_thin | entry、stop、target、sizing |
| M9 | 投組配置模型 | portfolio | planned | position_weight、exposure |
| M10 | 回測評估模型 | evaluation | active_read_only | CAGR、Sharpe、MDD、win rate |
| M11 | 模型監控模型 | monitoring | active_thin | PSI、IC、retrain signal |

## 組裝原則

- 每個模型只能讀自己的明確輸入，輸出標準欄位。
- 需要訓練的模型必須有 walk-forward 或 out-of-sample 驗證。
- 任何新 factor 先跑 IC、coverage、turnover，再考慮進排名權重。
- 回測仍隔離，API/UI 只能讀 artifact，不觸發長任務。
- 基本面爬蟲結果要 cache，不可在排名請求或 UI request 中即時抓外部網站。

## 接下來順序

1. 驗證 M2：挑 1-3 檔股票手動執行 `scripts/import_goodinfo_fundamentals.py`，確認 Goodinfo HTML 解析仍可用。
2. 強化 M11：把 factor monitor 接進 API/UI，並補近期命中率與 alert 門檻。
3. 擴充 M4：技術 + 事件 + 基本面共同訓練。
4. 強化 M7/M8：把分數拆成 prediction、setup、quality、risk。
5. 建立 M9：Top10 權重與總曝險。
