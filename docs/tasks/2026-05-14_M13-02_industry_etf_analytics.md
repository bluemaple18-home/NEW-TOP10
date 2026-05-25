# M13-02：產業與 ETF 分析維度接入

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M13-02`
卡片類型｜派工對象：分析 / ranking artifact｜另一個 coding model
請讀：`docs/tasks/2026-05-14_M13-01_industry_etf_dimension_contract.md`、`app/services/market_service.py`、`app/services/stock_detail_service.py`、`app/trading/ranking_policy.py`、`app/trading/portfolio_policy.py`
任務目的：把產業與 ETF 維度接進 ranking/detail 的分析輸出，先做可觀測與風險揭露，不先改模型權重。
證據路徑：更新 `scripts/verify_review_fixes.py` 或新增 `scripts/verify_industry_etf_dimensions.py`。

## 前置依賴

- 必須先完成 `M13-01`。

## 範圍

- ranking item 補充：
  - `industry_name`
  - `sector_name`
  - `market_type`
  - `theme_tags`
  - `major_etfs`
- Top10 / portfolio summary 可計算：
  - `industry_exposure`
  - `sector_exposure`
  - `etf_overlap_count`
  - `top_industry_concentration`
- 個股 detail 補充：
  - 產業分類區塊。
  - ETF exposure 區塊。
  - 缺資料時顯示 unavailable，不要阻塞 K 線/交易計畫。

## 不做

- 不把產業/ETF 直接加權到 `risk_adjusted_score`。
- 不做 ETF 成分股即時同步。
- 不做產業中性化訓練；這留給下一張模型卡。

## 驗收

- `/api/rankings/latest` 可看到產業與 ETF 欄位，舊 artifact 缺欄位時可 fallback。
- `/api/stocks/{stock_id}/detail` 可看到產業/ETF 區塊或 unavailable 狀態。
- Top10 可計算產業集中度，且不影響 `suggested_weight` 加總。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; c=TestClient(app); print(c.get('/api/rankings/latest').status_code); print(c.get('/api/stocks/1101/detail').status_code)"
```

## 完成紀錄（2026-05-17）

- `app/data/reference_repository.py` 提供 `annotate_ranking()`：
  - `industry_code`
  - `industry_name`
  - `sector_name`
  - `market_type`
  - `theme_tags`
  - `major_etfs`
  - `concept_tags`
- `app/services/market_service.py` 在 latest ranking 輸出補 reference annotation 與 `reference_summary`。
- `app/services/stock_detail_service.py` 在個股 detail 補 `reference` section。
- `app/contracts/market.py` 的 `RankingItem` 已加入產業 / ETF / concept 欄位。
- 本卡只做風險揭露與分析可觀測，不把產業 / ETF 欄位加進 `risk_adjusted_score`。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `/api/rankings/latest` smoke status：`200`
- ranking payload 含 `reference_summary`
- ranking item 含 `industry_name` / `major_etfs` / `concept_tags`
- `/api/stocks/{stock_id}/reference` smoke status：`200`
- `/api/stocks/{stock_id}/detail` 含 `reference` section
- missing detail smoke status：`200`，不因缺 mapping 阻塞。

## Review 重點

- 產業/ETF 是先揭露風險，不要偷偷改 ranking score。
- ETF exposure 與 portfolio exposure 不要混成同一個概念。
- 缺 mapping 不得讓 UI 500。
