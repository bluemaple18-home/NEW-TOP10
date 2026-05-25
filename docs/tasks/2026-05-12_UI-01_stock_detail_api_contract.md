# UI-01：個股詳情後端 contract/API

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`UI-01`
卡片類型｜派工對象：API / contract｜另一個 coding model
請讀：`app/contracts/market.py`、`app/contracts/fundamental.py`、`app/contracts/backtest.py`、`app/services/market_service.py`、`app/services/backtest_service.py`、`app/api/routers/market.py`
任務目的：提供個股頁四區所需的穩定後端資料，不讓前端直接拼多個內部格式。
證據路徑：新增 API smoke 測試或擴充 `scripts/verify_data_contracts.py`。

## 前置依賴

- 建議等 `M7-01`、`M9-01` 完成後再做，因為交易計畫與權重欄位會更完整。

## 範圍

- 建立個股詳情 response contract，至少包含：
  - K 線：既有 OHLCV / indicator series。
  - 基本面：只讀 cache 的 fundamental summary。
  - 交易計畫：entry、stop、target、risk_reward、suggested_weight、max exposure。
  - 回測證據：只讀已存在 artifact 的 summary 或 unavailable 狀態。
- API 可以是新 endpoint，例如 `/api/stocks/{stock_id}/detail`。
- 若某區資料不存在，回 `available=false` 或空狀態，不要 500。

## 不做

- 不改前端 layout。
- 不在 API 中即時跑回測。
- 不在 API 中即時抓 Goodinfo。

## 驗收

- 新 endpoint 可用 FastAPI TestClient smoke。
- 四區資料都有明確 contract；缺資料時也有可渲染狀態。
- 既有 `/api/stocks/{stock_id}/ohlcv` 與 `/api/stocks/{stock_id}/fundamentals` 不壞。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile app/api/main.py app/contracts/market.py app/services/market_service.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; c=TestClient(app); print(c.get('/api/stocks/1101/detail').status_code)"
```

## 完成紀錄（2026-05-17）

- `app/contracts/stock_detail.py` 已定義個股詳情四區 contract。
- `app/services/stock_detail_service.py` 已聚合：
  - K 線 / 型態訊號 / overlay。
  - 基本面 cache summary。
  - 交易計畫與投組權重欄位。
  - 系統層回測 artifact summary。
  - reference 產業 / ETF / 概念資料。
- `app/api/routers/stock_detail.py` 提供：
  - `/api/stocks/{stock_id}/detail`
  - `/api/stocks/{stock_id}/reference`
- 缺股票、缺基本面、缺回測時回 `available=false` 或可渲染狀態，不讓 API 500。
- API 不即時跑回測、不即時抓 Goodinfo。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `stock_detail: status=200, stock_id=1101`
- `price / reference / fundamentals / trade_plan / backtest` 均有 `available` contract。
- `ohlcv: status=200`
- `fundamentals: status=200`
- `missing_detail: status=200`
- `invalid_detail: status=422`
- `reference: status=200`

## Review 重點

- 回測資料是否仍隔離且只讀 artifact。
- 缺基本面或缺回測時是否可正常回傳。
- contract 是否過度暴露 DataFrame/raw artifact 內部欄位。
