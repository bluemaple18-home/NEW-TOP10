# M7-01：排名融合分數拆解

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M7-01`
卡片類型｜派工對象：決策層重構｜另一個 coding model
請讀：`app/trading/ranking_policy.py`、`app/agent_b_ranking.py`、`app/contracts/market.py`、`docs/architecture/TRADING_DECISION_LAYER.md`
任務目的：把 `final_score` 的決策語意拆成 `prediction_score + setup_score + quality_score - risk_penalty`，讓排序原因可解釋且可監控。
證據路徑：新增或更新 `scripts/verify_review_fixes.py`，並保留 ranking CSV/API smoke output。

## 前置依賴

- 建議等 `M4-02` 完成後再做，避免 prediction 欄位命名反覆改。

## 範圍

- `prediction_score`：來自模型機率或 expected return，需保留舊 `model_prob` 相容。
- `setup_score`：技術型態與事件訊號，例如突破、均線、量能、風險事件。
- `quality_score`：基本面品質與流動性品質，不可和 setup 混在一起。
- `risk_penalty`：市場狀態、波動、流動性不足、風險訊號造成的扣分。
- `risk_adjusted_score` 或新的排序欄位必須可由上述分數清楚推導。

## 不做

- 不用主觀拍腦袋大改權重；若有權重，需先用保守預設並標註待回測。
- 不做投組權重，留給 `M9-01`。
- 不移除舊欄位，避免 UI/API 斷線。

## 驗收

- Ranking CSV 至少包含：`prediction_score`、`setup_score`、`quality_score`、`risk_penalty`、`risk_adjusted_score`。
- `/api/rankings/latest` contract 可回傳新欄位，且舊 UI 仍可讀。
- 排序邏輯有單元或回歸測試覆蓋極端 case：高 prediction 但高 risk penalty 不應無條件排第一。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; r=TestClient(app).get('/api/rankings/latest'); print(r.status_code, len(r.json().get('items', [])))"
```

## 完成紀錄（2026-05-17）

- `app/trading/ranking_policy.py` 已拆出：
  - `prediction_score`
  - `setup_score`
  - `quality_score`
  - `risk_penalty`
  - `risk_adjusted_score`
- `app/contracts/market.py` 的 `RankingItem` 已保留舊欄位並新增拆解欄位。
- `MarketService.latest_ranking()` 可 backfill score decomposition，讓舊 ranking artifact 仍可讀。
- `quality_score` 目前依 UQ-05 / UQ-10 gate 只保留流動性品質；基本面未通過證據前不進 ranking score。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `REVIEW_FIXES_OK`
- `/api/rankings/latest` smoke status：`200`
- ranking item contract 已覆蓋 `industry_name` / `major_etfs` / `concept_tags` 與 score 欄位相容。

## Review 重點

- 是否保留舊欄位相容。
- 是否把 risk 寫成乘數黑盒，導致無法解釋。
- 是否把基本面品質和技術 setup 混成同一個分數。
