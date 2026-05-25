# UQ-01：可交易台股 Universe 資料契約

任務ID：`UQ-01`
卡片類型｜派工對象：資料契約 / Universe 修正｜Codex
請讀：`AGENTS.md`、`docs/architecture/UI_REFACTOR_ARCHITECTURE.md`、`docs/architecture/TRADING_DECISION_LAYER.md`、`app/data/market_repository.py`、`scripts/verify_data_contracts.py`
任務目的：建立「真實可交易台股清單」的本地資料契約，取代目前 `1101-1200` 這種樣本式 universe 對基本面與 ranking 評估造成的污染。
證據路徑：新增或更新 `data/reference/tradable_universe.csv`、`app/data/reference_repository.py`、`scripts/verify_data_contracts.py`。

## 背景

FQ shadow score 評估發現目前 `features.parquet` 的 universe 是 `1101-1200`，其中大量代號無 Goodinfo 近期財報或不是有效上市櫃標的，導致基本面可評分 coverage 只有 8%。在修正 universe 前，不應把基本面分數接入 ranking 權重。

## 建議資料形狀

`data/reference/tradable_universe.csv`：

- `stock_id`
- `stock_name`
- `market_type`：`twse` / `tpex`
- `is_etf`
- `is_active`
- `source`
- `updated_at`

## 範圍

- 定義本地 universe schema。
- 建立 validator：四位數股票代號、名稱不空、market type 合法、`stock_id` 不重複。
- repository/service 只能讀本地檔，不在 API request path 即時抓外部資料。
- 若檔案缺失，系統仍可回報 `available=false` 或 fallback，不可讓 ranking/detail API 500。

## 不做

- 不重建 features.parquet。
- 不改 ranking 權重。
- 不做基本面 score 接入。

## 驗收

- `verify_data_contracts.py` 能驗證 `tradable_universe.csv` schema。
- 任一合法股票可以查到 universe metadata。
- 缺檔或空檔不會讓 API 啟動失敗。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/build_fundamental_shadow_scores.py --horizon 10
```

## Review 重點

- 是否把外部抓取塞進 API request path。
- 是否允許非股票代號或樣本代號污染 universe。
- 缺資料時是否有清楚 fallback。

## 執行紀錄

狀態：`completed`

完成內容：

- 新增 `data/reference/tradable_universe.csv` 作為最小 seed 與 schema anchor。
- 新增 `TradableUniverseItem` / `TradableUniverseResponse` contract。
- 擴充 `ReferenceRepository`：
  - `load_tradable_universe()`
  - `tradable_universe()`
  - `tradable_universe_item()`
- 擴充 `scripts/verify_data_contracts.py` 驗證：
  - 四位數股票代號。
  - `stock_id` 不重複。
  - `stock_name` 不空。
  - `market_type` 僅允許 `twse / tpex`。

驗證結果：

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

兩者皆通過。

目前限制：

- `tradable_universe.csv` 仍是 manual seed，不是完整上市櫃清單。
- 全量匯入交給 `UQ-02`。
