# UQ-09：TWSE Historical Source Repair

任務ID：`UQ-09`
卡片類型｜派工對象：資料來源 / 歷史行情修復｜Codex
請讀：`app/data_fetcher.py`、`docs/tasks/2026-05-16_UQ-07_staged_real_universe_rebuild.md`、`app/pipeline/validation.py`
任務目的：修復 TWSE 上市歷史日行情來源，讓 real universe 重建不只依賴 TPEx 或已存在殘留資料，並改善 `ma20 / bb_middle` 最新日 coverage warning。
證據路徑：必要腳本、staging artifact、pipeline validate 結果。

狀態：`completed_with_gate`

## 背景

UQ-07 發現本機呼叫 TWSE historical RWD `MI_INDEX` 回 `307`。TWSE OpenAPI `STOCK_DAY_ALL` 可拿最新全市場日行情，但不接受歷史 date。現有 `data/clean` 已用 tradable universe 過濾乾淨，但長週期指標 coverage 仍偏低。

## 範圍

- 找出可用官方 TWSE 歷史資料路徑，或建立明確 fallback 策略。
- 不引入未審核第三方資料。
- 若無官方歷史全市場 endpoint，先讓 pipeline 明確標記 partial source，不誤報 full rebuild。

## 不做

- 不調 ranking 權重。
- 不接基本面分數。
- 不使用付費/券商 API。

## 驗收

- `ma20 / bb_middle` latest coverage warning 被解決，或有明確 partial-source gate 阻止誤判。
- 卡片記錄資料來源限制與下一步。

## 執行紀錄

### 官方來源檢查

- TWSE RWD `afterTrading/STOCK_DAY`：本機呼叫回 `307`，目前不可作為穩定歷史補資料來源。
- TWSE `exchangeReport/STOCK_DAY` 舊路徑：本機呼叫回 `307`，目前不可作為穩定歷史補資料來源。
- TWSE OpenAPI `STOCK_DAY_ALL`：可取最新全市場日行情，但不接受歷史 `date` 查詢，無法補足 `ma20 / bb_middle` 所需長週期資料。

### Gate 修復

- 在 `app/pipeline/validation.py` 新增 market-specific latest coverage gate。
- 目前 `features` 的整體 latest `ma20 / bb_middle` coverage 為 `41.1%`，但 gate 會進一步拆出來源：
  - TPEx latest 長週期 coverage 約 `91.3%`，未低於 warning threshold。
  - TWSE latest 長週期 coverage 為 `0.0%`，明確標記為 `twse 最新日期長週期欄位覆蓋率偏低`。
- 這代表 pipeline 不再把 partial-source rebuild 誤判為完整行情重建；ranking / model 仍可跑，但 TWSE 長週期特徵必須被視為資料來源限制。

### 驗證

- `uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py`
  - `MODEL_FOUNDATION_OK specs=11`
- `uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py`
  - API / reference / tradable universe contracts 通過。
- `uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --data-dir data --json`
  - `ok=true`
  - `ERROR=0`
  - `WARN=4`
  - warning 已包含 TWSE-specific source gate。
- `uv run --with-requirements requirements.txt python -m app.agent_b_ranking`
  - 成功載入 `models/latest_lgbm.pkl`
  - 成功輸出 `artifacts/ranking_2026-05-15.csv`

## 結論

本卡未直接修復 TWSE 歷史資料來源，因為目前沒有可用且已審核的官方歷史 endpoint。已完成 partial-source gate，避免把 TWSE 長週期特徵缺口誤判成模型或 ranking 問題。

## 下一步

- 若要真正消除 warning，需要核准新的 TWSE 歷史資料來源或提供可審核 vendor/source。
- 在此之前，不應用這批低 coverage TWSE 長週期特徵調 ranking 權重。
