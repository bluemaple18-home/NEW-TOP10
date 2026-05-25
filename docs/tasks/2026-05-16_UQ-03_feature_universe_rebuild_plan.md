# UQ-03：Features / Ranking Universe 重建計劃

任務ID：`UQ-03`
卡片類型｜派工對象：資料管線 / 模型輸入｜Codex
請讀：`docs/tasks/2026-05-16_UQ-01_tradable_universe_contract.md`、`docs/tasks/2026-05-16_UQ-02_universe_source_import.md`、`app/modeling/feature_contract.py`、`app/agent_b_ranking.py`、`scripts/run_daily.sh`
任務目的：把目前樣本式 `1101-1200` universe 替換成真實可交易 universe 的重建方案，先產生計劃與小批驗證，不直接覆蓋正式 features/ranking。
證據路徑：新增 `artifacts/universe_rebuild_probe.json`，必要時新增 `scripts/probe_universe_rebuild.py`。

## 背景

基本面 shadow score 顯示目前 universe 品質不足。直接重建全量 features 風險較大，因此先做 probe：確認資料來源、欄位、時間範圍、股票數、缺值狀況與 runtime。

## 範圍

- 找出目前 features/ranking 的 universe 產生入口。
- 設計真實 universe 接入點。
- 小批 5-20 檔 probe，不覆蓋 `data/clean/features.parquet`。
- 輸出重建計劃：需要哪些資料、預估耗時、會更新哪些 artifact。

## 不做

- 不直接覆蓋正式 features/ranking。
- 不修改模型權重。
- 不接基本面分數進 ranking。

## 驗收

- 能明確指出目前 `1101-1200` 是哪個流程或 fixture 產生。
- 有小批重建 probe artifact。
- 有是否可進入全量重建的結論。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/probe_universe_rebuild.py --limit 20
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

## Review 重點

- 是否誤覆蓋正式資料。
- 是否讓 feature schema 漂移。
- 是否保留可回復路徑。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 新增：`scripts/probe_universe_rebuild.py`
- 修正：`app/data_fetcher.py` 的 TPEx 日行情 parser，支援新版 `tables[].data` 回傳格式。
- Probe JSON：`artifacts/universe_rebuild_probe.json`
- Probe parquet：
  - `artifacts/universe_rebuild_probe/features.parquet`
  - `artifacts/universe_rebuild_probe/events.parquet`
  - `artifacts/universe_rebuild_probe/universe.parquet`

## 結果

- 目前正式 `data/clean/features.parquet` / `universe.parquet` 仍是 `1101-1200` 樣本式資料：
  - `features`: rows `30000`、stocks `100`、`looks_like_1101_1200_fixture=true`
  - `universe`: rows `30000`、stocks `100`、`looks_like_1101_1200_fixture=true`
- production pipeline 沒有找到硬編 `1101-1200`；重建入口是：
  - `scripts/run_daily.sh`
  - `scripts/run_automation.py:_run_daily`
  - `app.pipeline_cli: build_pipeline()`
  - `FetchStage -> IndicatorStage -> FundamentalStage -> EventStage -> FilterStage -> ReportStage`
- 小批 probe：
  - sample `20` 檔，TWSE `10` / TPEx `10`
  - raw rows `53214`
  - feature rows `478`
  - feature stocks `20`
  - filtered universe stocks `8`
  - missing sample ids `[]`

## 結論

- 可進入「備份後全量重建」；但本卡沒有覆蓋正式 `data/clean/*.parquet`。
- UQ-04 先用 probe parquet 重跑基本面 shadow score，避免在沒有完整回退策略前覆蓋正式資料。
- 已知風險：`FundamentalStage` 的營收整合目前會 fallback dummy revenue，完整全量重建前應另卡修正。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/probe_universe_rebuild.py --limit 20 --days 35
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

結果：

- `probe_status=OK`
- `verify_data_contracts.py` 通過。
- `verify_model_foundation.py` 通過，`MODEL_FOUNDATION_OK specs=11`。
