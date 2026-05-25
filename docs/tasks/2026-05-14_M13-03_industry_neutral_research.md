# M13-03：產業中性化與 ETF 風險研究

狀態：`completed`
前置狀態：`M13-01 completed`、`M13-02 completed`
完成日期：`2026-05-17`

任務ID：`M13-03`
卡片類型｜派工對象：研究 / 模型評估｜另一個 coding model
請讀：`docs/tasks/2026-05-14_M13-02_industry_etf_analytics.md`、`app/monitoring/factor_monitor.py`、`app/agent_b_modeling.py`、`docs/architecture/MODEL_ROADMAP.md`
任務目的：研究產業維度是否應進入模型與排名，先產生證據，不直接拍腦袋改權重。
證據路徑：產出 research artifact 或 monitor 報告，並更新模型 roadmap。

## 前置依賴

- 必須先完成 `M13-01`、`M13-02`。

## 範圍

- Factor IC 增加產業分組觀察：
  - overall IC
  - by-industry IC
  - industry-neutral IC
- Top10 concentration 監控：
  - 單一產業曝險過高 warning。
  - ETF overlap 過高 warning。
- 研究以下特徵是否有用：
  - `industry_breadth_ma20`
  - `industry_momentum_20d`
  - `industry_relative_strength`
  - `sector_rotation_score`
  - `etf_overlap_risk`

## 不做

- 不直接改 M7/M9 權重。
- 不訓練正式模型，除非另開 M4/M7 卡。

## 驗收

- 產出一份明確研究結果：哪些產業/ETF 維度值得進模型，哪些只適合 UI/風險揭露。
- 若要進 ranking，需提出下一張卡的權重/驗證方案。

## 完成紀錄（2026-05-17）

- 新增 `scripts/research_industry_etf_risk.py`，只產生研究證據，不修改模型、ranking 權重或正式資料。
- 產出：
  - `artifacts/industry_etf_risk_research.json`
  - `artifacts/industry_etf_risk_research.md`
- 研究內容：
  - Top10 產業集中度。
  - ETF overlap count。
  - industry source 覆蓋率。
  - overall IC / by-industry IC / industry-neutral IC。
- 研究結論：目前維持 `risk_disclosure_only`。產業與 ETF 維度適合先做 UI/風險揭露，不直接進模型或 ranking 權重。
- 後續補強：`M13-04` 已用本地 concept industry membership 補齊本地 reference mapping；目前可支撐風險揭露與分群研究，但仍不得直接改模型或 ranking 權重。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_etf_risk.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_etf_risk.py
```

結果：通過。

重點輸出：

- `INDUSTRY_ETF_RISK_RESEARCH_OK`
- 有效標籤樣本：`95632`
- latest ranking date：`2026-05-15`
- top industry concentration：`0.695231`
- ETF overlap count：`0`
- 本地 reference mapping 覆蓋率（不含 missing / prefix fallback）：`100.00%`
- 缺 mapping 或 prefix fallback 比例：`0.00%`
- 研究決策：`risk_disclosure_only`

## Review 重點

- 是否有 lookahead bias。
- 是否把產業分類缺失當成有效訊號。
- 是否有足夠樣本數支撐 by-industry IC。
