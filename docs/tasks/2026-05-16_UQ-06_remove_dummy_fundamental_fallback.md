# UQ-06：移除 FundamentalStage Dummy Fallback

任務ID：`UQ-06`
卡片類型｜派工對象：資料管線安全修復｜Codex
請讀：`app/pipeline/fundamental_stage.py`、`app/fundamental_data.py`、`scripts/verify_model_foundation.py`
任務目的：修掉營收資料缺失時自動產生虛擬基本面欄位的問題，避免假資料污染 features、ranking 與模型評估。
證據路徑：更新 `app/pipeline/fundamental_stage.py`、`scripts/verify_model_foundation.py`。

## 背景

UQ-03 發現 `FundamentalStage` 在月營收缺失或 fetch 失敗時會呼叫 `create_dummy_fundamental_data()`。這會產生隨機 `revenue_yoy / revenue_mom / eps_4q / roe / gross_margin / dividend_yield`，違反 No Vibe Coding，也會污染 ranking 解釋與模型特徵。

## 範圍

- 缺營收時只保留 `revenue_yoy / revenue_mom = NaN`。
- 不再於 production pipeline fallback 隨機 EPS / ROE / 毛利率。
- 保留 `create_dummy_fundamental_data()` 作為明確測試工具，不由 pipeline 自動呼叫。
- 補 smoke test，防止 regression。

## 不做

- 不實作完整月營收抓取。
- 不改 ranking 權重。
- 不覆蓋正式 `data/clean/*.parquet`。

## 驗收

- `FundamentalStage` 空營收時不產生 `eps_4q / roe / gross_margin / dividend_yield`。
- context stats 明確標記缺營收，不宣稱 dummy success。
- `scripts/verify_model_foundation.py` 通過。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 更新：`app/pipeline/fundamental_stage.py`
- 更新：`scripts/verify_model_foundation.py`
- 更新：`scripts/probe_universe_rebuild.py`

## 結果

- `FundamentalStage` 在缺營收來源、空營收、或營收處理 exception 時，都只保留 `revenue_yoy / revenue_mom = NaN`。
- production pipeline 不再自動呼叫 `create_dummy_fundamental_data()`。
- `context['stats']['revenue']` 會保留 `dummy_used=false` 與狀態。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：

- `verify_model_foundation.py` 通過，`MODEL_FOUNDATION_OK specs=11`。
- `verify_data_contracts.py` 通過。
