# UQ-02：Universe 來源匯入與失敗紀錄

任務ID：`UQ-02`
卡片類型｜派工對象：離線資料匯入｜Codex
請讀：`docs/tasks/2026-05-16_UQ-01_tradable_universe_contract.md`、`config/reference_sources.yaml`、`scripts/import_reference_sources.py`、`scripts/probe_reference_sources.py`
任務目的：建立可重跑的離線 universe 匯入流程，把真實上市櫃股票清單寫入 `data/reference/tradable_universe.csv`，並保留來源、成功數、失敗原因。
證據路徑：新增或更新 `scripts/import_tradable_universe.py`、`artifacts/tradable_universe_import_summary.json`。

## 背景

目前 features/ranking 使用樣本代號，導致 Goodinfo 財報 coverage 與模型評估不可信。必須先有穩定 universe 匯入來源，再談重建資料與 ranking。

## 範圍

- 寫一個離線 CLI 匯入入口。
- 匯入後輸出 summary artifact：
  - 來源 URL / 檔案
  - 成功筆數
  - 無效代號筆數
  - 去重筆數
  - 更新時間
- 匯入腳本可重跑，且不破壞既有 reference mapping。
- 若外部來源失敗，回報清楚錯誤並保留上一版本地檔。

## 不做

- 不在 UI/API 即時抓。
- 不重建 feature pipeline。
- 不篩選 Top10。

## 驗收

- `data/reference/tradable_universe.csv` 有真實可交易股票清單。
- summary artifact 可說明資料來源與失敗狀況。
- `scripts/verify_data_contracts.py` 通過。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/import_tradable_universe.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

## Review 重點

- 匯入失敗時是否覆蓋掉好資料。
- source / updated_at 是否保留。
- 是否把 ETF 與個股混成同一個無標記池。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 新增：`scripts/import_tradable_universe.py`
- 更新輸出：`data/reference/tradable_universe.csv`
- Summary：`artifacts/tradable_universe_import_summary.json`
- Raw evidence：
  - `data/raw/reference/tradable_universe/2026-05-16/twse_openapi.json`
  - `data/raw/reference/tradable_universe/2026-05-16/tpex_openapi.json`

## 結果

- TWSE OpenAPI：raw `1086`、valid `1080`、invalid `6`
- TPEx OpenAPI：raw `887`、valid `887`、invalid `0`
- 合併後 universe：`1967` 檔，無 duplicate removed。
- `data/reference/tradable_universe.csv` 欄位符合 UQ-01 契約：`stock_id / stock_name / market_type / is_etf / is_active / source / updated_at`。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/import_tradable_universe.py --dry-run
uv run --with-requirements requirements.txt python scripts/import_tradable_universe.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

結果：

- `verify_data_contracts.py` 通過，`tradable_universe: rows=1967`。
- `verify_model_foundation.py` 通過，`MODEL_FOUNDATION_OK specs=11`。
