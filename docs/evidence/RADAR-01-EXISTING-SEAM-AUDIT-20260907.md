# RADAR-01 Existing Seam Audit

- 日期：2026-09-07
- 稽核基準：local `main@502bfc2`
- 裁決：`MEASURED_GAP_CONFIRMED / READY_FOR_OWNER_ADMISSION_DECISION / NOT_ADMITTED`

👉 [假設與目標確認] 目標：確認 finalized Daily Close 到 SignalSpec、SignalOccurrence、研究統計與 Radar projection 的既有 seam 與實際缺口；邊界：唯讀稽核，不建立 implementation card，不改 ranking、Research Spine、scheduler、provider、production 或外部系統；驗收：資料粒度、鍵、語意漂移、缺資料行為、可重用元件與最小後續切片都有可重跑證據。

## 1. 結論

RADAR-01 的產品需求有真實 measured gap，但目前沒有 implementation authority。

現有程式已提供四種可延伸材料：ME-D1 finalized Daily Close snapshot、既有 deterministic indicator/event 計算、Research Ledger／regime research contracts，以及一個 closed-schema、research-only 的 Market Flow Radar read-model 範例。然而它們尚未形成 RADAR-01 所需的單一可追溯鏈，而且代表性本機資料已證實同名訊號在兩條計算路徑發生語意漂移。

因此不能把目前的 `events.parquet`、個股詳情 pattern signals 或 `config/signals.yaml` scoring weights 直接宣告為 Radar authority。Owner 若要繼續，應只先 admission `P1-A Signal Catalog / SignalSpec + observability contract`；P1-B 至 P1-E 仍各自維持未准入。

## 2. 資料契約與代表性資料

### 2.1 上游 authority

- `app/pipeline/daily_close_snapshot.py` 已提供 `daily-close-snapshot.v1`：不可變 records、content identity、finalization authority、TWSE/TPEX coverage 與 `(date, stock_id)` 驗證。
- `app/pipeline/fetch_stage.py` 在 provider fetch 後立即 materialize 並 reload snapshot，之後才進行 tradable filter、籌碼整合與 indicator enrichment。
- `app/research/dataset_bundle.py` 與 `app/research/run_receipts.py` 可重用作 DatasetSnapshot／evidence reference binding；不需要新增第二套 ledger。

### 2.2 本機代表性 clean artifacts

唯讀 probe：

```text
features.parquet
  rows=516,169
  grain=(trading_date, stock_id)
  duplicate_keys=0
  dates=282 (2025-07-08..2026-09-01)
  stocks=1,967
  market_rows=TWSE 297,653 / TPEX 218,516

events.parquet
  rows=516,169
  duplicate_keys=0
  ordered_keys_equal_features=true
  event_columns=13

latest 2026-09-01
  rows=1,930
  TWSE=1,072 / TPEX=858
```

限制：本 checkout 的 `data/raw/daily_close_snapshots/` 沒有 materialized manifest／records，且 `EventStage` 只寫 mutable `events.parquet` 與 `features.parquet`，沒有保存 input snapshot ID、SignalSpec version 或 provider/rule provenance。因此上述 clean artifacts 可用來量測現況，不能冒充已綁定 ME-D1 identity 的 Radar evidence。

## 3. 已確認可延伸 seams

| Seam | 現況 | 可重用範圍 | 不可宣告事項 |
|---|---|---|---|
| ME-D1 Daily Close | immutable snapshot contract 已本機接受 | Radar scanner 的 finalized input identity | 現存 clean parquet 尚未綁定該 snapshot |
| Indicator／event 計算 | `PatternIndicatorsMixin`、`app/signals/*`、`EventDetector` 已有 deterministic rules | 收斂成單一 rule authority 的 donor | 同名欄位目前不保證同語意 |
| Pattern registry | 11 個 UI pattern definitions，含 label/category/polarity/說明 | educational metadata 與部分 catalog donor | 不是 versioned SignalSpec，也沒有 dataset/horizon/evidence/eligibility |
| 個股詳情 projection | `_pattern_signals()` 可由既有 bars 產生 read-only signals | UI mapping 與去重顯示 donor | 不是 market-wide scanner、Occurrence 或歷史 evidence |
| Research Ledger | 27 tables；目前 ledger 有 486 TrialSpecs | 既有 research identity／receipt／eligibility seam | 本機 `run_receipts`、`execution_units`、`observations`、`projection_runs` 皆為 0，不能聲稱已有 signal evidence |
| Regime research | `market-regime-history.v2` 與 append-only merge contract | future relevant-regime comparator donor | current artifact input 只記 path，未綁 DatasetSnapshot content identity |
| Market Flow Radar | strict Pydantic response、coverage/freshness/evidence/research boundary | closed read-model 與 projection boundary pattern | 是 theme-flow fixture，語意與 RADAR-01 Signal Radar 不同，不可共用 item schema 或 endpoint meaning |
| Warning research scripts | 已有 forward-return、sample count、median、negative/downside rate與 baseline delta | evaluation implementation donor | 是特定 watchlist/warning universe 的 ad hoc research，不是 canonical per-SignalSpec evidence contract |

## 4. Measured gaps

### G1 — 同名訊號存在雙重計算 authority 與實際語意漂移

`IndicatorStage` 先由 `PatternIndicatorsMixin.calculate_binary_events()` 寫入 features；`EventStage` 隨後再由 `EventDetector` 依 `config/signals.yaml` 重算 events。代表性資料的鍵完全對齊，但結果如下：

| Signal | features hits | events hits | mismatches | 已證實原因 |
|---|---:|---:|---:|---|
| `break_20d_high` | 11,620 | 22,235 | 10,615 | 10,615 筆全發生於前 20 個市場交易日內有缺列；pivot calendar window 與 per-stock observation window 不同 |
| `macd_bullish_cross` | 21,920 | 23,490 | 1,570 | 全部 event-only 筆的前一筆個股 observation 不是前一個市場交易日 |
| `macd_bearish_cross` | 21,152 | 22,934 | 1,782 | 同上 |
| `gap_up_close_strong` | 24,053 | 25,904 | 1,851 | 同上 |
| `long_upper_shadow` | 83,139 | 95,490 | 12,351 | features 多一條 `upper_shadow > close * 0.005` guard；12,351 筆全未通過該 guard |
| volume event | `volume_spike_1.5x`=43,206 | `volume_spike`=32,172 | 48,976 | features 為 20 日均量 1.5 倍且含今日；events config 為 5 日量比 2 倍，名稱與規則均不同 |

這不是 rounding noise。SignalSpec 必須先固定 calendar/observation policy、rule reference 與唯一 computation authority，否則相同 dataset 無法保證 deterministic occurrences。

### G2 — `0` 同時代表「未觸發」與「不可觀測」

`EventDetector` 遇到未知 event type、缺欄位或例外時，會記 log 後整欄填 `0`；config 不存在時則回空 events。這不符合 Radar 的 exclusion／degradation contract。

2026-09-01 的本機資料進一步證實：

```text
TPEX latest rows=858
ma20 coverage=0.0%
bb_middle coverage=0.0%
ma5_cross_ma20_up hits=0
close_above_bb_mid hits=0
```

現有 validator 仍回傳 `ok=true`；它對 features 提出 4 個 coverage warnings，但 events 沒有 issue。故 Radar 若直接消費 events，會把 858 筆缺少必要長週期 feature 的 TPEX observation 解讀成「訊號未觸發」。未來 contract 必須輸出 structured `NOT_OBSERVABLE`／exclusion reason，不能 silent zero。

### G3 — 尚無 Radar-eligible SignalSpec contract

`PatternSignalDefinition` 只有 UI 說明欄位；`config/signals.yaml` 同時混合 event rule 與 production scoring weights。兩者都缺少 `signal_version`、required dataset／features、evaluation horizon、evidence reference、eligibility status 與 rule content identity。既有 ranking weights 不得被提升為 Radar confluence authority。

### G4 — 尚無可重建 SignalOccurrence

目前 `events.parquet` 沒有 dataset fingerprint、SignalSpec version、indicator/provider provenance、rule result status、research evidence ref 或 projection build version。個股詳情的 `StockPatternSignal` 也是 request-time UI DTO，不是 occurrence evidence。

### G5 — 尚無 governed conditional-vs-base-rate evidence

warning／capital-realism scripts 有 forward-return 與 baseline delta donor，但 universe 固定於 watchlist/ranking workflow；Research Ledger 的 observation grain則是 strategy execution unit／trial aggregate，不是 signal occurrence。現有兩者都不能直接回答：

```text
ConditionalOutcome(signal, horizon, universe, regime?)
vs RelevantBaseRate(horizon, universe, regime?)
```

缺少 per-SignalSpec sample/effective-sample、overlap/episode policy、matched universe/regime baseline、effect size、downside與 OOS/forward status contract。

### G6 — 尚無可稽核 confluence redundancy policy

選取 8 個既有偏多訊號做唯讀計數，516,169 筆中有 24,589 筆同時命中至少 2 個、3,843 筆至少 3 個；最新日有 59 筆至少 2 個。這只證明共現普遍存在，不證明多次命中代表獨立 evidence。現有 display-priority 去重與 scoring weights 都沒有 signal-family／correlation／redundancy contract。

### G7 — projection shell 可重用，Signal Radar projection 尚不存在

`MarketFlowRadarResponse` 已示範 strict schema、coverage、freshness、evidence 與 `ranking_impact=NONE`，但其資料是 theme membership + institutional flow fixture。RADAR-01 可重用 projection discipline，不可沿用語意、item schema、rank 或 endpoint authority。

## 5. 最小足夠後續切片（尚未 admission）

若 Owner 明確 admission，先只開 `RADAR-01 P1-A — SignalSpec Authority and Observability Contract`：

1. 從少量既有 deterministic signals 建立 versioned SignalSpec mapping；不擴 signal 數量。
2. 每個 spec 固定唯一 rule authority、calendar policy、required features、Daily Close dataset contract、direction、horizon、evidence／eligibility state。
3. 固定三態 evaluation：`TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE`，後者帶 reason；禁止 missing/error → zero。
4. 對重疊同名欄位加入 parity gate；不一致時 fail closed，不產生 eligible occurrence。
5. 只產 contract／validator 與 RED/GREEN tests；不建立 scanner、SignalOccurrence store、historical statistics、confluence、UI、scheduler 或 production wiring。

### Why not less

只替現有 registry 增加名稱或直接讀 `events.parquet`，無法解決雙 authority、calendar drift、missing-as-zero 與 provenance 缺口，仍不能可靠回答「哪個 SignalSpec 在哪個 DatasetSnapshot 上觸發」。

### Why not more

在 rule authority 與 observability 尚未固定前先建 scanner、統計或 Radar，會把已量測到的資料語意錯誤永久化。ME-D1、Research Ledger、regime artifact 與既有 read-model 已提供足夠 donor，不需要新 ledger、provider、scheduler 或 Research Spine subsystem。

## 6. Admission gate

目前只允許：

```text
RADAR-01 = MEASURED_GAP_CONFIRMED
OWNER_DECISION = READY
IMPLEMENTATION = NOT_ADMITTED
RUNTIME_AUTHORITY = NONE
```

Owner 明確 admission P1-A 前：不開 implementation card、不改 source、不建立 scanner／projection、不改 ranking、不 push。即使 P1-A 完成，也不自動 admission P1-B 至 P1-E。

## 7. 可重跑驗證

- `.venv/bin/python -m app.pipeline_cli validate --json` → `ok=true`，features 4 warnings、events 0 issues；證明現行 validator 沒有語意 parity／observability gate。
- `.venv/bin/pytest -q tests/test_daily_close_snapshot.py tests/test_market_flow_radar.py` → `29 passed, 1 warning in 3.53s`；warning 為既有 Starlette/httpx deprecation，與本稽核無關。
- PyArrow/Pandas 唯讀 probe → 516,169 筆、兩份 parquet ordered keys 相同、無重複；差異數與原因如 G1。
- DuckDB `read_only=True` probe → 27 tables；486 TrialSpecs；run receipts、execution units、observations、projection runs 皆 0。
- CodeGraph：確認現有 signal calculation、registry、stock-detail projection、forward-return donor與 Market Flow Radar read-model 邊界。
- `rg` 查核 tests：目前沒有直接覆蓋 `EventDetector`／`detect_all_events` 的單元測試；P1-A parity RED/GREEN 不可省略。
