# M9-01：Top10 建議權重與最大曝險

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M9-01`
卡片類型｜派工對象：投組配置｜另一個 coding model
請讀：`app/trading/ranking_policy.py`、`app/trading/trade_plan.py`、`app/contracts/market.py`、`app/modeling/registry.py`
任務目的：Top10 不只輸出排序，還要輸出建議權重、單檔上限、總曝險與風險註記。
證據路徑：新增 `app/trading/portfolio_policy.py` 與對應 verify script 或擴充 `scripts/verify_review_fixes.py`。

## 前置依賴

- 必須先完成 `M7-01`，因為權重應使用拆解後的 score 與 risk penalty。

## 範圍

- 建立 portfolio policy，輸入 TopN ranking + market regime + risk metrics，輸出：
  - `suggested_weight`
  - `max_position_weight`
  - `gross_exposure`
  - `cash_weight`
  - `exposure_note`
- 權重預設採保守規則：分數越高權重越高，但受單檔上限、總曝險、市場狀態限制。
- 市場偏空時要降低 gross exposure，不可只調整排序。

## 不做

- 不做完整 portfolio optimizer。
- 不做回測績效計算。
- 不讓 UI 或 API 觸發回測。

## 驗收

- Top10 每檔都有 `suggested_weight`，總和不超過 `gross_exposure`。
- 單檔權重不超過 `max_position_weight`。
- 市場 regime 改變時，總曝險會合理下降或上升。
- Ranking CSV/API 可看到權重欄位。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; r=TestClient(app).get('/api/rankings/latest'); print(r.status_code, r.json().get('items', [])[0].keys())"
```

## 完成紀錄（2026-05-17）

- `app/trading/portfolio_policy.py` 已建立保守 sizing：
  - `suggested_weight`
  - `max_position_weight`
  - `gross_exposure`
  - `allocated_exposure`
  - `cash_weight`
  - `exposure_note`
- `app/contracts/market.py` 的 `RankingItem` 已包含投組欄位。
- `MarketService.latest_ranking()` 會套用 ranking policy 與 portfolio policy，read API 不觸發回測。
- 單檔 cap 與總曝險由 market regime 控制，RISK_OFF 會降低 gross exposure。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `REVIEW_FIXES_OK`
- `/api/rankings/latest` smoke status：`200`
- `verify_portfolio_policy_allocation_caps()` 覆蓋權重加總與單檔上限。

## Review 重點

- 權重是否可能加總超過曝險上限。
- 高分但高風險股票是否仍被限制權重。
- 是否把回測或長任務塞進 ranking/API read path。
