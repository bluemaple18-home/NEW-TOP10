# M13-04：本地產業 reference mapping 覆蓋率補齊

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M13-04`
卡片類型｜派工對象：資料契約 / reference quality｜Codex
請讀：`docs/tasks/2026-05-14_M13-03_industry_neutral_research.md`、`data/reference/stock_concept_membership.csv`、`data/reference/tradable_universe.csv`、`app/data/reference_repository.py`
任務目的：用已落地的本地 concept industry membership 補齊 `stock_industry_map.csv`，降低 `code_prefix_fallback` 與 missing mapping，讓產業風險揭露與後續分群研究有穩定 reference 基礎；此 mapping 是本地 reference，不宣稱為交易所權威產業分類。
證據路徑：`scripts/build_stock_industry_map_from_concepts.py`、`artifacts/stock_industry_map_build_summary.json`、`scripts/verify_data_contracts.py`。

## 背景

`M13-03` 初版研究發現正式 industry mapping 覆蓋率不足。修正覆蓋率算法後確認：

- 舊 `stock_industry_map.csv` 只有 19 筆。
- 本地 reference mapping 覆蓋率僅約 0.58%。
- 多數樣本為 missing 或 `code_prefix_fallback`，不足以支撐後續產業模型研究。

同時本地已存在 `stock_concept_membership.csv`，其中 `concept_type=industry` 已覆蓋 active tradable universe，可離線整理成本地 reference mapping。

## 範圍

- 新增 `scripts/build_stock_industry_map_from_concepts.py`。
- 只讀本地：
  - `data/reference/stock_concept_membership.csv`
  - `data/reference/tradable_universe.csv`
- 產出/覆寫：
  - `data/reference/stock_industry_map.csv`
  - `artifacts/stock_industry_map_build_summary.json`
- 每檔 active stock 取一個最適產業分類：
  - 優先較細的 `電子產業 / ...`
  - 其次 `上市類股 / ...` 或 `上櫃類股 / 櫃...`
- 補 `sector_name`、`theme_tags`、`market_type`、`source`、`updated_at`。

## 不做

- 不抓外部即時資料。
- 不改 ranking score。
- 不改模型訓練欄位。
- 不把 ETF exposure 混成 portfolio exposure。

## 完成紀錄

- `stock_industry_map.csv` 從 19 筆補齊到 1967 筆。
- active tradable stock 覆蓋率：100%。
- 產業數：67。
- sector 數：9。
- source：`concept_industry_yahoo`。
- M13-03 研究報告已重跑，本地 reference mapping 覆蓋率改為 100%，缺 mapping 或 prefix fallback 比例為 0%。

## 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/build_stock_industry_map_from_concepts.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/research_industry_etf_risk.py
uv run --with-requirements requirements.txt python -m py_compile scripts/build_stock_industry_map_from_concepts.py scripts/research_industry_etf_risk.py
```

結果：通過。

重點輸出：

- `STOCK_INDUSTRY_MAP_BUILD_OK rows=1967 coverage=100.00%`
- `reference_industry: rows=1967, path=True`
- `industry_valid=True unique=True nonblank=True`
- `/api/rankings/latest` smoke status：`200`
- `/api/stocks/{stock_id}/detail` smoke status：`200`
- `INDUSTRY_ETF_RISK_RESEARCH_OK`

## Review 重點

- 產業 mapping 是本地 reference 整理，不是 request path 外部抓取。
- sector 分類是保守 keyword mapping，僅供風險揭露與研究分群，尚不進模型權重。
- 下一步若要做 `industry_momentum / sector_rotation`，需另開研究與回測驗證卡。

## Review 修正紀錄（2026-05-18）

- 修正 weekly candidate 文案語意：`primary_reasons` 不再輸出 `{industry} 共振`。
- 產業分類保留在 ranking item、`dominant_groups` 與 reference summary，避免把 `risk_disclosure_only` 誤讀成已驗證的產業動能訊號。
- `scripts/verify_data_contracts.py` 已新增 regression：`weekly_primary_reasons_no_industry_signal=True`。
