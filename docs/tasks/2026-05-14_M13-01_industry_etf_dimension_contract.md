# M13-01：產業與 ETF 維度資料契約

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M13-01`
卡片類型｜派工對象：資料契約 / 維度建模｜另一個 coding model
請讀：`docs/tasks/2026-05-12_GLOBAL_REWRITE_DIRECTIVE.md`、`app/modeling/feature_contract.py`、`app/data/market_repository.py`、`app/contracts/market.py`、`scripts/verify_data_contracts.py`
任務目的：建立「產業分類」與「ETF 關聯」的穩定本地資料契約，讓後續 ranking / UI / 分析可以使用，不在 API request path 即時抓外部資料。
證據路徑：新增或更新 `scripts/verify_data_contracts.py`，並提供一份小型 fixture/mapping 檔。

## 背景

目前 `features.parquet`、`universe.parquet`、ranking artifact 都沒有 `industry / sector / ETF` 欄位。只有股票名稱 mapping，不能做產業集中度、產業 breadth 或 ETF 曝險分析。

這張卡只建立資料契約與讀取層，不做排名加權。

## 建議資料形狀

建立本地 mapping，例如：

- `data/reference/stock_industry_map.csv`
- `data/reference/stock_etf_exposure.csv`

`stock_industry_map.csv` 建議欄位：

- `stock_id`
- `industry_code`
- `industry_name`
- `sector_name`
- `market_type`
- `theme_tags`
- `source`
- `updated_at`

`stock_etf_exposure.csv` 建議欄位：

- `stock_id`
- `etf_id`
- `etf_name`
- `weight`
- `is_major_holding`
- `source`
- `updated_at`

## 範圍

- 新增 repository，例如 `app/data/reference_repository.py`。
- 新增 contract，例如 `app/contracts/reference.py` 或擴充 market contract。
- API/read service 不可即時外部抓取，只讀本地 mapping。
- 若 mapping 缺資料，回傳 `available=false` 或 `null`，不可讓 ranking/API 500。
- 補 validator 檢查：
  - `stock_id` 格式合理。
  - `industry_code/name` 不為空。
  - ETF weight 在 `0~1`。
  - 同一 `stock_id + etf_id` 不重複。

## 不做

- 不把產業/ETF 維度加進 ranking score。
- 不訓練模型。
- 不抓外部即時資料。

## 驗收

- 可以用 service/API 讀出任一股票的產業資訊與 ETF exposure。
- mapping 不存在時，系統仍可正常啟動與查 ranking/detail。
- `verify_data_contracts.py` 有 regression 覆蓋 mapping schema。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile app/data/reference_repository.py app/contracts/reference.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

## 完成紀錄（2026-05-17）

- 本地 mapping 已存在：
  - `data/reference/stock_industry_map.csv`
  - `data/reference/stock_etf_exposure.csv`
  - `data/reference/stock_concept_membership.csv`
  - `data/reference/tradable_universe.csv`
- 讀取層已存在：`app/data/reference_repository.py`
- 契約層已存在：`app/contracts/reference.py`
- validator 已覆蓋 schema、duplicate、ETF weight 範圍、concept confidence 範圍、API/service smoke。
- API request path 僅讀本地 reference mapping，沒有即時外部抓取。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python -m py_compile app/data/reference_repository.py app/contracts/reference.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `reference_industry: rows=19, path=True`
- `reference_etfs: rows=9, path=True`
- `reference_concepts: rows=13753, path=True`
- `tradable_universe: rows=1967, path=True`
- `industry_valid=True unique=True nonblank=True`
- `etf_valid=True unique=True weight_range=True`
- `concept_valid=True nonblank=True confidence_range=True`
- `/api/stocks/{stock_id}/detail`、`/api/stocks/{stock_id}/reference`、`/api/rankings/latest`、`/api/weekly-candidates` smoke 均為 200。
- invalid stock id smoke 為 422；missing detail smoke 為 200 且不阻塞 detail contract。

## Review 重點

- 是否把外部抓取塞進 API request path。
- ETF weight 是否可能超過合理範圍。
- 缺 mapping 時是否會讓個股頁或 ranking API 壞掉。
