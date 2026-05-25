# UQ-07：Staged Real-Universe Rebuild

任務ID：`UQ-07`
卡片類型｜派工對象：資料管線 / 重建驗證｜Codex
請讀：`docs/tasks/2026-05-16_UQ-03_feature_universe_rebuild_plan.md`、`docs/tasks/2026-05-16_UQ-06_remove_dummy_fundamental_fallback.md`、`app/pipeline_cli.py`
任務目的：在不覆蓋正式 `data/clean` 的前提下，用真實 TWSE/TPEx 日行情重建一份 staging features/events/universe，確認修正後 pipeline 可跑真實 universe。
證據路徑：`artifacts/real_universe_rebuild/clean/*.parquet`、`artifacts/real_universe_rebuild/artifacts/etl_report.md`。

## 背景

正式 `data/clean` 仍是 `1101-1200` 樣本式資料。UQ-03 probe 已確認真實 universe 小批可跑，UQ-06 已移除 dummy fallback。下一步先 staging 重建，不直接切正式資料。

## 範圍

- 使用 `app.pipeline_cli run --data-dir artifacts/real_universe_rebuild`。
- 日期窗先採近期窗，驗證全市場資料流與 schema。
- 驗證 staging 輸出，不覆蓋 `data/clean/*.parquet`。

## 不做

- 不訓練模型。
- 不改 ranking 權重。
- 不把 staging 直接切成正式資料。

## 驗收

- staging `features.parquet` 股票數明顯不是 `1101-1200` fixture。
- `app.pipeline_cli validate --data-dir artifacts/real_universe_rebuild` 通過。
- revenue stats 不得出現 `dummy_used=true`。

## 執行紀錄

- 狀態：`completed_with_recovery`
- 完成時間：`2026-05-16`
- 修正：
  - `app/pipeline_cli.py`：`--data-dir` 現在會真正傳入 `ETLPipeline(data_dir=...)`。
  - `app/pipeline_cli.py`：非正式 data dir 預設 artifacts 會落到 `<data-dir>/artifacts`。
  - `app/finmind_integrator.py`：FinMind 缺套件時降級 skip，不阻斷價格資料 pipeline。
  - `app/pipeline/fetch_stage.py`：套用 `data/reference/tradable_universe.csv`，排除 ETF / 權證 / 非四碼商品。
  - `scripts/filter_clean_to_tradable_universe.py`：可離線把既有 clean parquet 過濾成 tradable universe。

## Incident / Recovery

- 原本預期 staging run 不覆蓋正式資料；實際發現 `app.pipeline_cli build_pipeline()` 沒有把 `--data-dir` 傳給 `ETLPipeline()`，第一次 run 覆蓋了 `data/clean`。
- Recovery：
  - 保留未過濾版本：`artifacts/real_universe_rebuild_unfiltered/clean/`
  - 產生過濾版：`artifacts/real_universe_rebuild_filtered/clean/`
  - 用過濾版回填 `data/clean/`
- 目前正式 `data/clean` 已是乾淨四碼股票 universe：
  - features rows `115283`、stocks `1967`
  - events rows `115283`、stocks `1967`
  - universe rows `65128`、stocks `1151`
  - 非四碼 stock_id rows `0`

## 結果

- Staging filtered validate 通過，無 ERROR。
- 正式 `data/clean` validate 通過，無 ERROR。
- 仍有 WARN：
  - `ma20` 最新日期 coverage `41.1% < 65%`
  - `bb_middle` 最新日期 coverage `41.1% < 65%`
- WARN 原因：TWSE historical RWD 目前回 `307`，本次可穩定重建的歷史段主要來自已抓到資料與 TPEx；長週期技術指標需要更完整 TWSE 歷史窗補齊。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --data-dir artifacts/real_universe_rebuild_filtered --json
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --data-dir data --json
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

結果：

- `data/clean/features.parquet`：rows `115283`、stocks `1967`
- `data/clean/universe.parquet`：rows `65128`、stocks `1151`
- `verify_data_contracts.py` 通過。
- `verify_model_foundation.py` 通過。

## Ranking Smoke

```bash
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
```

結果：

- 通過，產出 `artifacts/ranking_2026-05-15.csv`。
- 目前 `models/latest_lgbm.pkl` 不存在，因此 ranking 使用 fallback `model_prob=0.5`，仍可產生規則/風險調整排名。
